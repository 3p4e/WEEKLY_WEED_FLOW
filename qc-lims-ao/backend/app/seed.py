"""
Idempotent seed script for the QC LIMS backend.

Run from the ``backend/`` directory:

    python -m app.seed

Creates tables (safe before the app boots) and inserts a realistic demo
dataset in FK-safe order:
    users -> specifications (+ spec_parameters) -> samples ->
    certificates_of_analysis (+ test_results) -> oos_records -> audit_entries

Idempotent: every insert is guarded by a lookup on the unique business key,
so the script can be run repeatedly without creating duplicates.
"""

import asyncio
import os
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

# Importing app.models registers every model on Base.metadata.
import app.models  # noqa: F401
from app.core.database import Base, async_session, engine
from app.core.security import hash_password
from app.models.audit import AuditAction, AuditEntry
from app.models.certificate import (
    BatchDecision,
    CertificateOfAnalysis,
    COAStatus,
    TestResult,
    TestResultStatus,
)
from app.models.custody import ChainOfCustody
from app.models.oos import OOSRecord, OOSRiskLevel, OOSStatus, OOSType
from app.models.sample import SampleStatus, SampleType, Sample
from app.models.sampling_request import RQSStatus, SamplingRequest
from app.models.stability import StabilityStudy
from app.models.transport import SampleTransport
from app.models.water import WaterTest
from app.models.specification import (
    SpecParameter,
    SpecParameterType,
    SpecStatus,
    Specification,
    TestLocation,
)
from app.models.user import User, UserRole

PASSWORD = "Password123!"

# Track what happened for the summary print.
_created: list[str] = []
_skipped: list[str] = []


async def _get_or_create(session, model, where, factory, label):
    """Return existing row matching ``where`` or create one via ``factory``."""
    result = await session.execute(select(model).where(where))
    obj = result.scalar_one_or_none()
    if obj is not None:
        _skipped.append(label)
        return obj, False
    obj = factory()
    session.add(obj)
    await session.flush()
    _created.append(label)
    return obj, True


async def seed() -> None:
    # 1. Create tables (safe to run before the app).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Demo data is gated: an unset/false flag means the backend boots with
    # whatever the database already contains. Set SEED_DEMO_DATA=true on a
    # fresh deploy (e.g. local dev) to populate the original fictional users,
    # samples, COAs, OOS records, etc. Production keeps it OFF so a restart
    # cannot re-introduce demo records into a purged database.
    if os.environ.get("SEED_DEMO_DATA", "").lower() not in ("1", "true", "yes"):
        print("⏭  SEED_DEMO_DATA not set — skipping demo data seed.")
        return

    async with async_session() as session:
        # ── Users ───────────────────────────────────────────────────────────
        pwd = hash_password(PASSWORD)
        user_specs = [
            ("elena", "elena@purelyplant.eu", "Elena Stojanova", UserRole.QC_MANAGER),
            ("stefan", "stefan@purelyplant.eu", "Stefan Petrov", UserRole.QC_ANALYST),
            ("jana", "jana@purelyplant.eu", "Jana Ilieva", UserRole.QP),
            ("sofija", "sofija@purelyplant.eu", "Sofija Markova", UserRole.QA_AUDITOR),
            ("admin", "admin@purelyplant.eu", "System Administrator", UserRole.SYSTEM_ADMIN),
        ]
        users: dict[str, User] = {}
        for username, email, full_name, role in user_specs:
            obj, _ = await _get_or_create(
                session,
                User,
                User.email == email,
                lambda u=username, e=email, fn=full_name, r=role: User(
                    username=u,
                    email=e,
                    full_name=fn,
                    role=r.value,
                    password_hash=pwd,
                    is_active=True,
                ),
                f"user:{email}",
            )
            users[username] = obj

        elena = users["elena"]
        stefan = users["stefan"]
        jana = users["jana"]
        sofija = users["sofija"]

        # ── Specification (+ parameters) ────────────────────────────────────
        spec, spec_created = await _get_or_create(
            session,
            Specification,
            Specification.spec_id == "PP-SPEC-2026-0001",
            lambda: Specification(
                spec_id="PP-SPEC-2026-0001",
                material_code="CF-WR-001",
                material_name_en="Cannabis Flower — White Rhino",
                material_name_mk="Канабис цвет — Бел Носорог",
                version=1,
                effective_date=date(2026, 1, 15),
                status=SpecStatus.ACTIVE.value,
                approved_by_id=elena.id,
            ),
            "specification:PP-SPEC-2026-0001",
        )

        # Parameters (only if none exist yet for this spec).
        existing_params = (
            await session.execute(
                select(SpecParameter).where(SpecParameter.spec_id == spec.id)
            )
        ).scalars().all()
        param_loss = None
        if not existing_params:
            param_loss = SpecParameter(
                spec_id=spec.id,
                test_name_en="Loss on Drying",
                test_name_mk="Губење при сушење",
                test_method="Ph.Eur. 2.2.32",
                spec_type=SpecParameterType.NUMERIC_MAX.value,
                upper_limit=10.0,
                unit="% w/w",
                test_location=TestLocation.IN_HOUSE.value,
            )
            param_pest = SpecParameter(
                spec_id=spec.id,
                test_name_en="Pesticide Residues — Total",
                test_name_mk="Остатоци од пестициди — Вкупно",
                test_method="Ph.Eur. 2.8.18",
                spec_type=SpecParameterType.NUMERIC_MAX.value,
                upper_limit=0.01,
                unit="mg/kg",
                test_location=TestLocation.EXTERNAL.value,
            )
            param_thc = SpecParameter(
                spec_id=spec.id,
                test_name_en="Total THC",
                test_name_mk="Вкупен ТХЦ",
                test_method="Ph.Eur. 2.8.10",
                spec_type=SpecParameterType.NUMERIC_BOUNDED.value,
                lower_limit=21.0,
                upper_limit=24.9,
                unit="% w/w",
                test_location=TestLocation.IN_HOUSE.value,
            )
            session.add_all([param_loss, param_pest, param_thc])
            await session.flush()
            _created.append("spec_parameters:3")
        else:
            param_loss = existing_params[0]
            _skipped.append("spec_parameters")

        # ── Samples ─────────────────────────────────────────────────────────
        sample_specs = [
            ("PP-SMP-2026-0036", "PP-BATCH-2026-A1", SampleType.RAW_MATERIAL,
             "Cannabis Flower — White Rhino", "Канабис цвет — Бел Носорог",
             "SP_06", SampleStatus.COLLECTED),
            ("PP-SMP-2026-0037", "PP-BATCH-2026-A1", SampleType.IPC,
             "Cannabis Flower — White Rhino (drying)", "Канабис цвет — Бел Носорог (сушење)",
             "SP_07", SampleStatus.IN_TEST),
            ("PP-SMP-2026-0038", "PP-BATCH-2026-A1", SampleType.FINISHED_PRODUCT,
             "Cannabis Flower — White Rhino (packaged)", "Канабис цвет — Бел Носорог (спакуван)",
             "SP_09", SampleStatus.TESTED),
            ("PP-SMP-2026-0039", "PP-BATCH-2026-B2", SampleType.RAW_MATERIAL,
             "Cannabis Flower — Northern Lights", "Канабис цвет — Северна Светлина",
             "SP_06", SampleStatus.APPROVED),
            ("PP-SMP-2026-0040", "PP-BATCH-2026-B2", SampleType.FINISHED_PRODUCT,
             "Cannabis Flower — Northern Lights (packaged)", "Канабис цвет — Северна Светлина (спакуван)",
             "SP_09", SampleStatus.REJECTED),
            ("PP-SMP-2026-0041", "PP-BATCH-2026-C3", SampleType.IPC,
             "Cannabis Flower — Amnesia Haze (curing)", "Канабис цвет — Амнезија (зреење)",
             "SP_08", SampleStatus.IN_TEST),
        ]
        for sid, batch, stype, en, mk, sp, sstatus in sample_specs:
            await _get_or_create(
                session,
                Sample,
                Sample.sample_id == sid,
                lambda sid=sid, batch=batch, stype=stype, en=en, mk=mk, sp=sp, st=sstatus: Sample(
                    sample_id=sid,
                    batch_id=batch,
                    sample_type=stype.value,
                    material_name_en=en,
                    material_name_mk=mk,
                    material_code="CF-WR-001",
                    sampling_date=datetime(2026, 2, 10, 9, 0, tzinfo=timezone.utc),
                    sampled_by_id=stefan.id,
                    status=st.value,
                    sp_type=sp,
                    potency_grade="B",
                ),
                f"sample:{sid}",
            )

        # ── Certificate of Analysis (+ test results) ────────────────────────
        coa, coa_created = await _get_or_create(
            session,
            CertificateOfAnalysis,
            CertificateOfAnalysis.coa_number == "PP-COA-2026-0018",
            lambda: CertificateOfAnalysis(
                coa_number="PP-COA-2026-0018",
                batch_id="PP-BATCH-2026-A1",
                specification_id=spec.id,
                report_date=date(2026, 2, 20),
                analyst_id=stefan.id,
                reviewer_id=elena.id,
                approver_id=jana.id,
                status=COAStatus.APPROVED.value,
                decision=BatchDecision.PASS.value,
            ),
            "coa:PP-COA-2026-0018",
        )

        existing_results = (
            await session.execute(
                select(TestResult).where(TestResult.coa_id == coa.id)
            )
        ).scalars().all()
        if not existing_results and param_loss is not None:
            params = (
                await session.execute(
                    select(SpecParameter).where(SpecParameter.spec_id == spec.id)
                )
            ).scalars().all()
            p0 = params[0]
            p1 = params[1] if len(params) > 1 else params[0]
            session.add_all([
                TestResult(
                    coa_id=coa.id,
                    parameter_id=p0.id,
                    result_value="8.4",
                    result_numeric=8.4,
                    unit="% w/w",
                    complies=True,
                    status=TestResultStatus.PASS.value,
                    analyst_id=stefan.id,
                    verified_by_id=elena.id,
                ),
                TestResult(
                    coa_id=coa.id,
                    parameter_id=p1.id,
                    result_value="<0.01",
                    result_numeric=0.005,
                    unit="mg/kg",
                    complies=True,
                    status=TestResultStatus.PASS.value,
                    analyst_id=stefan.id,
                    verified_by_id=elena.id,
                ),
            ])
            await session.flush()
            _created.append("test_results:2")
        else:
            _skipped.append("test_results")

        # ── OOS record ──────────────────────────────────────────────────────
        # Needs a test_result_id (NOT NULL FK). Use the pesticide result.
        a_result = (
            await session.execute(
                select(TestResult).where(TestResult.coa_id == coa.id)
            )
        ).scalars().first()
        if a_result is not None:
            await _get_or_create(
                session,
                OOSRecord,
                OOSRecord.oos_number == "PP-OOS-2026-003",
                lambda: OOSRecord(
                    oos_number="PP-OOS-2026-003",
                    test_result_id=a_result.id,
                    detection_date=datetime(2026, 3, 1, 11, 30, tzinfo=timezone.utc),
                    detected_by_id=stefan.id,
                    oos_type=OOSType.OOS.value,
                    risk_level=OOSRiskLevel.HIGH.value,
                    batch_id="PP-BATCH-2026-C3",
                    sample_id="PP-SMP-2026-0041",
                    material_code="CF-WR-001",
                    material_name_en="Cannabis Flower — Amnesia Haze",
                    material_name_mk="Канабис цвет — Амнезија",
                    test_name="Pesticide Residues — Total",
                    method_ref="Ph.Eur. 2.8.18",
                    specification_value="<= 0.01 mg/kg",
                    obtained_value="0.034 mg/kg",
                    phase="II",
                    status=OOSStatus.PHASE_II.value,
                    timeline_deadline=datetime(2026, 3, 21, 17, 0, tzinfo=timezone.utc),
                    root_cause_category="ENVIRONMENT",
                    root_cause_description=(
                        "Pesticide residue control — Flower Room 1 ventilation"
                    ),
                    impact_assessment=(
                        "Single batch affected; adjacent rooms screened negative."
                    ),
                    capa_reference="CAPA-2026-003",
                    effectiveness_check_date=datetime(2026, 4, 30, 17, 0, tzinfo=timezone.utc),
                    phase_ii_completed_by_id=elena.id,
                ),
                "oos:PP-OOS-2026-003",
            )

        # ── Audit entries ───────────────────────────────────────────────────
        existing_audit = (
            await session.execute(select(AuditEntry).limit(1))
        ).scalar_one_or_none()
        if existing_audit is None:
            audit_rows = [
                ("CREATE", "sample", "PP-SMP-2026-0036", stefan, None),
                ("CREATE", "sample", "PP-SMP-2026-0037", stefan, None),
                ("CREATE", "specification", "PP-SPEC-2026-0001", elena, "ACTIVE"),
                ("CREATE", "coa", "PP-COA-2026-0018", stefan, "DRAFT"),
                ("APPROVE", "coa", "PP-COA-2026-0018", jana, "APPROVED"),
                ("CREATE", "oos", "PP-OOS-2026-003", stefan, "PHASE_II"),
                ("VIEW", "audit", "AUDIT-TRAIL", sofija, None),
                ("UPDATE", "sample", "PP-SMP-2026-0040", elena, "REJECTED"),
            ]
            for i, (action, rtype, rident, actor, newval) in enumerate(audit_rows):
                session.add(
                    AuditEntry(
                        timestamp=datetime(2026, 3, 2, 8, i, tzinfo=timezone.utc),
                        user_id=actor.id,
                        user_full_name=actor.full_name,
                        action=action,
                        record_type=rtype,
                        record_id=rident,
                        record_identifier=rident,
                        new_value=newval,
                        ip_address="127.0.0.1",
                        session_id="seed",
                    )
                )
            await session.flush()
            _created.append(f"audit_entries:{len(audit_rows)}")
        else:
            _skipped.append("audit_entries")

        # ── Sampling Requests (RQS) ─────────────────────────────────────────
        rqs_specs = [
            ("PP-RQS-2026-0021", "PP-MC-001", "Cannabis Flower (Flower Room 3)",
             "Канабис цвет (Соба 3)", "PP-FP-2026-004", "Production", stefan,
             datetime(2026, 6, 1, 8, 30, tzinfo=timezone.utc), "SP_06",
             RQSStatus.IN_PROGRESS, elena),
            ("PP-RQS-2026-0020", "PP-MC-WTR", "Purified Water — Loop A",
             "Прочистена вода — Јамка А", None, "Engineering", stefan,
             datetime(2026, 5, 31, 14, 0, tzinfo=timezone.utc), "SP_03",
             RQSStatus.COMPLETED, elena),
            ("PP-RQS-2026-0019", "PP-MC-001", "Cannabis Flower (IPC drying)",
             "Канабис цвет (МПК сушење)", "PP-IPC-2026-013", "Production", stefan,
             datetime(2026, 6, 1, 10, 15, tzinfo=timezone.utc), "SP_07",
             RQSStatus.OPEN, None),
        ]
        for (rid, mcode, en, mk, batch, dept, req_by, req_at, sp,
             rstatus, reg_by) in rqs_specs:
            await _get_or_create(
                session,
                SamplingRequest,
                SamplingRequest.rqs_id == rid,
                lambda rid=rid, mcode=mcode, en=en, mk=mk, batch=batch, dept=dept,
                req_by=req_by, req_at=req_at, sp=sp, rstatus=rstatus,
                reg_by=reg_by: SamplingRequest(
                    rqs_id=rid,
                    material_code=mcode,
                    material_name_en=en,
                    material_name_mk=mk,
                    batch_id=batch,
                    originating_department=dept,
                    requested_by_id=req_by.id,
                    requested_at=req_at,
                    assigned_sp_type=sp,
                    status=rstatus.value,
                    registered_by_id=reg_by.id if reg_by is not None else None,
                    registered_at=req_at if reg_by is not None else None,
                    registration_deadline=req_at + timedelta(hours=24),
                ),
                f"sampling_request:{rid}",
            )

        # ── Chain of Custody / Transport ────────────────────────────────────
        # Generic custody-transfer log rows backing the Transport screen.
        # Use the seeded samples as the custody subjects.
        cust_sample = (
            await session.execute(
                select(Sample).where(Sample.sample_id == "PP-SMP-2026-0036")
            )
        ).unique().scalar_one_or_none()
        cust_sample2 = (
            await session.execute(
                select(Sample).where(Sample.sample_id == "PP-SMP-2026-0038")
            )
        ).unique().scalar_one_or_none()
        custody_specs = [
            ("PP-SFR-2026-0042", cust_sample, "QC Lab - Cabinet A",
             "External Lab Intake", datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc),
             "FIELD_TO_LAB"),
            ("PP-SFR-2026-0041", cust_sample2, "Packaging Hall",
             "QC Lab - Cabinet B", datetime(2026, 5, 22, 13, 30, tzinfo=timezone.utc),
             "LAB_INTERNAL"),
        ]
        for sfr_id, smp, from_loc, to_loc, when, ttype in custody_specs:
            if smp is None:
                continue
            await _get_or_create(
                session,
                ChainOfCustody,
                ChainOfCustody.sfr_id == sfr_id,
                lambda sfr_id=sfr_id, smp=smp, from_loc=from_loc, to_loc=to_loc,
                when=when, ttype=ttype: ChainOfCustody(
                    sample_id=smp.id,
                    from_user_id=stefan.id,
                    to_user_id=elena.id,
                    transferred_at=when,
                    from_location=from_loc,
                    to_location=to_loc,
                    transfer_reason="Testing",
                    sfr_id=sfr_id,
                    transfer_type=ttype,
                ),
                f"custody:{sfr_id}",
            )

        # ── Sample Transports (external-lab chain of custody, PP-QC-SOP-012) ──
        # transport_id, sample_id, batch_id, lab, tests, status,
        # (sar, moia, tmcoc, coo, fin), created, shipped, expected, tracking
        transport_specs = [
            ("TR-PP-2026-0042", "PP-SMP-2026-0041", "PP-FP-2026-003", "ukim",
             ["THC", "CBD"], "in_transit", (True, True, True, True, False),
             date(2026, 5, 22), date(2026, 5, 23), date(2026, 5, 26), "PP-COURIER-44193"),
            ("TR-PP-2026-0041", "PP-SMP-2026-0039", "PP-FP-2026-001", "agilent",
             ["Pesticides", "Heavy metals"], "received", (True, False, True, True, True),
             date(2026, 5, 15), date(2026, 5, 15), date(2026, 5, 20), "PP-COURIER-44188"),
            ("TR-PP-2026-0040", "PP-SMP-2026-0038", "PP-FP-2025-048", "phytolab",
             ["Full panel"], "draft", (False, False, False, False, False),
             date(2026, 5, 20), None, None, ""),
        ]
        for tid, sid, bid, lab, tests, status, forms, created, shipped, expected, tracking in transport_specs:
            sar, moia, tmcoc, coo, fin = forms
            await _get_or_create(
                session,
                SampleTransport,
                SampleTransport.transport_id == tid,
                lambda tid=tid, sid=sid, bid=bid, lab=lab, tests=tests, status=status,
                sar=sar, moia=moia, tmcoc=tmcoc, coo=coo, fin=fin,
                created=created, shipped=shipped, expected=expected, tracking=tracking: SampleTransport(
                    transport_id=tid,
                    sample_id=sid,
                    batch_id=bid,
                    external_lab=lab,
                    tests=tests,
                    status=status,
                    form_sar=sar,
                    form_moia=moia,
                    form_tmcoc=tmcoc,
                    form_coo=coo,
                    form_fin=fin,
                    created_date=created,
                    shipped_date=shipped,
                    expected_date=expected,
                    tracking=tracking,
                ),
                f"transport:{tid}",
            )

        # ── Water Quality Test results ──────────────────────────────────────
        water_specs = [
            ("WT-TW_T161_001-2026-01-15", date(2026, 1, 15), "TW_T161_001", "TW",
             {"pH": "7.4", "Conductivity": "320", "TAMC": "<10", "E.coli": "Absent"},
             True, None),
            ("WT-RO_F97_001-2026-03-15", date(2026, 3, 15), "RO_F97_001", "RO",
             {"Conductivity": "2.2", "TOC": "140", "TAMC": "15", "Endotoxin": "<0.1"},
             True, None),
            ("WT-RO_F97_001-2026-05-15", date(2026, 5, 15), "RO_F97_001", "RO",
             {"Conductivity": "6.4", "TOC": "180", "TAMC": "<10", "Endotoxin": "<0.1"},
             False, "Conductivity 6.4 > spec 5.1"),
        ]
        for wid, wdate, loc, grade, params, passed, ooe in water_specs:
            await _get_or_create(
                session,
                WaterTest,
                WaterTest.water_test_id == wid,
                lambda wid=wid, wdate=wdate, loc=loc, grade=grade, params=params,
                passed=passed, ooe=ooe: WaterTest(
                    water_test_id=wid,
                    result_date=wdate,
                    location=loc,
                    grade=grade,
                    parameters=params,
                    passed=passed,
                    ooe=ooe,
                ),
                f"water_test:{wid}",
            )

        # ── Stability studies ───────────────────────────────────────────────
        stab_specs = [
            ("LT-2026-001", "LT", "TD1-DF400", "Gorilla Glue — Dried Cannabis Flower",
             "Горила Глу — Сушен канабис цвет", ["GG1024", "GG1024_02", "GG0824"],
             date(2026, 1, 15), "IN_PROGRESS", "QCSOP 018-A01", "QCSOP 018-A07",
             None, None),
            ("ACC-2026-001", "ACC", "TD1-DF400", "Gorilla Glue — Dried Cannabis Flower",
             "Горила Глу — Сушен канабис цвет", ["GG1024", "GG1024_02", "GG0824"],
             date(2026, 1, 15), "IN_PROGRESS", "QCSOP 018-A02", "QCSOP 018-A07",
             None, None),
            ("LT-2025-003", "LT", "TD1-DF400", "Blue Gelato — Dried Cannabis Flower",
             "Блу Желато — Сушен канабис цвет", ["BG1024", "BG0824", "BG0624"],
             date(2025, 6, 1), "IN_PROGRESS", "QCSOP 018-A01", "QCSOP 018-A07",
             None, None),
            ("LT-2024-002", "LT", "TD1-DF400", "Grape Pie — Dried Cannabis Flower",
             "Грејп Пај — Сушен канабис цвет", ["GP0824", "GP0624", "GP0424"],
             date(2024, 9, 1), "CLOSED", "QCSOP 018-A01", "QCSOP 018-A07",
             "QCSOP 018-A04", "18 months (assigned)"),
        ]
        for (sid, stype, mcode, en, mk, batches, started, sstatus, proto,
             sched, report, shelf) in stab_specs:
            await _get_or_create(
                session,
                StabilityStudy,
                StabilityStudy.study_id == sid,
                lambda sid=sid, stype=stype, mcode=mcode, en=en, mk=mk,
                batches=batches, started=started, sstatus=sstatus, proto=proto,
                sched=sched, report=report, shelf=shelf: StabilityStudy(
                    study_id=sid,
                    study_type=stype,
                    material_code=mcode,
                    material_name_en=en,
                    material_name_mk=mk,
                    batches=batches,
                    started=started,
                    status=sstatus,
                    protocol=proto,
                    schedule=sched,
                    report=report,
                    shelf_life=shelf,
                ),
                f"stability_study:{sid}",
            )

        await session.commit()

    await engine.dispose()

    print("\n=== QC LIMS seed summary ===")
    print(f"Created ({len(_created)}):")
    for c in _created:
        print(f"  + {c}")
    print(f"Skipped/existing ({len(_skipped)}):")
    for s in _skipped:
        print(f"  = {s}")
    print(
        "\nScreen data seeded: sampling_requests (RQS), chain_of_custody "
        "(Transport), water_tests (Water), stability_studies (Stability). "
        "CAPA is derived live from the seeded OOS (root-cause/CAPA fields set)."
    )
    print(f"\nAll demo users share password: {PASSWORD}")
    print("Login emails: elena@, stefan@, jana@, sofija@, admin@purelyplant.eu")


if __name__ == "__main__":
    asyncio.run(seed())
