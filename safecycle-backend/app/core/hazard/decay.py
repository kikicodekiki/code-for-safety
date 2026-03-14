"""
Temporal decay for hazard reports.

All penalties decay linearly from 1.0 (fresh) to 0.0 (expired).
Different hazard types have different horizons because physical
conditions persist for different lengths of time.
"""
from app.models.enums import HazardType

# Hours until a report's penalty reaches 0.0
DECAY_HORIZON: dict[HazardType, float] = {
    HazardType.ROAD_CLOSED:        24.0,   # closures last longer
    HazardType.OBSTACLE:           12.0,
    HazardType.POTHOLE:           168.0,   # physical damage persists (7 days)
    HazardType.DANGEROUS_TRAFFIC:   4.0,   # traffic conditions change quickly
    HazardType.WET_SURFACE:         6.0,   # surfaces dry
    HazardType.OTHER:              10.0,
}

# Redis TTL: longest possible horizon so nothing expires in cache before Postgres
MAX_DECAY_HORIZON_HOURS: float = max(DECAY_HORIZON.values())  # 168h


def decay_factor(age_hours: float, hazard_type: HazardType) -> float:
    """
    Returns a multiplier in [0.0, 1.0] applied to the effective penalty.
    At age 0h → 1.0 (full penalty). At or beyond horizon → 0.0 (no effect).
    """
    horizon = DECAY_HORIZON[hazard_type]
    return max(0.0, 1.0 - (age_hours / horizon))
