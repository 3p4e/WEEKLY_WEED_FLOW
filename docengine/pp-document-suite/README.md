# pp-document-suite — the Purely Plant .docx engine

This is the code that actually renders Purely Plant controlled documents. It was recovered from
inside the `letta` container (`/root/.letta/pp-document-suite`), where it existed only as
unversioned files on a container filesystem — no copy in any repository. It is committed here so
that it survives the container.

## What it does

`build_from_md.py` renders bilingual Macedonian|English Markdown into a controlled `.docx` in the
house style, per `PP_UNIFIED_DOCX_GUIDE.md`:

```
python3 scripts/build_from_md.py <src.md> <out.docx>
```

- **doctype SOP** → `pp_format` two-column layout (MK|EN, divider, native TOC); §7/§8/§9 as nested
  full-width tables sized by `pp_report.fixed()`.
- **doctype ANNEX / FORM / CHECKLIST / LOG** → base-template shell (logo header, Page X of Y),
  navy `#2B547E` section banners, and every table built through `pp_report`: label|value forms as
  2-column with `#F2F2F2` labels, data tables with a navy header row, zebra rows and a repeating
  header across page breaks, and single-select lists as `status_grid()` checkbox grids.

Column widths are not hand-set — `pp_report.fixed()` decides them from how each column is used
(compact-centred summaries vs full-width data, purpose-sized Name/Date/Signature entry columns,
minimal ordinal columns).

## Modules

| File | Role |
|---|---|
| `build_from_md.py` | entry point — parses the `<!--HEADERDATA-->` block and `[[TABLE]]`/`[[FORM]]` blocks, dispatches SOP vs annex |
| `pp_format.py` | page setup, two-column SOP body, base-template shell, headers/footers |
| `pp_report.py` | the layout brain — `fixed()` width solver, table/form/grid builders |
| `pp_theme.py` | house constants: navy `#2B547E`, Calibri, font floor 6 pt, shading `clear` |
| `pp_data.py` | data shaping for tables and charts |
| `pp_charts.py` | matplotlib chart rendering for reports |
| `pp_verify.py` | post-build verification of the produced `.docx` |
| `assets/PP_BASE_TEMPLATE.docx` | the base template the annex/form shell is built from |

## How Letta called it

Two custom Letta tools wrapped this engine, and both were thin:

- `build_pp_document(markdown, out_name)` — wrote the Markdown to a temp file, put
  `/root/.letta/pp-libs` and `scripts/` on `sys.path`, called `build_from_md.main(src, out)`, and
  returned JSON `{ok, verify, path, bytes}` with the result under `/root/.letta/pp-out`.
- `fetch_pp_document(path)` — returned a produced `.docx` as base64 for download.

The agents held no logic of their own; all of it is here. That is why the fleet can be rebuilt
from scratch without losing anything, provided this directory is preserved.

## Dependencies

`requirements.txt` pins the versions that were vendored next to the engine. The vendored tree
itself (248 MB of wheels: python-docx, lxml, matplotlib, numpy, pillow, pymupdf and their
transitive deps) is not committed.

## Provenance

Extracted 2026-08-17 from container `letta` (`letta/letta:latest`), source path
`/root/.letta/pp-document-suite`. Archive md5 `10630eb9060e59e41f7aa844a6d4d5ce`. Two `.bak`
files and `__pycache__` were excluded; all seven modules parse cleanly. Nothing was modified —
this is the engine as it runs today.
