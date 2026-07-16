# Offline proof of the formatting core: the canonical merged engine builds
# real bilingual documents and the PASS gate actually gates.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import builder  # noqa: E402

SOP_MD = """<!--HEADERDATA
mk_title: Тест СОП за примерок
en_title: Test Sampling SOP
code: QCSOP-999
version: 1.0
doctype: SOP
orient: portrait
-->
# 1.0 ЦЕЛ|PURPOSE
Оваа процедура ја опишува постапката за земање мостри.|This procedure describes sampling.

# 3.0 ОДГОВОРНОСТИ|RESPONSIBILITIES
[[TABLE]]
Улога~~Role|||Одговорност~~Responsibility
Аналитичар~~Analyst|||Земање мостра~~Sampling
[[/TABLE]]

# 6.0 ПОСТАПКА|PROCEDURE
Чекор еден: подготовка.|Step one: preparation.
"""

FORM_MD = """<!--HEADERDATA
mk_title: Образец за земање мостра
en_title: Sampling Form
code: FM-QC-999
version: 1.0
doctype: FORM
orient: portrait
-->
# 1.0 ИНФОРМАЦИИ|INFORMATION
[[FORM:grid]]
Датум~~Date|||
Серија~~Batch|||
Материјал~~Material|||
Аналитичар~~Analyst|||
[[/FORM]]
"""


def test_sop_builds_and_passes(tmp_path):
    r = builder.build(SOP_MD, tmp_path, "sop_test")
    assert r.path.exists() and r.bytes > 10_000
    assert "RESULT: PASS" in r.verify_report
    assert r.doctype == "SOP"


def test_form_grid_builds_and_passes(tmp_path):
    r = builder.build(FORM_MD, tmp_path, "form_test")
    assert r.path.exists() and r.bytes > 10_000
    assert "RESULT: PASS" in r.verify_report
    assert r.doctype == "FORM"


def test_verify_gate_blocks_and_deletes(tmp_path, monkeypatch):
    # Force the verifier to fail: the artifact must NOT survive on disk.
    monkeypatch.setattr(builder, "run_verify", lambda p, min_pt=6.0: (False, "RESULT: FAIL"))
    with pytest.raises(builder.VerifyFailed) as e:
        builder.build(SOP_MD, tmp_path, "gated")
    assert "FAIL" in e.value.report
    assert not (tmp_path / "gated.docx").exists()


def test_house_style_in_output(tmp_path):
    # The produced docx carries the house navy #2B547E and Calibri.
    import zipfile
    r = builder.build(FORM_MD, tmp_path, "style_test")
    xml = zipfile.ZipFile(r.path).read("word/document.xml").decode("utf-8")
    assert "2B547E" in xml
    assert "Calibri" in xml


def test_safe_name():
    assert builder.safe_name("../../etc/passwd") == ".._.._etc_passwd"
    assert builder.safe_name("") == "document"
    assert "/" not in builder.safe_name("a/b\\c d")
