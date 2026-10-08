from typing import Literal
from pydantic import BaseModel, Field, AwareDatetime


class AlertInput(BaseModel):
    hazard: Literal['flash_flood','cyclone','earthquake','el_nino_extreme_rain']
    center_lat: float = Field(ge=-90,le=90)
    center_lon: float = Field(ge=-180,le=180)
    radius_m: float = Field(gt=0,le=100000)
    event_time: AwareDatetime
    magnitude: float | None = Field(default=None,ge=0,le=10)
    message: str = Field(default='',max_length=2000)
    phones: list[str] = Field(default_factory=list,max_length=100)
    recipient_source: Literal['manual','locality'] = 'manual'


class AreaInput(BaseModel):
    center_lat: float = Field(ge=-90,le=90)
    center_lon: float = Field(ge=-180,le=180)
    radius_m: float = Field(gt=0,le=100000)


class ResidentInput(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    phone: str = Field(pattern=r'^(\+[1-9][0-9]{7,14}|demo-[a-zA-Z0-9-]+)$',max_length=40)
    lat: float = Field(ge=-90,le=90)
    lon: float = Field(ge=-180,le=180)
    consent: bool
