from pydantic import BaseModel, Field, model_validator

from app.models.enums import HazardType


class HazardReportCreate(BaseModel):
    lat: float = Field(..., ge=42.62, le=42.73, description="Sofia bounding box")
    lon: float = Field(..., ge=23.23, le=23.42, description="Sofia bounding box")
    type: HazardType
    severity: int = Field(..., ge=1, le=10, description="1=negligible, 10=emergency")
    description: str | None = Field(
        None,
        max_length=500,
        description="Required when type=OTHER. Optional for all others.",
    )

    @model_validator(mode="after")
    def description_required_for_other(self) -> "HazardReportCreate":
        if self.type == HazardType.OTHER and not self.description:
            raise ValueError("description is required when hazard type is OTHER")
        return self
