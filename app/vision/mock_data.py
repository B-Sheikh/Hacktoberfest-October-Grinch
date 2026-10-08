"""Canned perception, never a claim about uploaded photo contents."""
from copy import deepcopy
from .schemas import FloodExtraction

FLOOD = dict(scene_type='flood', image_usable=True, image_issues=[],
    references=[dict(ref_id='tyre_center_car',waterline_bin='q4',touches_same_ground_as_water=True,confidence=.7)],
    flow_class='moderate',trend='rising_moderate',wet_line_above_water=False,debris='none',
    people=dict(count_visible=1,contexts=['in_vehicle']),vehicles_visible=1,location_type='street',hazards=[])

def mock_extract(filename):
    data = deepcopy(FLOOD)
    if 'receding' in filename.lower():
        data.update(trend='receding',wet_line_above_water=True)
    if 'roof' in filename.lower():
        data['references'][0].update(ref_id='window_sill',waterline_bin='q4')
        data['people']['contexts'] = ['on_roof']
    return FloodExtraction.model_validate(data).model_dump()
