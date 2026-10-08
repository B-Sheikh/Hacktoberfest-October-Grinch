"""Perception contract: enums and references only; arithmetic stays in code."""
import json
from ...settings import REFERENCES
from .schemas import FloodExtraction, UnsupportedScene
SYSTEM = ('You are a perception module. Output ONLY one JSON object matching the schema. '
          'Never output measurements in cm or metres. Choose ids and bins only from the lists. '
          'If unsure, lower confidence or choose unknown. Do not guess people who are not visible.')
BINS = ('none = no water at the base of the object; q1 = water covers the lower quarter of the span '
        'from ground to the feature; q2 = lower half; q3 = up to three quarters; '
        'q4 = up to or at the feature; over = water is above the feature.')

def flood_prompt():
    return '\n'.join([
        SYSTEM, BINS,
        'First classify the actual scene. For collapse, damaged_standing, or out_of_scope, '
        'return only {"scene_type": "<classification>"}. Do not fabricate a flood scene.',
        'For flood, follow this schema exactly: '+json.dumps(FloodExtraction.model_json_schema()),
        'Non-flood schema: '+json.dumps(UnsupportedScene.model_json_schema()),
        'Allowed reference landmarks: '+', '.join(REFERENCES['flood']),
        'Use adult person landmarks only. A landmark must stand on the same ground as the water. '
        'If no trustworthy reference is visible, return references=[] and image_issues=["no_reference"]. '
        'Describe only what is visible. Do not include measurements, advice, or Markdown.',
    ])
