from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, AwareDatetime, ConfigDict

class AlertInput(BaseModel):
    hazard: Literal['flash_flood','cyclone','earthquake','el_nino_extreme_rain']
    center_lat: float = Field(ge=-90,le=90)
    center_lon: float = Field(ge=-180,le=180)
    radius_m: float = Field(gt=0,le=100000)
    event_time: AwareDatetime
    magnitude: float | None = Field(default=None,ge=0,le=10)
    message: str = Field(default='',max_length=2000)
    phones: list[str] = Field(default_factory=list,max_length=100)

class DispatchInput(BaseModel):
    eta_scale: float = Field(default=1,ge=.5,le=3)
    horizon_min: int | None = Field(default=None,ge=1,le=1440)

class TeamInput(BaseModel):
    id: str = Field(min_length=1,max_length=80,pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=1,max_length=100)
    type: Literal['boat','rescue_4x4','heavy_usar','light_crew']
    base_lat: float = Field(ge=-90,le=90)
    base_lon: float = Field(ge=-180,le=180)
    available: bool = True
    swiftwater_trained: bool = False

class FieldUpdate(BaseModel):
    team_id: str
    status: Literal['en_route','on_scene','escalate','resolved'] | None = None
    depth_cm: float | None = Field(default=None,ge=0,le=1000)
    count: int | None = Field(default=None,ge=0,le=10000)
    note: str = Field(default='',max_length=2000)
