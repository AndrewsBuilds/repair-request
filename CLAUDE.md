# Formosa Nova — Repair Request Portal

## What this is
A single-page tenant repair request form backed by a Flask API. Tenants fill out the form, Claude generates a warm acknowledgment email, and the submission is saved to SharePoint, emailed to the tenant and owner, and posted to a Teams channel.

## Stack
- **Backend:** Python / Flask (`app.py`), served by gunicorn
- **Frontend:** Single self-contained HTML file (`index.html`)
- **AI:** Anthropic Claude (`claude-opus-4-6`) via the `anthropic` SDK
- **Email:** Microsoft Graph API (`/users/{sender}/sendMail`)
- **Storage:** SharePoint list via Microsoft Graph API
- **Notifications:** Microsoft Teams via Adaptive Card webhook
- **Deploy:** Azure App Service — push to `main` triggers GitHub Actions deployment

## Key files
| File | Purpose |
|---|---|
| `app.py` | Flask app, all API logic |
| `index.html` | Frontend form (no build step, served directly by Flask) |
| `triage.py` | Leftover dev prototype — not used by the app, safe to delete |
| `Procfile` | `web: gunicorn app:app` |
| `requirements.txt` | Pinned dependencies |
| `.github/workflows/main_formosa-nova-portal.yml` | CI/CD to Azure Web App `formosa-nova-portal` |

## Environment variables (all required unless noted)
| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `AZURE_TENANT_ID` | Azure AD tenant for Graph auth |
| `AZURE_CLIENT_ID` | App registration client ID |
| `AZURE_CLIENT_SECRET` | App registration client secret |
| `MAIL_SENDER` | From address for Graph sendMail (default: `repairs@theameizenteam.com`) |
| `OWNER_EMAIL` | Owner notification recipient |
| `TEAMS_WEBHOOK_URL` | Incoming webhook URL for Teams notifications (optional — skipped if absent) |

## Architecture notes

### Request flow (one form submission)
1. Frontend validates fields, converts photos to base64, POSTs to `/submit`
2. Backend validates all fields server-side (returns `400` with field errors if invalid)
3. Claude generates the tenant acknowledgment email body
4. `get_graph_token()` is called **once** — the token is passed to both `send_emails` and `save_to_sharepoint`
5. `send_emails` sends the tenant confirmation and owner notification via Graph API
6. `send_teams_notification` posts an Adaptive Card to the Teams webhook
7. `save_to_sharepoint` writes a new list item; static SharePoint IDs (`site_id`, `list_id`, `col_map`) are **module-level cached** after the first request

### SharePoint column map
Internal column names are confirmed in `SHAREPOINT_COLUMNS` at the top of `app.py`. The `_load_sharepoint_ids()` helper caches them at startup so they are only fetched once per app instance.

### Validation
- Frontend: client-side JS in `index.html` (`handleSubmit`)
- Backend: server-side in `submit()` using allowlists for `issueType`, `urgency`, and `access`; a `400` with a structured `errors` dict is returned on failure; the frontend displays these inline via `showServerErrors()`

## Running locally
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...  # plus other env vars
python app.py               # dev server on http://localhost:5000
```

## Deployment
Push to `main`. The GitHub Actions workflow builds and deploys to the `formosa-nova-portal` Azure Web App automatically. No manual steps needed.
