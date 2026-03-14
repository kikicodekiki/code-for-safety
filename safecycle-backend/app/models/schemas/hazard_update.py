from typing import Literal

from pydantic import BaseModel, Field


class HazardConfirmationCreate(BaseModel):
    lat: float = Field(..., description="Confirmer's current GPS latitude")
    lon: float = Field(..., description="Confirmer's current GPS longitude")
    action: Literal["confirm", "dismiss"]
