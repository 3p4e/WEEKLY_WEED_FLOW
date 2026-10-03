"""Shared catalogue parsing + draft-spec construction.

Both the startup auto-seed (``app.main``) and the external HTTP seeder
(``seed.py``) use these, so the ``const DATA`` parsing and the tolerance/range
maths live in exactly one place.
"""

from __future__ import annotations

import json


def extract_data_array(html_text: str, name: str = "DATA") -> list:
    """Extract and parse the ``const <name> = [ ... ];`` array (valid JSON).

    ``DATA`` is the Purely Plant catalogue; ``VERSA`` the Tetra Hip → Versa one.
    """
    idx = html_text.find("const " + name + " ")
    if idx == -1:
        raise ValueError(f"`const {name}` not found in catalogue HTML")
    eq = html_text.find("=", idx)
    start = html_text.find("[", eq)
    if start == -1:
        raise ValueError(f"could not find start of {name} array")

    # Balanced-bracket scan that ignores brackets inside double-quoted strings.
    depth = 0
    in_str = False
    esc = False
    i = start
    while i < len(html_text):
        c = html_text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return json.loads(html_text[start : i + 1])
        i += 1
    raise ValueError(f"unbalanced {name} array in catalogue HTML")


def build_spec(abbr: str, name: str, nominals: list) -> dict:
    """Build a draft Spec dict for one strain from its catalogue grades.

    A grade is either a bare nominal, which opens at the 10 % ceiling, or a
    ``[nominal, tolerance]`` pair carrying the tolerance the specification
    actually prints. The Purely Plant grades have been the pair form since the
    15.09.2026 specification was adopted, where the tolerance is deliberately
    not a flat 10 % on every grade (Amnesia Core Cut is 12 ± 0.95); the Versa
    product grades, derived from the product codes, are still ± 10 %.
    """
    tol: dict[str, float] = {}
    ranges: list[dict] = []
    for grade in nominals:
        if isinstance(grade, (list, tuple)):
            n, t = float(grade[0]), round(float(grade[1]), 2)
        else:
            n, t = float(grade), round(float(grade) * 0.10, 2)
        t = min(t, round(n * 0.10, 2))  # never above the 10 % ceiling
        lo = round(n - t, 2)
        hi = round(n + t - 0.01, 2)
        tol[str(int(n))] = t
        ranges.append({"nominal": int(n), "tol": t, "lo": lo, "hi": hi})
    return {
        "id": abbr.upper(),
        "name": name,
        "custom": False,                # from the seed catalogue, not user-created
        "status": "draft",
        "tol": tol,
        "ranges": ranges,
        "results_entered": [],
        "results_excluded": [],
    }
