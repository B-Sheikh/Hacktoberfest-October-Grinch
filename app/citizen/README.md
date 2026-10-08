# Citizen reporting and evidence intake

**Development owner: Aadidev.** This is development ownership, not a retrospective authorship claim.

This feature connects residents and field reporters to Waterline's evidence pipeline. It provides public hazard discovery, personal or shared reporting links, situation and vulnerability inputs, photo/location upload, receipts, geofence warnings and stored evidence.

## Code

| File | Responsibility |
| --- | --- |
| `routes.py` | Public portal and alerts, reporting-link resolution, civilian and assignment-bound field photo submission |
| `service.py` | Resolve recipient/public tokens to alerts and create shared public reporting links |

Frontend files remain shared under [`../static/`](../static/): `portal.html`, `portal.js`, `report.html`, `report.js`, `upload.js`, `location.js` and `style.css`. Shared upload/location utilities also support responder reporting without duplication.

## Workflow and interface

1. Open `/report` and choose a locality/alert, or open a personal SMS reporting link at `/report/{token}`. Legacy `/r/{token}` links also work.
2. Select whether help is needed, the reporter is reporting from a secure location, or the report concerns another person. Supply the number needing help and any children, elderly or mobility flags.
3. Add one to four photos and an optional note. The safety banner instructs users not to enter water or damaged buildings for a photo.
4. Select a map location or use device geolocation. Accuracy is shown; a location failure does not create a fictitious coordinate.
5. Resize images, show upload progress and retry temporary failures while the tab stays open. Server validation checks image readability, dimensions, upload limits and reporting tokens.
6. Invoke the intelligence package. Measurable flood reports update a nearby incident; failed, unsupported or unmeasurable scenes are stored for human review without fabricated depth.
7. Return a receipt containing extraction status and safety wording. Residents do not receive the command priority queue or other residents' reports.

Endpoints are `/`, `/report`, `/report/{token}`, `/r/{token}`, `/api/public/alerts`, `/api/report-link/{token}`, `/api/reports` and `/api/field/reports`. Field uploads require an authenticated admin session and a current team/site assignment even though the intake implementation is reused here.

## Data and integration

Reports retain photo paths, timestamps, location source/accuracy, situation, counts, notes, extraction result/status and team identity when applicable. Photos live in the ignored upload directory under generated filenames. Duplicate hashes are checked within the alert and compatible extraction mode. Nearby flood observations cluster within the configured distance; live and mock observations are not combined in one rate fit.

The intelligence feature supplies validated perception and intervals. The operations feature supplies team assignments and displays the resulting evidence history. Shared SQLite/configuration are application infrastructure.

## Verification and limits

Run `python -m pytest tests/test_api.py tests/test_field_reports.py -q` and `node --test tests/test_location.cjs` from repository root. Tests cover tokens, uploads, geofence flags, duplicates, assignment checks and location behavior. Live mode sends resized images to Google's hosted model; the API key remains server-side. EXIF capture-time/GPS prioritization, persistent offline queues, public-report rate limits, multilingual text, voice transcription and retention/deletion controls are still unimplemented requirements, not hidden placeholders.
