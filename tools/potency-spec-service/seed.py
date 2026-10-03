#!/usr/bin/env python3
"""Seed the Potency Spec Service from the strain catalogue.

Reads the ``const DATA = [...]`` array out of the repo file
``docs/tools/potency-range-builder.html``, builds one *draft* Spec per strain,
and PUTs each to a running instance of this service.

Each catalogue entry is ``[abbr, name, [[value, batch, cert], ...], [nominal, ...]]``.
For every nominal ``n`` the seed uses the "10% max" tolerance ``round(n*0.10, 2)``
and the range ``lo = round(n - tol, 2)``, ``hi = round(n + tol - 0.01, 2)``.
Measured results are intentionally left empty (``results_entered`` /
``results_excluded`` are ``[]``) — this seeds specifications, not measurements.

Usage:
    python seed.py [BASE_URL] [CATALOGUE_HTML]

    BASE_URL         base URL of a running instance
                     (argv[1] or $SPECS_BASE_URL, default http://localhost:8000)
    CATALOGUE_HTML   path to potency-range-builder.html
                     (argv[2] or $CATALOGUE_HTML, else auto-discovered by walking
                      up from the CWD and this script looking for
                      docs/tools/potency-range-builder.html)

Flags:
    --skip-existing  GET each id first and skip specs that already exist, so a
                     re-seed of a live DB never clobbers user edits. Default off:
                     by default every spec is PUT (upsert), which is idempotent
                     in that repeated runs converge to the seed state.

Idempotent: PUT is an upsert keyed by id, so running this repeatedly yields the
same catalogue state.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from app.catalogue import build_spec, extract_data_array

CATALOGUE_RELPATH = os.path.join("docs", "tools", "potency-range-builder.html")


def find_catalogue(explicit: str | None) -> str:
    """Locate the catalogue HTML file."""
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    env = os.getenv("CATALOGUE_HTML")
    if env:
        candidates.append(env)
    # The served SPA itself carries the catalogue, so a container / self-contained
    # run can seed with no repo present.
    candidates.append(os.path.join(os.getenv("STATIC_DIR", "web"), "index.html"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "index.html"))
    # Walk up from both the CWD and this script's directory.
    roots = [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
    for root in roots:
        cur = root
        for _ in range(8):
            candidates.append(os.path.join(cur, CATALOGUE_RELPATH))
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "Could not find the catalogue HTML. Pass its path as the 2nd argument or "
        "set $CATALOGUE_HTML (looking for docs/tools/potency-range-builder.html)."
    )


def _get_json(url: str):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _put_json(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="PUT", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def spec_exists(base_url: str, spec_id: str) -> bool:
    try:
        status, _ = _get_json(f"{base_url}/api/specs/{spec_id}")
        return status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    skip_existing = "--skip-existing" in argv[1:]

    base_url = (args[0] if len(args) > 0 else os.getenv("SPECS_BASE_URL") or "http://localhost:8000").rstrip("/")
    catalogue = find_catalogue(args[1] if len(args) > 1 else None)

    with open(catalogue, "r", encoding="utf-8") as fh:
        html_text = fh.read()
    data = extract_data_array(html_text)

    print(f"catalogue : {catalogue}")
    print(f"base URL  : {base_url}")
    print(f"strains   : {len(data)}")
    print()

    put = skipped = failed = 0
    for entry in data:
        abbr, name, _measured, nominals = entry[0], entry[1], entry[2], entry[3]
        spec = build_spec(abbr, name, nominals)
        spec_id = spec["id"]
        url = f"{base_url}/api/specs/{spec_id}"
        try:
            if skip_existing and spec_exists(base_url, spec_id):
                print(f"  skip   {spec_id:<6} (already present)")
                skipped += 1
                continue
            status, _ = _put_json(url, spec)
            print(f"  put    {spec_id:<6} {name}  ({len(nominals)} nominal(s)) -> {status}")
            put += 1
        except urllib.error.HTTPError as e:
            print(f"  FAIL   {spec_id:<6} HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
            failed += 1
        except urllib.error.URLError as e:
            print(f"  FAIL   {spec_id:<6} {e}")
            failed += 1

    print()
    print(f"done: {put} put, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
