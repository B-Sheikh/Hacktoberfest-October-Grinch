# AI perception and hazard calculations

**Development owner: Abhishek Bharathi.** This assigns future maintenance and delivery responsibility without claiming individual authorship of existing work.

This feature converts observations into numerical planning estimates while separating model perception from deterministic mathematics. It owns validated Gemma flood extraction, explicit mock mode, landmark intervals, rate fitting/fusion, projection scenarios, flood hazard measures and collapse reference calculations.

## Code

| File or directory | Responsibility |
| --- | --- |
| `physics.py` | Spec Appendix A reference formulas for landmark bins, intervals, rates, flood hazards, arrival benefits, apertures, mass, illustrative time decay and travel distance |
| `fusion.py` | Incident recomputation, recent evidence fusion, Bayesian rate blending, depth scenarios, deadlines, relative priority and advisory collapse zone scores |
| `vision/client.py` | Hosted Gemma calls, three-run flood ensemble, validation retries, concurrency limits, timeouts and failed-call/manual-review status |
| `vision/schemas.py` | Strict allowed flood reference IDs, bins, scene and hazard enums; non-flood classification contract |
| `vision/prompts.py` | Perception-only prompts and schema/landmark vocabulary |
| `vision/mock_data.py` | Explicit canned offline perception |
| `routes.py` | Public configuration and health, plus authenticated benchmark results |

Editable assumptions remain centralized under [`../config/`](../config/): references, rates, thresholds, occupancy, survival, teams, templates and vision parameters. The shared command frontend displays this feature's outputs; it does not reimplement the physics.

## Processing contract

1. The citizen feature supplies resized JPEGs. With `VISION_PROVIDER=gemini` and a server-side key, the configured Gemma model chooses allowed reference IDs, bins and enums. It never supplies physical lengths or rescue procedures.
2. Flood extraction runs three times per image. JSON and enums are validated; retry, semaphore and time limits are configurable. Disagreement widens bin intervals or triggers review when no common valid landmark exists.
3. Code converts ground-to-landmark spans into intervals. It preserves inconsistent and open-ended flags instead of hiding them behind an exact-looking number.
4. Incident fusion uses observation timestamps, interval widths and a rate-class prior. Best/expected/worst depth paths are planning assumptions rather than hydrodynamic forecasts.
5. Hazard-at-arrival feeds headline priority. Decreasing arrival-benefit formulas feed the operations optimizer, preventing later arrival from being rewarded merely because severity rises.
6. The collapse reference module computes aperture plausibility, mass/crew and an illustrative time-decay curve for seeded scenes. Live collapse zone extraction is not yet implemented.

Actual receipt/site statuses distinguish `ok`, `retry_ok`, `mock`, `failed` and `manual_review`. Explicit mock mode supplies simulated measurements; failure in live mode stores evidence for manual review without injecting mock measurements. Configured live health is not proof that the latest inference succeeded.

## Model and credentials

The configured default is `gemma-4-26b-a4b-it`, accessed through google-genai and Google's Gemini API. The earlier 31B full-prompt test timed out; the available 26B A4B model was selected during integration. Local `GEMINI_API_KEY`, provider and model settings belong in ignored `.env`; `.env.example` contains no credentials. Hosted access and professional measurement accuracy are separate questions.

## Verification and limits

Run `python -m pytest tests/test_physics.py tests/test_vision.py -q`. Golden tests cover reference intervals, inconsistent/open-ended fusion, ensemble bins, rate uncertainty/blending, projections, hazard floors, monotone arrival benefits, void fit, mass, illustrative decay and distance. Mocked SDK tests cover live contracts and failure handling. Ground-truth measurements produce benchmark values at `/api/benchmark`; no measurements means no accuracy metric. Real-photo accuracy, local landmark validation, live collapse extraction and professional review of rate/occupancy/vehicle assumptions remain outstanding.
