"""
Specification Validation Service for LIMS.

Per P1-E3: Chemotype validation and other spec validation logic.
"""

from dataclasses import dataclass
from typing import Any, Optional

from app.models.specification import Chemotype, THCGrade


@dataclass
class ValidationResult:
    """Outcome of validating a single test result against a spec parameter."""

    complies: bool
    status: str  # "pass" | "alert" | "fail" | "error"
    limit_type: Optional[str]
    spec_parameter_id: Optional[Any]
    spec_parameter_name: Optional[str]
    alert_message: Optional[str]
    result_value: Optional[str]
    spec_limit_display: Optional[str]


def _fmt_limits(lo: Optional[float], hi: Optional[float], unit: Optional[str]) -> str:
    """Human-readable display of a limit range."""
    u = f" {unit}" if unit else ""
    if lo is not None and hi is not None:
        return f"{lo}–{hi}{u}"
    if hi is not None:
        return f"≤ {hi}{u}"
    if lo is not None:
        return f"≥ {lo}{u}"
    return "—"


def validate_result(
    result_value: Optional[str],
    result_numeric: Optional[float],
    spec_parameter: dict,
) -> ValidationResult:
    """
    Validate a single numeric result against a spec parameter's limits.

    Uses release limits as the hard pass/fail boundary and operational limits
    (if present) as an early-warning "alert" band. Non-numeric results that
    cannot be evaluated return status "error".
    """
    pid = spec_parameter.get("id")
    pname = spec_parameter.get("test_name_en")
    unit = spec_parameter.get("unit")
    rel_min = spec_parameter.get("release_limit_min")
    rel_max = spec_parameter.get("release_limit_max")
    op_min = spec_parameter.get("operational_limit_min")
    op_max = spec_parameter.get("operational_limit_max")
    display = _fmt_limits(rel_min, rel_max, unit)

    if result_numeric is None:
        return ValidationResult(
            complies=False,
            status="error",
            limit_type=None,
            spec_parameter_id=pid,
            spec_parameter_name=pname,
            alert_message="Result is not numeric; manual review required.",
            result_value=result_value,
            spec_limit_display=display,
        )

    # Hard release-limit breach -> fail.
    if (rel_min is not None and result_numeric < rel_min) or (
        rel_max is not None and result_numeric > rel_max
    ):
        return ValidationResult(
            complies=False,
            status="fail",
            limit_type="release",
            spec_parameter_id=pid,
            spec_parameter_name=pname,
            alert_message=f"Result {result_numeric} is outside release limits ({display}).",
            result_value=result_value,
            spec_limit_display=display,
        )

    # Within release limits but outside operational band -> alert.
    if (op_min is not None and result_numeric < op_min) or (
        op_max is not None and result_numeric > op_max
    ):
        return ValidationResult(
            complies=True,
            status="alert",
            limit_type="operational",
            spec_parameter_id=pid,
            spec_parameter_name=pname,
            alert_message=f"Result {result_numeric} breached operational alert limit.",
            result_value=result_value,
            spec_limit_display=display,
        )

    return ValidationResult(
        complies=True,
        status="pass",
        limit_type="release",
        spec_parameter_id=pid,
        spec_parameter_name=pname,
        alert_message=None,
        result_value=result_value,
        spec_limit_display=display,
    )


def validate_batch_results(
    results: list[dict],
    spec_parameters: list[dict],
) -> list[ValidationResult]:
    """
    Validate a batch of results against a list of spec parameters.

    Each result is matched to its parameter by ``test_name`` == ``test_name_en``.
    Unmatched results produce an "error" ValidationResult.
    """
    by_name = {p.get("test_name_en"): p for p in spec_parameters}
    out: list[ValidationResult] = []
    for r in results:
        param = by_name.get(r.get("test_name"))
        if param is None:
            out.append(
                ValidationResult(
                    complies=False,
                    status="error",
                    limit_type=None,
                    spec_parameter_id=None,
                    spec_parameter_name=r.get("test_name"),
                    alert_message="No matching specification parameter found.",
                    result_value=r.get("result_value"),
                    spec_limit_display="—",
                )
            )
            continue
        out.append(
            validate_result(
                result_value=r.get("result_value"),
                result_numeric=r.get("result_numeric"),
                spec_parameter=param,
            )
        )
    return out


def validate_chemotype(thc_pct: float, cbd_pct: float) -> Chemotype:
    """
    Validate and determine chemotype from THC and CBD percentages.
    
    Per P1-E3:
    - THC-dominant: THC ≥ 5.0%, CBD ≤ 1.0%
    - Intermediate: THC 1.0-5.0%, CBD ≥ 1.0%, ratio 0.2-5.0
    - CBD-dominant: THC ≤ 1.0%, CBD ≥ 5.0%
    
    Args:
        thc_pct: THC percentage (w/w)
        cbd_pct: CBD percentage (w/w)
    
    Returns:
        Chemotype enum value
    
    Raises:
        ValueError: If percentages don't meet any chemotype criteria
    """
    return Chemotype.validate_from_percentages(thc_pct, cbd_pct)


def assign_thc_grade(thc_pct: float) -> THCGrade:
    """
    Assign THC potency grade from percentage.
    
    Per P1-E1 / PPQCSPECIB001:
    - GRADE_I: 25.0-28.9%
    - GRADE_II: 21.0-24.9%
    - GRADE_III: 17.0-20.9%
    - GRADE_IV: 13.0-16.9%
    - GRADE_V: 5.0-12.9%
    
    Args:
        thc_pct: THC percentage (w/w)
    
    Returns:
        THCGrade enum value
    """
    return THCGrade.from_thc_percentage(thc_pct)


def validate_thc_grade_range(thc_pct: float, expected_grade: THCGrade) -> bool:
    """
    Validate that THC percentage falls within expected grade range.
    
    Args:
        thc_pct: THC percentage (w/w)
        expected_grade: Expected THC grade
    
    Returns:
        True if percentage is within grade range
    """
    actual_grade = THCGrade.from_thc_percentage(thc_pct)
    return actual_grade == expected_grade


def get_thc_grade_range(grade: THCGrade) -> tuple[float, float]:
    """
    Get min/max THC percentage for a given grade.
    
    Args:
        grade: THC grade
    
    Returns:
        Tuple of (min_pct, max_pct)
    """
    ranges = {
        THCGrade.GRADE_I: (25.0, 28.9),
        THCGrade.GRADE_II: (21.0, 24.9),
        THCGrade.GRADE_III: (17.0, 20.9),
        THCGrade.GRADE_IV: (13.0, 16.9),
        THCGrade.GRADE_V: (5.0, 12.9),
    }
    return ranges.get(grade, (0.0, 0.0))
