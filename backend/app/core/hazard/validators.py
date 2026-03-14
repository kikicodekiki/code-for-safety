"""
Type-specific validation rules for hazard reports.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.models.enums import HazardType

logger = logging.getLogger(__name__)


class HazardValidationError(ValueError):
    def __init__(self, field_name: str, message: str) -> None:
        self.field_name = field_name
        self.message = message
        super().__init__(f"{field_name}: {message}")


@dataclass
class ValidationResult:
    requires_immediate_broadcast: bool = False
    affects_routing_immediately: bool = False
    warnings: list[str] = field(default_factory=list)


def validate_hazard_report(
    hazard_type: HazardType,
    severity: int,
    description: str | None,
) -> ValidationResult:
    """
    Applies type-specific business rules beyond basic field validation.
    Raises HazardValidationError on hard failures.
    Returns ValidationResult with broadcast/routing flags for soft rules.
    """
    if not (1 <= severity <= 10):
        raise HazardValidationError("severity", "Must be an integer between 1 and 10.")

    result = ValidationResult()

    # Hard rule: OTHER always requires a description
    if hazard_type == HazardType.OTHER and not (description and description.strip()):
        raise HazardValidationError(
            "description", "Description is required when hazard type is OTHER."
        )

    # Soft rule: ROAD_CLOSED severity 1–2 with language implying full blockage
    if hazard_type == HazardType.ROAD_CLOSED and severity <= 2 and description:
        full_blockage_keywords = ("completely", "fully", "impassable", "blocked", "closed")
        if any(kw in description.lower() for kw in full_blockage_keywords):
            result.warnings.append(
                "Severity 1–2 indicates partial closure, but description suggests full blockage. "
                "Consider raising severity."
            )
            logger.warning(
                "ROAD_CLOSED report severity=%d has description suggesting full blockage: %r",
                severity,
                description,
            )

    # Routing exclusion: ROAD_CLOSED severity ≥ 6
    if hazard_type == HazardType.ROAD_CLOSED and severity >= 6:
        result.requires_immediate_broadcast = True
        result.affects_routing_immediately = True

    # Immediate broadcast: OBSTACLE severity ≥ 8 (very high danger)
    elif hazard_type == HazardType.OBSTACLE and severity >= 8:
        result.requires_immediate_broadcast = True

    # Immediate broadcast: WET_SURFACE severity ≥ 9 (flooding risk)
    elif hazard_type == HazardType.WET_SURFACE and severity >= 9:
        result.requires_immediate_broadcast = True

    # Immediate broadcast: DANGEROUS_TRAFFIC severity 10 (life-threatening)
    elif hazard_type == HazardType.DANGEROUS_TRAFFIC and severity == 10:
        result.requires_immediate_broadcast = True

    return result
