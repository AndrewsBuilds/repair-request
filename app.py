# Formosa Nova - Repair Request Web App
import os
import base64
import anthropic
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── Microsoft Graph / SharePoint config ────────────────────────────────────
TENANT_ID     = os.environ.get("AZURE_TENANT_ID")
CLIENT_ID     = os.environ.get("AZURE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")


def get_graph_token():
    """Get an access token from Azure AD for Microsoft Graph API."""
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default"
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["access_token"]


def get_sharepoint_site_id(token):
    """Get the SharePoint site ID needed for Graph API calls."""
    url = "https://graph.microsoft.com/v1.0/sites/netorgft13553269.sharepoint.com:/sites/RentalPropertiesHub"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["id"]


def get_list_id(token, site_id):
    """Get the ID of the Repair Requests SharePoint list."""
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    lists = response.json().get("value", [])
    for lst in lists:
        if lst["name"] == "Repair Requests":
            return lst["id"]
    raise Exception("Repair Requests list not found in SharePoint site")


def save_to_sharepoint(tenant_name, unit, issue_type, urgency, description, email, phone):
    """Save a repair request as a new item in the SharePoint Repair Requests list."""
    try:
        token = get_graph_token()
        site_id = get_sharepoint_site_id(token)
        list_id = get_list_id(token, site_id)

        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "fields": {
                "Title": tenant_name,
                "Unit": unit,
                "Issue_x0020_Type": issue_type,
                "Urgency": urgency,
                "Description": description,
                "Email": email,
                "Phone": phone,
                "Submission_x0020_Date": datetime.now(timezone.utc).isoformat(),
                "Status": "New"
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code not in (200, 201):
            print(f"SharePoint save failed: {response.status_code} {response.text}")
        else:
            print("SharePoint record created successfully")

    except Exception as e:
        print(f"SharePoint error: {e}")


def send_teams_notification(tenant_name, unit, issue_type, urgency, description):
    """Post a repair request notification to the Teams repair-requests channel."""
    webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")
    if not webhook_url:
        print("Teams webhook URL not configured — skipping notification")
        return

    urgency_emoji = {
        "Emergency": "🚨",
        "Urgent": "🔴",
        "Routine": "🟡",
        "Low": "🟢"
    }.get(urgency, "🔧")

    message = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"{urgency_emoji} New Repair Request — {issue_type}",
                            "weight": "Bolder",
                            "size": "Medium"
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Tenant", "value": tenant_name},
                                {"title": "Unit", "value": unit},
                                {"title": "Issue Type", "value": issue_type},
                                {"title": "Urgency", "value": urgency},
                                {"title": "Description", "value": description}
                            ]
                        }
                    ]
                }
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=message)
        if response.status_code != 202:
            print(f"Teams notification failed: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Teams notification error: {e}")


def send_emails(tenant_name, tenant_email, issue_type, urgency, ai_response, photos=None):
    sg = SendGridAPIClient(api_key=os.environ.get("SENDGRID_API_KEY"))
    from_email = os.environ.get("SENDGRID_FROM_EMAIL")

    try:
        # ── Email to tenant ──
        tenant_message = Mail(
            from_email=from_email,
            to_emails=tenant_email,
            subject=f"Repair Request Received — {issue_type}",
            plain_text_content=ai_response
        )
        sg.send(tenant_message)

        # ── Email to owner (with photo attachments if provided) ──
        owner_body = (
            f"New repair request submitted:\n\n"
            f"Tenant: {tenant_name}\n"
            f"Issue: {issue_type}\n"
            f"Urgency: {urgency}\n"
            f"Photos attached: {len(photos) if photos else 0}\n\n"
            f"AI Triage:\n{ai_response}"
        )

        owner_message = Mail(
            from_email=from_email,
            to_emails=os.environ.get("OWNER_EMAIL"),
            subject=f"New Repair Request — {issue_type} ({urgency})",
            plain_text_content=owner_body
        )

        if photos:
            for i, photo in enumerate(photos):
                attachment = Attachment(
                    FileContent(photo['data']),
                    FileName(photo['filename'] or f"photo_{i+1}.jpg"),
                    FileType(photo['type'] or 'image/jpeg'),
                    Disposition('attachment')
                )
                owner_message.add_attachment(attachment)

        sg.send(owner_message)

    except Exception as e:
        print(f"SendGrid error: {e.body}")


# Serve the HTML form
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# Handle form submission
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    tenant_name  = data.get("tenantName")
    unit         = data.get("unit")
    issue_type   = data.get("issueType")
    urgency      = data.get("urgency")
    description  = data.get("description")
    tenant_email = data.get("email")
    phone        = data.get("phone", "Not provided")
    photos       = data.get("photos", [])

    prompt = f"""
You are a property management assistant for Formosa Nova.
A tenant has submitted the following repair request:
Tenant: {tenant_name} / Unit: {unit} / Issue Type: {issue_type} / Urgency: {urgency} / Description: {description}

Write a short, warm, professional acknowledgment email BODY to the tenant.
Rules: No subject line, no headers like "1." or "2.", no ** markdown, start with "Dear [name],",
confirm receipt, mention issue type and urgency, follow up within 24 hours, close warmly,
sign off as "Formosa Nova Maintenance Team"
"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    triage_response = message.content[0].text

    # Send emails, Teams notification, and save to SharePoint
    send_emails(tenant_name, tenant_email, issue_type, urgency, triage_response, photos)
    send_teams_notification(tenant_name, unit, issue_type, urgency, description)
    save_to_sharepoint(tenant_name, unit, issue_type, urgency, description, tenant_email, phone)

    return jsonify({"triage": triage_response})


if __name__ == "__main__":
    app.run(debug=True)



