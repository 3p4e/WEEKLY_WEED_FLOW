"""Faithful A4 HTML documents — ImB per-strain spec + single-parameter iCoA.

The spec document renders through the owner's own archive template (tokenized);
the iCoA through the design-system shell. Both: № never "No.", MK-GMP footer,
every DB value escaped, nothing fabricated (DRAFT watermark, unselected
phenotype, roles-of-record vs executed signatures).
"""
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role):
    user, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, user["username"], otp)
    return user, {"Authorization": f"Bearer {token}"}


async def _gp_ladder(client, admin_headers, code="GP", name="Grape Pie"):
    r = await client.post("/cultivation/cultivars", json={"code": code, "name": name},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    cv = r.json()
    body = {"cultivar_id": cv["id"], "version": "v5.2", "floor_pct": 13.83, "n_batches": 10,
            "ranges": [
                {"tier": 1, "range_min": 26, "range_max": 30, "nominal": 28.0, "width_pp": 2.0},
                {"tier": 2, "range_min": 22, "range_max": 26, "nominal": 24.0, "width_pp": 2.0},
                {"tier": 3, "range_min": 18, "range_max": 22, "nominal": 20.0, "width_pp": 2.0},
                {"tier": 4, "range_min": 13.83, "range_max": 18, "nominal": 16.0, "width_pp": 2.08},
            ]}
    r = await client.post("/qc/potency-specs", json=body, headers=admin_headers)
    assert r.status_code == 201, r.text
    return cv, r.json()


async def test_spec_document_renders_the_archive_layout(client, admin_headers):
    cv, spec = await _gp_ladder(client, admin_headers)
    r = await client.get(f"/qc/potency-specs/{spec['id']}/document?tier=3",
                         headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    doc = r.text
    # identity + the tokenized data slots
    assert "Grape Pie" in doc
    assert "QCSP 001_GP-III_v.01" in doc
    assert "Grade III" in doc and "Класа III" in doc
    assert "20.00% ± 2.00%" in doc and "18.00 – 22.00%" in doc
    assert "GP_THC20:CBD1" in doc
    # house rules: № never "No.", never "EU GMP"; the ImB family footer carries
    # the template code (QCSP 001 v.03) + address + page marker per the archive
    assert "№" in doc and "No." not in doc
    assert "EU GMP" not in doc
    assert "QCSP 001 v.03" in doc and "1 | 1" in doc
    # a DRAFT ladder must SAY so and carry no signature dates
    assert "Draft — not approved" in doc
    # the app has no verified phenotype — no gold-tag selection is fabricated
    assert "INDICA-DOMINANT" not in doc
    # signatories are the locked spec roles-of-record
    assert "Blagoj Nikolov" in doc and "Jovana Romevska Cvetkovski" in doc


async def test_spec_document_approved_drops_watermark_and_dates(client, admin_headers):
    cv, spec = await _gp_ladder(client, admin_headers, code="GP2", name="Grape Pie Two")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/potency-specs/{spec['id']}/approve",
                              headers=qc2)).status_code == 200
    doc = (await client.get(f"/qc/potency-specs/{spec['id']}/document?tier=1",
                            headers=admin_headers)).text
    assert "Draft — not approved" not in doc
    assert "Grade I" in doc and "28.00% ± 2.00%" in doc and "26.00 – 30.00%" in doc


async def test_spec_document_escapes_hostile_cultivar_name(client, admin_headers):
    r = await client.post("/cultivation/cultivars",
                          json={"code": "XSS", "name": "<script>alert(1)</script>"},
                          headers=admin_headers)
    cv = r.json()
    body = {"cultivar_id": cv["id"], "version": "vx", "floor_pct": 5.0, "n_batches": 0,
            "ranges": [{"tier": 1, "range_min": 5.0, "range_max": 30.0, "nominal": 17.5}]}
    spec = (await client.post("/qc/potency-specs", json=body, headers=admin_headers)).json()
    doc = (await client.get(f"/qc/potency-specs/{spec['id']}/document?tier=1",
                            headers=admin_headers)).text
    assert "<script>alert(1)</script>" not in doc
    assert "&lt;script&gt;" in doc
    assert r.status_code == 201


async def test_spec_document_missing_tier_is_404(client, admin_headers):
    cv, spec = await _gp_ladder(client, admin_headers, code="GP3", name="Grape Pie Three")
    assert (await client.get(f"/qc/potency-specs/{spec['id']}/document?tier=6",
                             headers=admin_headers)).status_code == 404
    # base USER cannot read documents
    _, user_h = await _actor(client, admin_headers, "USER")
    assert (await client.get(f"/qc/potency-specs/{spec['id']}/document?tier=1",
                             headers=user_h)).status_code == 403


async def test_icoa_html_renders_result_and_honest_signoff(client, admin_headers):
    from tests.test_qc import _spec, _coa
    spec = await _spec(client, admin_headers, material="IHTML-MAT")
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Loss on Drying", "test_method": "Ph. Eur. 2.2.32",
                                "unit": "%", "upper_limit": 12.0}, headers=admin_headers)
    pid = p.json()["id"]
    coa = await _coa(client, admin_headers, spec["id"], batch="B-IHTML", report_date="2026-07-01")
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": pid, "test_name": "Loss on Drying",
                                    "result_numeric": 6.77, "upper_limit": 12.0, "unit": "%",
                                    "result_date": "2026-07-01"},
                              headers=admin_headers)).status_code == 201
    r = await client.get(f"/qc/certificates/{coa['id']}/icoa-html?parameter_id={pid}",
                         headers=admin_headers)
    assert r.status_code == 200, r.text
    doc = r.text
    assert "Internal Certificate of Analysis" in doc
    assert "iCoA-PP-" in doc                     # per-type numbering series
    assert "Loss on Drying" in doc and "6.77" in doc
    assert "MK GMP Certified Facility" in doc and "EU GMP" not in doc
    assert "№" in doc and "No." not in doc
    # no e-signature captured → honest roles-of-record attribution, never an
    # executed-signature claim
    assert "no electronic signature captured" in doc
    assert "Annex 11 audit trail" in doc


async def test_icoa_html_rejects_non_internal_certs(client, admin_headers):
    from tests.test_qc import _spec
    spec = await _spec(client, admin_headers, material="IHTML-ECOA")
    r = await client.post("/qc/certificates",
                          json={"batch_id": "B-EX", "specification_id": spec["id"],
                                "cert_type": "ECOA", "source_lab": "Ext Lab"},
                          headers=admin_headers)
    coa = r.json()
    # any parameter id — the type gate fires first
    r = await client.get(
        f"/qc/certificates/{coa['id']}/icoa-html?parameter_id={coa['specification_id']}",
        headers=admin_headers)
    assert r.status_code == 409
    assert "INTERNAL" in r.json()["detail"]


async def test_icoa_html_watermarks_non_presentable_status(client, admin_headers):
    """A document must never look released before its data is (same principle
    as the ImB spec's DRAFT watermark). DRAFT and VOIDED certificates must
    carry an unmistakable stamp; only APPROVED/RELEASED renders clean."""
    from tests.test_qc import _coa, _hoqc_walk, _spec
    spec = await _spec(client, admin_headers, material="IHTML-WM")
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Loss on Drying", "test_method": "Ph. Eur. 2.2.32",
                                "unit": "%", "upper_limit": 12.0}, headers=admin_headers)
    pid = p.json()["id"]

    async def _coa_with_result(batch):
        coa = await _coa(client, admin_headers, spec["id"], batch=batch, report_date="2026-07-01")
        assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                                  json={"parameter_id": pid, "test_name": "Loss on Drying",
                                        "result_numeric": 6.77, "upper_limit": 12.0, "unit": "%",
                                        "result_date": "2026-07-01"},
                                  headers=admin_headers)).status_code == 201
        return coa

    # DRAFT (pre-approval) — the softer "not approved" stamp. Check for the
    # rendered watermark DIV itself, not just the (always-present) stylesheet
    # rule defining .draft-wm/.void-wm.
    draft_coa = await _coa_with_result("B-WM-DRAFT")
    doc = (await client.get(f"/qc/certificates/{draft_coa['id']}/icoa-html?parameter_id={pid}",
                            headers=admin_headers)).text
    assert 'class="wm draft-wm"' in doc and "Draft — Not Approved" in doc

    # VOIDED (QCSOP 012 §6.6) — the strongest stamp; the pass/fail verdict
    # badge is left untouched (it's driven by the decision field), so the
    # watermark is the real, hard-to-miss tell that the document is invalid
    void_coa = await _coa_with_result("B-WM-VOID")
    assert (await client.patch(f"/qc/certificates/{void_coa['id']}",
                               json={"decision": "PASS"}, headers=admin_headers)).status_code == 200
    assert (await client.post(f"/qc/certificates/{void_coa['id']}/void",
                              json={"reason": "wrong batch identified on sampling"},
                              headers=admin_headers)).status_code == 200
    doc = (await client.get(f"/qc/certificates/{void_coa['id']}/icoa-html?parameter_id={pid}",
                            headers=admin_headers)).text
    assert 'class="wm void-wm"' in doc and "VOIDED — Do Not Use" in doc
    assert "Conforms to Specification" in doc

    # APPROVED/RELEASED — the presentable states — carry NEITHER watermark
    _, qp = await _actor(client, admin_headers, "QP")
    ok_coa = await _coa_with_result("B-WM-OK")
    assert (await client.patch(f"/qc/certificates/{ok_coa['id']}",
                               json={"decision": "PASS"}, headers=admin_headers)).status_code == 200
    await _hoqc_walk(client, admin_headers, qp, ok_coa["id"])
    doc = (await client.get(f"/qc/certificates/{ok_coa['id']}/icoa-html?parameter_id={pid}",
                            headers=admin_headers)).text
    assert 'class="wm draft-wm"' not in doc and 'class="wm void-wm"' not in doc
    assert "Not Approved" not in doc and "Do Not Use" not in doc
