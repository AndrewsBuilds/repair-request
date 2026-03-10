# Formosa Nova - Repair Request Web App
import os
import base64
import anthropic
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

TENANT_ID     = os.environ.get("AZURE_TENANT_ID")
CLIENT_ID     = os.environ.get("AZURE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")

# Map form radio values to friendly display text for SharePoint
ACCESS_MAP = {
    "yes_alone":      "You may enter when I'm not home",
    "yes_present":    "Please schedule when I'm present",
    "emergency_only": "Entry for emergencies only"
}

# Hardcoded internal SharePoint column names (confirmed from logs)
SHAREPOINT_COLUMNS = {
    "Unit":             "Unit",
    "Issue Type":       "IssueType",
    "Urgency":          "Urgency",
    "Description":      "Description",
    "Email":            "Email",
    "Phone":            "Phone",
    "Submission Date":  "SubmissionDate",
    "Status":           "Status",
    "AI Triage Response": "AI_x0020_Triage_x0020_Response",
    "Entry Authorization": "Entry_x0020_Authorization"
}


def get_graph_token():
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
    url = "https://graph.microsoft.com/v1.0/sites/netorgft13553269.sharepoint.com:/sites/RentalPropertiesHub"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["id"]


def get_list_id(token, site_id):
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    for lst in response.json().get("value", []):
        if lst["name"] == "Repair Requests":
            return lst["id"]
    raise Exception("Repair Requests list not found")


def get_column_names(token, site_id, list_id):
    """Fetch actual internal column names from SharePoint."""
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/columns"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return {col.get("displayName"): col.get("name") for col in response.json().get("value", [])}


def save_to_sharepoint(tenant_name, unit, issue_type, urgency, description,
                       email, phone, access, ai_response):
    print("[SharePoint] Starting save_to_sharepoint", flush=True)
    try:
        token = get_graph_token()
        site_id = get_sharepoint_site_id(token)
        list_id = get_list_id(token, site_id)
        col_map = get_column_names(token, site_id, list_id)

        # Translate raw form value to friendly display text
        entry_auth = ACCESS_MAP.get(access, access)

        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "fields": {
                "Title":                              tenant_name,
                col_map.get("Unit", "Unit"):          unit,
                col_map.get("Issue Type", "IssueType"): issue_type,
                col_map.get("Urgency", "Urgency"):    urgency,
                col_map.get("Description", "Description"): description,
                col_map.get("Email", "Email"):        email,
                col_map.get("Phone", "Phone"):        phone,
                col_map.get("Submission Date", "SubmissionDate"): datetime.now(timezone.utc).isoformat(),
                col_map.get("Status", "Status"):      "New",
                col_map.get("Entry Authorization", "Entry_x0020_Authorization"): entry_auth,
                col_map.get("AI Triage Response", "AI_x0020_Triage_x0020_Response"): ai_response
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        print(f"[SharePoint] Post response: {response.status_code}", flush=True)
        if response.status_code not in (200, 201):
            print(f"[SharePoint] Post error: {response.text}", flush=True)
        else:
            print("[SharePoint] Record created successfully!", flush=True)

    except Exception as e:
        print(f"[SharePoint] Exception: {str(e)}", flush=True)


def send_teams_notification(tenant_name, unit, issue_type, urgency, description):
    webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")
    if not webhook_url:
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
    print("[Email] Starting send_emails", flush=True)
    try:
        token = get_graph_token()
        sender = os.environ.get("MAIL_SENDER", "repairs@theameizenteam.com")
        owner_email = os.environ.get("OWNER_EMAIL")
        url = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # --- Tenant confirmation email ---
        tenant_payload = {
            "message": {
                "subject": f"Repair Request Received — {issue_type}",
                "body": {"contentType": "Text", "content": ai_response},
                "toRecipients": [{"emailAddress": {"address": tenant_email}}]
            },
            "saveToSentItems": "true"
        }
        r = requests.post(url, headers=headers, json=tenant_payload)
        print(f"[Email] Tenant email response: {r.status_code}", flush=True)
        if r.status_code not in (200, 202):
            print(f"[Email] Tenant email error: {r.text}", flush=True)

        # --- Owner notification email ---
        owner_body = (
            f"New repair request submitted:\n\n"
            f"Tenant: {tenant_name}\n"
            f"Issue: {issue_type}\n"
            f"Urgency: {urgency}\n"
            f"Photos attached: {len(photos) if photos else 0}\n\n"
            f"AI Triage:\n{ai_response}"
        )

        owner_message = {
            "subject": f"New Repair Request — {issue_type} ({urgency})",
            "body": {"contentType": "Text", "content": owner_body},
            "toRecipients": [{"emailAddress": {"address": owner_email}}]
        }

        # Attach photos if provided
        if photos:
            owner_message["attachments"] = [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": photo.get("filename") or f"photo_{i+1}.jpg",
                    "contentType": photo.get("type") or "image/jpeg",
                    "contentBytes": photo.get("data")
                }
                for i, photo in enumerate(photos)
            ]

        owner_payload = {
            "message": owner_message,
            "saveToSentItems": "true"
        }
        r = requests.post(url, headers=headers, json=owner_payload)
        print(f"[Email] Owner email response: {r.status_code}", flush=True)
        if r.status_code not in (200, 202):
            print(f"[Email] Owner email error: {r.text}", flush=True)

    except Exception as e:
        print(f"[Email] Exception: {str(e)}", flush=True)


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


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
    access       = data.get("access", "yes_alone")

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

    send_emails(tenant_name, tenant_email, issue_type, urgency, triage_response, photos)
    send_teams_notification(tenant_name, unit, issue_type, urgency, description)
    save_to_sharepoint(tenant_name, unit, issue_type, urgency, description,
                       tenant_email, phone, access, triage_response)

    return jsonify({"triage": triage_response})


if __name__ == "__main__":
    app.run(debug=True)