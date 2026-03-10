# Formosa Nova - Repair Request Web App
import os
import sys
import base64
import anthropic
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

TENANT_ID     = os.environ.get("AZURE_TENANT_ID")
CLIENT_ID     = os.environ.get("AZURE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")


def get_graph_token():
    print(f"[SharePoint] Getting token for tenant: {TENANT_ID}", flush=True)
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default"
    }
    response = requests.post(url, data=data)
    print(f"[SharePoint] Token response status: {response.status_code}", flush=True)
    if response.status_code != 200:
        print(f"[SharePoint] Token error: {response.text}", flush=True)
    response.raise_for_status()
    return response.json()["access_token"]


def get_sharepoint_site_id(token):
    url = "https://graph.microsoft.com/v1.0/sites/netorgft13553269.sharepoint.com:/sites/RentalPropertiesHub"
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[SharePoint] Getting site ID", flush=True)
    response = requests.get(url, headers=headers)
    print(f"[SharePoint] Site ID response: {response.status_code}", flush=True)
    if response.status_code != 200:
        print(f"[SharePoint] Site ID error: {response.text}", flush=True)
    response.raise_for_status()
    return response.json()["id"]


def get_list_id(token, site_id):
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[SharePoint] Getting lists", flush=True)
    response = requests.get(url, headers=headers)
    print(f"[SharePoint] Lists response: {response.status_code}", flush=True)
    if response.status_code != 200:
        print(f"[SharePoint] Lists error: {response.text}", flush=True)
    response.raise_for_status()
    lists = response.json().get("value", [])
    list_names = [lst["name"] for lst in lists]
    print(f"[SharePoint] Available lists: {list_names}", flush=True)
    for lst in lists:
        if lst["name"] == "Repair Requests":
            print(f"[SharePoint] Found list: {lst['id']}", flush=True)
            return lst["id"]
    raise Exception(f"List not found. Available: {list_names}")


def save_to_sharepoint(tenant_name, unit, issue_type, urgency, description, email, phone):
    print("[SharePoint] Starting save_to_sharepoint", flush=True)
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

        print(f"[SharePoint] Posting item", flush=True)
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
        tenant_message = Mail(
            from_email=from_email,
            to_emails=tenant_email,
            subject=f"Repair Request Received — {issue_type}",
            plain_text_content=ai_response
        )
        sg.send(tenant_message)

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
    save_to_sharepoint(tenant_name, unit, issue_type, urgency, description, tenant_email, phone)

    return jsonify({"triage": triage_response})


if __name__ == "__main__":
    app.run(debug=True)



