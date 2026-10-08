# Office administration and alert campaigns

**Development owner: Aadithya Ram.** This assignment defines responsibility; it is not a claim that all listed code was authored by this member.

This feature lets the October Grinch team operate Waterline's main office: sign in, maintain opted-in residents, choose a circular hazard area, prepare a campaign, review recipient messages, and simulate sending reporting links.

## Code

| File | Responsibility |
| --- | --- |
| `routes.py` | Admin login/logout, resident registration, area preview, alert creation, campaign counters, recipient preview, simulated sending and outbox |
| `auth.py` | Password hashing and verification, session fingerprints, credential-version invalidation, origin checks and interactive admin setup |
| `models.py` | Validated alert, circular area and resident inputs |
| `service.py` | Circle-based resident matching and deterministic SMS message construction |

Office and login screens use shared frontend files in [`../static/`](../static/): `index.html`, `app.js`, `login.html`, `login.js`, `location.js` and `style.css`. The office shell is also used by command and responder screens, so it remains shared rather than duplicated.

## Workflow and interface

1. Configure an admin locally with `python -m app.office.auth`, then sign in at `/admin/login`.
2. Register a resident name, phone or synthetic demo label, registered location and consent.
3. Select the alert center and radius on the office map. Recipient preview includes only consenting registered residents inside the circle.
4. Create a hazard alert with event time and message. Each selected recipient receives a personal random reporting token; the alert also has a shared public reporting link.
5. Review recipients and message previews, then simulate sending. Consent is checked again at send time and repeated sends skip already processed recipients.
6. Review campaign counters and the simulated outbox. No physical phone-location discovery or actual SMS delivery is implemented.

Entry pages are `/office`, `/authority` and `/admin/login`. APIs cover `/api/auth/*`, `/api/residents`, `/api/residents/demo`, `/api/office`, `/api/office/preview`, `/api/office/recipients`, `/api/alerts`, `/api/alerts/{alert_id}/send` and `/api/outbox`.

## Data and dependencies

Uses shared SQLite tables for alerts, recipients, residents, public reporting links, sessions and login attempts. Geofence distance uses the intelligence package's haversine function. Shared configuration and database lifecycle stay in `app/settings.py` and `app/db.py`. Public-link creation is reused from citizen reporting.

`ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` are stored only in ignored `.env`. `ADMIN_COOKIE_SECURE=true` is appropriate for HTTPS. Credentials are never included in feature documentation, Git commits or frontend responses.

## Verification and limits

From the repository root, run `python -m pytest tests/test_auth.py tests/test_office.py -q`. These tests exercise session/access boundaries, credential behavior, registered-locality matching, consent and repeat-safe simulated sends. Real SMS, national alert-system integration, separate operator roles, polygon geofences and production security review remain outside the implemented feature.
