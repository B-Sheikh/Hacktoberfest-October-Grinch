# Waterline implementation plan

Source: the team's supplied Waterline Master Build Specification v1.0, reviewed in full on 8 October 2026. The document defines intended product requirements; it does not establish that a feature has been built, validated, deployed, or used in the field.

## Initial build

- Reference physics from Appendix A, retained unchanged; Appendix B scenario retained with its package import adjusted and print side effects removed.
- Golden tests for intervals, fusion, ensemble bins, robust rates, Bayesian blending, projections, flood hazards, benefit monotonicity, collapse plausibility, mass, illustrative survival, distance, and assignment at ETA ×1 and ×2.
- Editable JSON references, rates, thresholds, vehicle parameters, occupancy priors, survival table, and interface templates.
- SQLite WAL persistence with alerts, recipients, reports, incidents, teams, assignments, and field updates. Structured incident payloads are JSON columns in the initial schema.
- Eleven simulated seed incidents and seven teams; seed resets only the demo alert and its related data.
- Command queue, point-marker map, ETA scale, site card, three depth paths, deadlines, navigation, and assumption labels.
- Simulated SMS outbox with random opaque reporting tokens tied to alert records.
- Mobile citizen reporting with state, photos, coordinates, vulnerability flags, resize, progress, retry, geofence warnings, duplicate detection, and mock flood extraction.
- Dispatch, field status and measurements, and benchmark calculations from recorded measurements only.

## Next milestones

| Requirement | Remaining work |
| --- | --- |
| Perception (§6) | Live google-genai adapter, strict collapse schema, three-run flood ensemble, validation retries, semaphore/backoff, and visible failure fallback. The initial adapter always returns mock flood extraction, regardless of filename. |
| Metadata (§5) | Read original server-side EXIF time/GPS before resize, preserve original metadata during client resize, validate timestamps and location priorities. Initial reports use submission time and browser/entered coordinates. |
| Report analysis (§3, §7) | Real collapse photo processing, zone merging by side, deterministic mass intervals from multiples, note/voice extraction, unknown/unusable/out-of-scope rejection. Collapse calculations currently use explicit seed fixtures. |
| Authority (§3, §10) | Map pin and radius editor, counters, HMAC token format if needed. Initial opaque tokens are stored server-side, not stateless HMAC tokens. |
| Guidance (§9) | Complete externally reviewed playbook with per-rule source attribution. Initial briefings are deterministic summaries of computed facts and basic safety reminders, not a complete rescue playbook. |
| Citizen UX (§10) | Tap-to-pin map, automatic location request, multilingual text and robust persistent offline queue. Current retry queue lasts only while the tab is open. |
| Dispatch (§8) | Per-capability multi-slot collapse assignments, medical staging, conflict handling for already-active field assignments, explicit fleet equipment limits, alert-scoped dispatch. Current implementation assigns one team per site. |
| Privacy/security (§14) | Operator authentication and roles, token/IP rate limits, report invalidation, deletion endpoint, retention controls, secure upload inspection and deployment review. Local demo only until these are implemented. |
| Evidence (§11) | Staged depth/aperture measurements, professional review of assumptions, real-phone HTTPS test, recorded demo, live deployment and Devpost submission. No accuracy claims yet. |

Optional cut-line items from the spec: LLM paraphrased briefings, manual calibration, real SMS, multilingual UI, OSRM routing. Compound proximity tagging and a basic field page are already present.

## Decisions and uncertainties

- Use the repository root as the project root rather than a nested `waterline/` directory.
- Default to mock perception and deterministic templates; do not assume the spec's example model ID is available. A live model identifier remains unset.
- Demo coordinates are around Coimbatore; all seeded measurements are simulated. Demo collapse occupancy is an assumption, not a report of an actual incident.
- Retain golden physics unchanged even where prose describes broader production behaviour. The application supplies configurable caps, travel settings and planning horizons explicitly. Several coefficients inside the reference implementation remain fixed; expose them through a tested adapter in a later milestone.
- Do not assign personal contribution claims or a team name without team confirmation.
- No new project license is selected by this initial build. Team license decision is pending.
- The illustrative survival curve is a ranking assumption, not an estimate of any person's outcome.
