# Formosa Nova — Repair Request Portal

An AI-powered maintenance request web app for Formosa Nova properties. Tenants submit repair requests via a branded web form, receive an AI-generated confirmation email, and the property owner receives a notification with any uploaded photos attached.

**Live URL:** https://repairs.theameizenteam.com

---

## What It Does

1. Tenant fills out the repair request form
2. Flask receives the submission
3. Claude AI (Anthropic) generates a warm, professional acknowledgment email
4. SendGrid sends the tenant a confirmation email
5. SendGrid sends the owner a notification email with photo attachments
6. The AI response is displayed on the success screen

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python 3.14 + Flask |
| AI | Claude (Anthropic API) |
| Email | SendGrid (Twilio) |
| Hosting | Render.com |
| Version Control | Git + GitHub |
| Domain | GoDaddy (CNAME → Render) |

---

## Project Structure

```
repair-request/
├── app.py           # Flask backend — handles form submission, AI triage, email
├── index.html       # Frontend — branded form UI
├── Procfile         # Tells Render how to start the app (gunicorn)
├── requirements.txt # Python dependencies
└── README.md        # This file
```

---

## Environment Variables

Set these in Render → Settings → Environment before deploying:

| Key | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key (console.anthropic.com) |
| `SENDGRID_API_KEY` | SendGrid API key (app.sendgrid.com) |
| `SENDGRID_FROM_EMAIL` | Verified sender email in SendGrid |
| `OWNER_EMAIL` | Email address to receive owner notifications |

---

## Local Development

```bash
# 1. Clone the repo
git clone git@github.com:AndrewsBuilds/repair-request.git
cd repair-request

# 2. Install dependencies (always use Git Bash on Windows)
py -m pip install -r requirements.txt

# 3. Set environment variables
export ANTHROPIC_API_KEY="sk-ant-..."
export SENDGRID_API_KEY="SG...."
export SENDGRID_FROM_EMAIL="you@yourdomain.com"
export OWNER_EMAIL="you@yourdomain.com"

# 4. Run locally
py app.py

# 5. Visit in browser
http://127.0.0.1:5000
```

---

## Deployment (Render)

Auto-deploys on every push to `main`. To manually deploy:

```bash
git add .
git commit -m "Your message here"
git push
```

Render settings:
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app:app`

---

## Custom Domain (GoDaddy → Render)

DNS record set in GoDaddy:

| Type | Name | Value | TTL |
|---|---|---|---|
| CNAME | repairs | repair-request.onrender.com | 1 Hour |

SSL is provisioned automatically by Render once DNS propagates.

---

## Key Commands (Git Bash on Windows)

```bash
# Deploy changes
git add .
git commit -m "Description of change"
git push

# Install a new package
py -m pip install <package-name>
py -m pip freeze > requirements.txt  # Always update after installing!

# Check what's in requirements.txt
cat requirements.txt | grep <package-name>
```

---

## Form Features

- Auto-formats phone number to `(555) 000-0000` with live validation
- Photo upload with thumbnail preview (sent as attachments to owner email)
- Progress bar tracks form completion
- Urgency selector — Urgent / Standard / Low
- Entry authorization options
- AI-generated confirmation displayed on success screen

---

## Planned Enhancements

- [ ] Migrate hosting to Azure App Service
- [ ] Replace SendGrid with Microsoft Graph API (Outlook)
- [ ] Store requests in SharePoint list
- [ ] Teams notification on new submission
- [ ] Power Automate workflows for ticket assignment
- [ ] Power BI dashboard for request analytics
- [ ] Tenant portal to check request status

---

## Notes

- Free tier on Render spins down after inactivity — first request may take 50+ seconds to load
- SendGrid free tier allows 100 emails/day
- Photos are converted to base64 in the browser before sending — large files may slow submission
- Always run `pip freeze > requirements.txt` from Git Bash after installing new packages (virtual environment gotcha on Windows)

---

*Built by Jason Andrews — Formosa Nova Property Management*
