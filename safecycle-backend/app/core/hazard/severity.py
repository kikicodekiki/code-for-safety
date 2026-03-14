"""
Severity-to-penalty mapping for the 1–10 hazard severity scale.
Single source of truth for how user reports affect routing edge weights.
"""
from dataclasses import dataclass

from app.models.enums import HazardType


@dataclass(frozen=True)
class SeverityPenalty:
    additive: float    # Added directly to the edge's safe_weight
    multiplier: float  # Multiplied against the edge's base weight
    exclude: bool      # If True, edge weight is set to float("inf")


# fmt: off
SEVERITY_PENALTY_MAP: dict[tuple[HazardType, int], SeverityPenalty] = {
    # POTHOLE — surface damage, additive weight penalty
    (HazardType.POTHOLE,  1): SeverityPenalty(additive=0.10, multiplier=1.00, exclude=False),
    (HazardType.POTHOLE,  2): SeverityPenalty(additive=0.30, multiplier=1.00, exclude=False),
    (HazardType.POTHOLE,  3): SeverityPenalty(additive=0.55, multiplier=1.05, exclude=False),
    (HazardType.POTHOLE,  4): SeverityPenalty(additive=0.80, multiplier=1.10, exclude=False),
    (HazardType.POTHOLE,  5): SeverityPenalty(additive=1.15, multiplier=1.20, exclude=False),
    (HazardType.POTHOLE,  6): SeverityPenalty(additive=1.50, multiplier=1.30, exclude=False),
    (HazardType.POTHOLE,  7): SeverityPenalty(additive=2.00, multiplier=1.45, exclude=False),
    (HazardType.POTHOLE,  8): SeverityPenalty(additive=2.50, multiplier=1.60, exclude=False),
    (HazardType.POTHOLE,  9): SeverityPenalty(additive=3.25, multiplier=1.80, exclude=False),
    (HazardType.POTHOLE, 10): SeverityPenalty(additive=4.00, multiplier=2.00, exclude=False),

    # OBSTACLE — physical blockage, high penalty at high severity
    (HazardType.OBSTACLE,  1): SeverityPenalty(additive=0.20, multiplier=1.05, exclude=False),
    (HazardType.OBSTACLE,  2): SeverityPenalty(additive=0.50, multiplier=1.10, exclude=False),
    (HazardType.OBSTACLE,  3): SeverityPenalty(additive=0.85, multiplier=1.20, exclude=False),
    (HazardType.OBSTACLE,  4): SeverityPenalty(additive=1.20, multiplier=1.30, exclude=False),
    (HazardType.OBSTACLE,  5): SeverityPenalty(additive=1.85, multiplier=1.40, exclude=False),
    (HazardType.OBSTACLE,  6): SeverityPenalty(additive=2.50, multiplier=1.50, exclude=False),
    (HazardType.OBSTACLE,  7): SeverityPenalty(additive=3.75, multiplier=2.00, exclude=False),
    (HazardType.OBSTACLE,  8): SeverityPenalty(additive=5.00, multiplier=2.50, exclude=False),
    (HazardType.OBSTACLE,  9): SeverityPenalty(additive=7.50, multiplier=3.25, exclude=False),
    (HazardType.OBSTACLE, 10): SeverityPenalty(additive=10.0, multiplier=4.00, exclude=False),

    # DANGEROUS_TRAFFIC — downgrade highway type equivalent
    (HazardType.DANGEROUS_TRAFFIC,  1): SeverityPenalty(additive=0.15, multiplier=1.05, exclude=False),
    (HazardType.DANGEROUS_TRAFFIC,  2): SeverityPenalty(additive=0.40, multiplier=1.10, exclude=False),
    (HazardType.DANGEROUS_TRAFFIC,  3): SeverityPenalty(additive=0.70, multiplier=1.20, exclude=False),
    (HazardType.DANGEROUS_TRAFFIC,  4): SeverityPenalty(additive=1.00, multiplier=1.30, exclude=False),
    (HazardType.DANGEROUS_TRAFFIC,  5): SeverityPenalty(additive=1.50, multiplier=1.45, exclude=False),
    (HazardType.DANGEROUS_TRAFFIC,  6): SeverityPenalty(additive=2.00, multiplier=1.60, exclude=False),
    (HazardType.DANGEROUS_TRAFFIC,  7): SeverityPenalty(additive=2.75, multiplier=1.80, exclude=False),
    (HazardType.DANGEROUS_TRAFFIC,  8): SeverityPenalty(additive=3.50, multiplier=2.00, exclude=False),
    (HazardType.DANGEROUS_TRAFFIC,  9): SeverityPenalty(additive=4.75, multiplier=2.50, exclude=False),
    (HazardType.DANGEROUS_TRAFFIC, 10): SeverityPenalty(additive=6.00, multiplier=3.00, exclude=False),

    # ROAD_CLOSED — partial or full exclusion (severity ≥ 6 → exclude)
    (HazardType.ROAD_CLOSED,  1): SeverityPenalty(additive=1.00, multiplier=1.20, exclude=False),
    (HazardType.ROAD_CLOSED,  2): SeverityPenalty(additive=2.00, multiplier=1.50, exclude=False),
    (HazardType.ROAD_CLOSED,  3): SeverityPenalty(additive=3.00, multiplier=2.00, exclude=False),
    (HazardType.ROAD_CLOSED,  4): SeverityPenalty(additive=5.00, multiplier=2.50, exclude=False),
    (HazardType.ROAD_CLOSED,  5): SeverityPenalty(additive=8.00, multiplier=3.00, exclude=False),
    (HazardType.ROAD_CLOSED,  6): SeverityPenalty(additive=15.0, multiplier=5.00, exclude=True),
    (HazardType.ROAD_CLOSED,  7): SeverityPenalty(additive=15.0, multiplier=5.00, exclude=True),
    (HazardType.ROAD_CLOSED,  8): SeverityPenalty(additive=15.0, multiplier=5.00, exclude=True),
    (HazardType.ROAD_CLOSED,  9): SeverityPenalty(additive=15.0, multiplier=5.00, exclude=True),
    (HazardType.ROAD_CLOSED, 10): SeverityPenalty(additive=15.0, multiplier=5.00, exclude=True),

    # WET_SURFACE — slippery conditions, surface-style penalty
    (HazardType.WET_SURFACE,  1): SeverityPenalty(additive=0.08, multiplier=1.02, exclude=False),
    (HazardType.WET_SURFACE,  2): SeverityPenalty(additive=0.20, multiplier=1.05, exclude=False),
    (HazardType.WET_SURFACE,  3): SeverityPenalty(additive=0.40, multiplier=1.10, exclude=False),
    (HazardType.WET_SURFACE,  4): SeverityPenalty(additive=0.60, multiplier=1.15, exclude=False),
    (HazardType.WET_SURFACE,  5): SeverityPenalty(additive=0.90, multiplier=1.22, exclude=False),
    (HazardType.WET_SURFACE,  6): SeverityPenalty(additive=1.20, multiplier=1.30, exclude=False),
    (HazardType.WET_SURFACE,  7): SeverityPenalty(additive=1.60, multiplier=1.40, exclude=False),
    (HazardType.WET_SURFACE,  8): SeverityPenalty(additive=2.00, multiplier=1.50, exclude=False),
    (HazardType.WET_SURFACE,  9): SeverityPenalty(additive=2.75, multiplier=1.65, exclude=False),
    (HazardType.WET_SURFACE, 10): SeverityPenalty(additive=3.50, multiplier=1.80, exclude=False),

    # OTHER — conservative generic penalty
    (HazardType.OTHER,  1): SeverityPenalty(additive=0.15, multiplier=1.05, exclude=False),
    (HazardType.OTHER,  2): SeverityPenalty(additive=0.35, multiplier=1.10, exclude=False),
    (HazardType.OTHER,  3): SeverityPenalty(additive=0.65, multiplier=1.15, exclude=False),
    (HazardType.OTHER,  4): SeverityPenalty(additive=1.00, multiplier=1.20, exclude=False),
    (HazardType.OTHER,  5): SeverityPenalty(additive=1.50, multiplier=1.30, exclude=False),
    (HazardType.OTHER,  6): SeverityPenalty(additive=2.00, multiplier=1.40, exclude=False),
    (HazardType.OTHER,  7): SeverityPenalty(additive=2.75, multiplier=1.55, exclude=False),
    (HazardType.OTHER,  8): SeverityPenalty(additive=3.50, multiplier=1.70, exclude=False),
    (HazardType.OTHER,  9): SeverityPenalty(additive=4.25, multiplier=1.95, exclude=False),
    (HazardType.OTHER, 10): SeverityPenalty(additive=5.00, multiplier=2.20, exclude=False),
}
# fmt: on


def apply_severity_penalty(base_weight: float, penalty: SeverityPenalty) -> float:
    """Compute the penalised edge weight. Returns inf if penalty.exclude is True."""
    if penalty.exclude:
        return float("inf")
    return (base_weight * penalty.multiplier) + penalty.additive
