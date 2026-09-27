# docengine.app.builder — the formatting core, adopted COMPLETELY from
# pp-document-suite per docs/DOCENGINE-CANON-2026-07.md.
#
# In-process wrapper around the vendored canonical engine:
#   bilingual Markdown --build_from_md--> .docx --pp_verify--> PASS | FAIL
#
# HARD GATE: a document that does not print `RESULT: PASS` never leaves this
# module — build() raises instead of returning a path. This mirrors the live
# Letta tool's contract ({ok, verify, path, bytes}) but enforces PASS.
import contextlib
import hashlib
import io
import os
import re
import sys
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import ENGINE_SCRIPTS

# The engine scripts import each other as top-level modules (pp_format,
# pp_report, ...), exactly like inside the packaged skill — put the vendored
# scripts dir on sys.path once.
if str(ENGINE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ENGINE_SCRIPTS))

import build_from_md  # noqa: E402  (vendored engine)
import pp_verify      # noqa: E402  (vendored engine)

# python-docx documents are not thread-safe and the engine uses module state
# (template lookup, sys.argv shim in verify) — serialize builds. Throughput is
# not the concern here; correctness of controlled documents is.
_BUILD_LOCK = threading.Lock()

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class VerifyFailed(Exception):
    """The produced .docx failed the pp_verify gate — it must not be shipped."""

    def __init__(self, report: str):
        super().__init__("pp_verify FAILED")
        self.report = report


@dataclass
class BuildResult:
    path: Path
    bytes: int
    verify_report: str
    doctype: str


def safe_name(name: str) -> str:
    """Collapse anything path-hostile out of a user-supplied output name."""
    name = _SAFE_NAME.sub("_", (name or "document").strip()) or "document"
    return name[:120]


def sha256_text(text: str) -> str:
    """Hash of a document source, for the provenance record."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def run_verify(docx_path: Path, min_pt: float = 6.0, require_bilingual: bool = True) -> tuple[bool, str]:
    """Run the vendored pp_verify in-process; return (passed, report_text)."""
    buf = io.StringIO()
    argv = sys.argv
    sys.argv = ["pp_verify", str(docx_path), "--min-pt", str(min_pt),
                "--require-bilingual", "true" if require_bilingual else "false"]
    code = 0
    try:
        with contextlib.redirect_stdout(buf):
            try:
                pp_verify.main()
            except SystemExit as e:  # pp_verify exits 0=PASS 1=FAIL
                code = int(e.code or 0)
    finally:
        sys.argv = argv
    report = buf.getvalue().strip()
    # pp_verify opens its report with `== VERIFY: <absolute path>`, and this
    # report is handed straight back to API callers (both in the success
    # response and in VerifyFailed's 422 detail) and stored in the documents
    # table. That published the service's container filesystem layout to every
    # client for no diagnostic benefit — the basename identifies the artifact
    # just as well, and the caller already knows which document it asked for.
    report = report.replace(str(docx_path), Path(docx_path).name)
    return code == 0 and "RESULT: PASS" in report, report


def _headerdata_span(lines: list[str]) -> tuple[int | None, int | None]:
    """(start, end) line indexes of the FIRST HEADERDATA block, line-anchored
    exactly like build_from_md.py's parser (which is why a naive non-greedy
    regex is wrong here: it would stop at the first literal '-->' inside a
    field value)."""
    start = end = None
    for idx, ln in enumerate(lines):
        if ln.strip() == "<!--HEADERDATA":
            start = idx
            break
    if start is not None:
        for idx in range(start + 1, len(lines)):
            if lines[idx].strip() == "-->":
                end = idx
                break
    return start, end


def headerdata(markdown: str) -> dict[str, str]:
    """The `key: value` fields of the document's HEADERDATA block, and ONLY
    those. Every fact about a document's identity (code, version, doctype,
    titles, orientation, the bilingual switch) is read from here.

    It used to be read from anywhere in the markdown with a `^doctype:` /
    `^bilingual:` regex, so a line `bilingual: no` in the body — a table
    cell, a stray paragraph — switched off the bilingual verification of the
    whole document (review 2026-09-27, DI-06). The block is the header; the
    body is content."""
    lines = markdown.splitlines()
    start, end = _headerdata_span(lines)
    if start is None or end is None:
        return {}
    out: dict[str, str] = {}
    for ln in lines[start + 1:end]:
        if ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        k = k.strip().lower()
        if k:
            out[k] = v.strip()
    return out


def _strip_headerdata(markdown: str) -> str:
    """The markdown without its HEADERDATA block (see _headerdata_span)."""
    lines = markdown.splitlines()
    start, end = _headerdata_span(lines)
    if start is not None and end is not None:
        return "\n".join(lines[:start] + lines[end + 1 :])
    return markdown


def _source_word_char_counts(markdown: str) -> tuple[int, int]:
    """§5A fidelity source-side count: the ASSEMBLED markdown minus its own
    grammar tokens (HEADERDATA block, [[FORM/TABLE]] markers, heading
    markup, column separators). This pipeline never has a second reference
    .docx to compare against (build() only ever has the source markdown and
    the produced .docx) — the source markdown itself is the ground truth
    for a no-impoverishment check."""
    body = _strip_headerdata(markdown)
    body = re.sub(r"^\[\[/?(?:FORM|TABLE)[^\]]*\]\]\s*$", "", body, flags=re.M)
    body = re.sub(r"^#{1,6}\s+", "", body, flags=re.M)
    body = body.replace("|||", " ").replace("~~", " ").replace("|", " ")
    words = len(re.findall(r"\S+", body))
    chars = len(re.sub(r"\s+", "", body))
    return words, chars


def build(markdown: str, out_dir: Path, out_name: str = "document") -> BuildResult:
    """Bilingual Markdown -> controlled .docx, verified. Raises VerifyFailed
    (doc deleted) on a FAIL — a failed document never exists on disk after."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # H13 — the output path used to be safe_name(out_name) + ".docx", derived
    # from the document CODE alone. Two concurrent builds of the same code
    # therefore wrote the same file: they interleaved, and the FAIL path below
    # (out.unlink) could delete the OTHER build's *passing* document. The
    # service runs ONE uvicorn worker today (Dockerfile, 2026-09-07), so the
    # in-process _BUILD_LOCK does serialise builds — but a unique path per
    # build is what makes that safe whatever the worker count.
    # Each build now owns a unique path. It is written under a dot-prefixed
    # `.partial` name and only os.replace()d into place once it has PASSED, so
    # a reader can never observe a half-written or unverified document, and the
    # FAIL cleanup can only ever remove this build's own temp file.
    stamp = uuid.uuid4().hex[:12]
    final = out_dir / f"{safe_name(out_name)}-{stamp}.docx"
    out = out_dir / f".{safe_name(out_name)}-{stamp}.partial.docx"
    hd = headerdata(markdown)
    doctype = (hd.get("doctype") or "SOP").upper()
    # Only the header may switch bilingual verification off — never a line
    # in the body (see headerdata()).
    require_bilingual = hd.get("bilingual", "").strip().lower() not in ("no", "false")
    with _BUILD_LOCK:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(markdown)
            src = f.name
        try:
            build_from_md.main(src, str(out))
        finally:
            Path(src).unlink(missing_ok=True)
        passed, report = run_verify(out, require_bilingual=require_bilingual)
        # §5A no-impoverishment check: the produced .docx must not contain
        # LESS content than the source markdown it was built from. Always
        # run and always reported, even when already failing on font/
        # bilingual, so a FAIL report names every reason at once.
        src_words, src_chars = _source_word_char_counts(markdown)
        r = pp_verify.analyse(str(out))
        fid_ok = r["words"] >= src_words and r["chars"] >= src_chars
        report += (f"\n   FIDELITY (§5A, markdown-source) output>=source:"
                   f" words {r['words']}>={src_words}, chars {r['chars']}>={src_chars}"
                   f"  [{'OK' if fid_ok else 'FAIL'}]")
        passed = passed and fid_ok
    if not passed:
        out.unlink(missing_ok=True)
        raise VerifyFailed(report)
    # Atomic publish: same filesystem, so os.replace is a rename, and the
    # document appears at its final path complete and already verified.
    os.replace(out, final)
    return BuildResult(
        path=final, bytes=final.stat().st_size, verify_report=report, doctype=doctype
    )
