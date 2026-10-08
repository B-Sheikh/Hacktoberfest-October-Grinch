# Deploying Waterline on Render

Public citizen portal: https://hacktoberfest-october-grinch.onrender.com/report

Operator login: https://hacktoberfest-october-grinch.onrender.com/admin/login

The public portal was opened successfully during repository preparation. This establishes page availability, not end-to-end AI accuracy, persistent storage or emergency readiness. Operator credentials are private and must not appear in the repository.

## Service settings

Connect this GitHub repository to a Render **Python Web Service**. Use branch `main` and leave Root Directory empty.

| Setting | Value |
| --- | --- |
| Build command | `pip install -r requirements.txt` |
| Start command | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/health` |

The local `run.sh` binds localhost on port 8000; use the start command above on Render. Python 3.12 is the locally tested version. To pin Render's runtime, set `PYTHON_VERSION` to a fully qualified supported 3.12 patch version, following [Render's Python version documentation](https://render.com/docs/python-version).

## Environment variables

Enter these in Render's Environment settings, not in tracked source files:

| Variable | Value / instructions |
| --- | --- |
| `PUBLIC_BASE_URL` | `https://hacktoberfest-october-grinch.onrender.com` for the current service; use the new service URL for another deployment |
| `ADMIN_USERNAME` | Username selected during local admin setup |
| `ADMIN_PASSWORD_HASH` | Complete generated hash, without surrounding dotenv quotes |
| `ADMIN_COOKIE_SECURE` | `true` |
| `VISION_PROVIDER` | `mock` for synthetic demonstration; `gemini` for live analysis |
| `VISION_MODEL` | `gemma-4-26b-a4b-it`, subject to availability for your API key |
| `GEMINI_API_KEY` | Private Google API key; required for live analysis only |
| `BRIEFING_PROVIDER` | `template` |
| `WATERLINE_DB` | `/var/data/waterline.db` when using the persistent disk below |
| `WATERLINE_UPLOADS` | `/var/data/uploads` when using the persistent disk below |

`HMAC_SECRET` and the three `TWILIO_*` variables are reserved and can remain empty. Current alert sending is simulated even when Twilio credentials are present. Runtime status and code responses, rather than a configured provider name, establish whether live analysis succeeded.

## Admin setup

After installing dependencies and copying `.env.example` to ignored `.env`, run locally:

```powershell
.\.venv\Scripts\python.exe -m app.office.auth
```

On Linux/macOS use `.venv/bin/python -m app.office.auth`. Choose a password of at least 12 characters. Copy only the generated `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` values from `.env` into Render. The login form accepts the original password, not the hash. Do not commit `.env` or include credentials in screenshots. Save the environment changes and redeploy. Credential rotation requires a restart and invalidates existing sessions.

## Persistent storage

The application stores SQLite data and uploaded images on the filesystem. Render's default filesystem is ephemeral: writes can be lost on redeploy or restart. Free web services do not support persistent disks. A paid web service with a disk mounted at `/var/data`, plus the paths above, preserves both types of data. Keep the service at one instance for the current disk-backed SQLite architecture.

For a disposable free demonstration, leave `WATERLINE_DB=data/waterline.db` and `WATERLINE_UPLOADS=uploads`, expect data loss, and use only synthetic reports. Do not describe a free instance as durable storage. Changing database paths starts a separate database; it does not migrate existing records or photos. Keep a coordinated database/upload backup before storage changes.

See [Render persistent disks](https://render.com/docs/disks) and [free service limitations](https://render.com/docs/free).

## Deployment verification

1. Open `/api/health`. This checks service availability; it does not verify a live model response.
2. Open `/admin/login`, sign in and confirm `/office`, `/command` and `/responders` are accessible.
3. In a controlled synthetic demo, load demo sites and residents, create an alert, and confirm it appears in `/report`.
4. Submit a synthetic report from a phone over HTTPS. Verify its receipt, saved location, evidence and extraction status in the office dashboard. In mock mode keep simulation labels visible.
5. Dispatch a team, open its field workspace and submit a synthetic field update. Verify it appears in the assigned site's history.
6. If a persistent disk is configured, restart the service and verify the same report and photos remain. This must be checked on the actual service; repository tests do not prove persistence on Render.

Do not submit personal information or actual emergency reports for testing. Public upload throttling, retention/deletion controls, separate responder accounts and professional validation remain outstanding.

## Redeployment and troubleshooting

Save environment changes and redeploy from Render's dashboard. Repository changes can deploy automatically if the service's auto-deploy setting is enabled. Review the build/runtime logs after each deployment.

- Import failures: ensure Root Directory is empty and the start target is `app.main:app`.
- Port failures: bind `0.0.0.0` and `$PORT` as shown above.
- Login failures: check username/hash values, secure cookies over HTTPS and that the service restarted after credential changes.
- Incorrect reporting links: correct `PUBLIC_BASE_URL` and restart; previously saved messages may retain old links.
- AI errors: verify model access/key and inspect the report's diagnostic status; failed live analysis remains manual review.
- Missing records/images after restart: check disk mount and both storage paths. An environment path alone does not create a persistent disk.

The deployment settings follow [Render's FastAPI guide](https://render.com/docs/deploy-fastapi).
