# Waterline implementation plan

Source: the team's supplied Waterline Master Build Specification v1.0, reviewed in full on 8 October 2026. The document defines intended product requirements; it does not establish that a feature has been built, validated, deployed, or used in the field.

## Initial build

- Reference physics from Appendix A, retained unchanged; Appendix B scenario retained with its package import adjusted and print side effects removed.
- Golden tests for intervals, fusion, ensemble bins, robust rates, Bayesian blending, projections, flood hazards, benefit monotonicity, collapse plausibility, mass, illustrative survival, distance, and assignment at ETA ×1 and ×2.
- Editable JSON references, rates, thresholds, vehicle parameters, occupancy priors, survival table, and interface templates.
- SQLite WAL persistence with alerts, recipients, reports, incidents, teams, assignments, and field updates. Structured incident payloads are JSON columns in the initial schema.
- Eleven simulated seed incidents and seven teams; seed resets only the demo alert and its related data.
- Command queue, point-marker map, ETA scale, site card, three depth paths, deadlines, navigation, and assumption labels.
- Main office resident registry and consent, geofence recipient preview, campaign/message review, repeat-safe simulated SMS sending, consent recheck, report counters and shared public reporting links.
- Public civilian portal with locality filtering and reporting without a personal SMS; home page opens the portal.
- Mobile citizen reporting with state, photos, map-selected locations, vulnerability flags, resize, progress, retry, geofence warnings, duplicate detection, and mock flood extraction.
- Dispatch, field team directory, assignment-bound photo uploads, field status/measurements, shared photo and observation history, and benchmark calculations from recorded measurements only.
- Redesigned navigation, summary counts, searchable priority queue, focused site details, resident reporting wizard, image previews and responsive styles. Authority circular-area selection with draggable center and boundary handles, resident map pins and responder photo-location maps are implemented.

## Next milestones

| Requirement | Remaining work |
| --- | --- |
| Perception (§6) | Hosted Gemma flood adapter, three-run ensemble, strict validation, retries, semaphore/backoff, minimal-thinking generation, bounded timeouts and manual review on failure are implemented. Non-flood scenes and unusable/no-reference photos are stored for manual review without ranking. Strict collapse schema and zone extraction remain pending. |
| Metadata (§5) | Read original server-side EXIF time/GPS before resize, preserve original metadata during client resize, validate timestamps and location priorities. Reports currently use submission time and browser or map-selected coordinates. |
| Report analysis (§3, §7) | Real collapse photo processing, zone merging by side, deterministic mass intervals from multiples, note/voice extraction, unknown/unusable/out-of-scope rejection. Collapse calculations currently use explicit seed fixtures. |
| Authority (§3, §10) | Polygon area editing and HMAC token format if needed. Main office campaign/report counters, opted-in resident matching and simulated sending are implemented. Tap-to-select circular areas and draggable center/boundary handles are implemented. Initial opaque tokens are stored server-side, not stateless HMAC tokens. |
| Guidance (§9) | Complete externally reviewed playbook with per-rule source attribution. Initial briefings are deterministic summaries of computed facts and basic safety reminders, not a complete rescue playbook. |
| Citizen UX (§10) | Automatic location request, multilingual text and robust persistent offline queue. Current retry queue lasts only while the tab is open. |
| Dispatch (§8) | Per-capability multi-slot collapse assignments, medical staging, conflict handling for already-active field assignments, explicit fleet equipment limits, alert-scoped dispatch. Current implementation assigns one team per site. |
| Privacy/security (§14) | Operator authentication and roles, token/IP rate limits, report invalidation, deletion endpoint, retention controls, secure upload inspection and deployment review. Use the hosted prototype only for controlled demonstrations until these are implemented. |
| Evidence (§11) | Staged depth/aperture measurements, professional review of assumptions, real-phone HTTPS test, recorded demo, hosted persistence verification and Devpost submission. The public portal is deployed on Render. No accuracy claims yet. |

Optional cut-line items from the spec: LLM paraphrased briefings, manual calibration, real SMS, multilingual UI, OSRM routing. Compound proximity tagging and a basic field page are already present.

## Decisions and uncertainties

- Use the repository root as the project root rather than a nested `waterline/` directory.
- Default the example environment to mock perception and deterministic templates. Live mode uses `gemma-4-26b-a4b-it`, verified in the supplied key's model list; the key is stored only in ignored `.env`. A live full-prompt blank-image classification was checked. The 31B variant timed out on the full prompt during integration, so the available 26B A4B variant was selected. Model access does not establish measurement accuracy.
- Demo coordinates are around Coimbatore; all seeded measurements are simulated. Demo collapse occupancy is an assumption, not a report of an actual incident.
- Retain golden physics unchanged even where prose describes broader production behaviour. The application supplies configurable caps, travel settings and planning horizons explicitly. Several coefficients inside the reference implementation remain fixed; expose them through a tested adapter in a later milestone.
- Team name is October Grinch. Assigned feature owners are Abhishek Bharathi (intelligence), Aadithya Ram (office), Aadidev (citizen) and Sanjay S M (operations). These assignments are responsibilities, not retrospective contribution claims.
- Team-owned project code is licensed under the MIT License; third-party components retain their own terms.
- The illustrative survival curve is a ranking assumption, not an estimate of any person's outcome.

- Standalone `/report/<token>` SMS forms; legacy `/r/<token>` support. Single-admin login now protects office/command/team pages and sensitive APIs, with hashed credentials, revocable expiring sessions, secure-cookie configuration, origin/header checks and failed-login throttling. Public reporting stays accessible without an admin session.

## Feature organization

Application code is organized into `app/office`, `app/citizen`, `app/intelligence` and `app/operations`. Their READMEs describe implemented workflows, endpoint contracts and remaining requirements. The composition root is `app/main.py`; database/configuration/common utilities and browser assets remain shared. All existing HTTP paths and the Uvicorn startup target remain stable.
