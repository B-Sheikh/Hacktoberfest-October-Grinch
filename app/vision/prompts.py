"""Perception contract for the planned live adapter."""
SYSTEM = ('You are a perception module. Output ONLY one JSON object matching the schema. '
          'Never output measurements in cm or metres. Choose ids and bins only from the lists. '
          'If unsure, lower confidence or choose unknown. Do not guess people who are not visible.')
BINS = ('none = no water at the base of the object; q1 = water covers the lower quarter of the span '
        'from ground to the feature; q2 = lower half; q3 = up to three quarters; '
        'q4 = up to or at the feature; over = water is above the feature.')
