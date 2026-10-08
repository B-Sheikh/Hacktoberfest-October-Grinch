from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from ..settings import REFERENCES

class Reference(BaseModel):
    ref_id: str
    waterline_bin: Literal['none','q1','q2','q3','q4','over']
    touches_same_ground_as_water: bool
    confidence: float = Field(ge=0,le=1)
    @field_validator('ref_id')
    @classmethod
    def known_reference(cls, value):
        if value not in REFERENCES['flood']:
            raise ValueError('Unknown reference')
        return value

class People(BaseModel):
    count_visible: int = Field(ge=0)
    contexts: list[Literal['on_roof','in_vehicle','wading','at_window','stranded_ground_floor']]

class FloodExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scene_type: Literal['flood']
    image_usable: bool
    image_issues: list[Literal['dark','blur','no_reference','water_not_visible']]
    references: list[Reference]
    flow_class: Literal['still','slow','moderate','rapid','unknown']
    trend: Literal['receding','steady','rising_slow','rising_moderate','rising_rapid','unknown']
    wet_line_above_water: bool
    debris: Literal['none','some','heavy']
    people: People
    vehicles_visible: int = Field(ge=0)
    location_type: Literal['street','ground_floor_room','underpass','bridge','field','other']
    hazards: list[Literal['live_wire','gas_smell','fire','open_manhole','animals','none']]
