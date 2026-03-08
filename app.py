# Andrews Properties - Repair Request Web App
# Week 3 - Flask + AI Triage

import os
import anthropic
from flask import Flask, request, jsonify, send_from_directory
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def send_emails(tenant_name, tenant_email, issue_type, urgency, ai_response):
    sg = SendGridAPIClient(api_key=os.environ.get("SENDGRID_API_KEY"))
    from_email = os.environ.get("SENDGRID_FROM_EMAIL")

    # Email to tenant
    tenant_message = Mail(
        from_email=from_email,
        to_emails=tenant_email,
        subject=f"Repair Request Received — {issue_type}",
        plain_text_content=ai_response
    )
    sg.send(tenant_message)

    # Email to Jason
    owner_message = Mail(
        from_email=from_email,
        to_emails=os.environ.get("OWNER_EMAIL"),
        subject=f"New Repair Request — {issue_type} ({urgency})",
        plain_text_content=f"New repair request submitted:\n\nTenant: {tenant_name}\nIssue: {issue_type}\nUrgency: {urgency}\n\nAI Triage:\n{ai_response}"
    )
    sg.send(owner_message)

#Serve the HTML form
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# Handle form submission
@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    tenant_name = data.get("tenantName")
    unit = data.get("unit")
    issue_type = data.get("issueType")
    urgency = data.get("urgency")
    description = data.get("description")

    prompt = f"""
You are a property management assistant for Andrews Properties.
A tenant has submitted the following repair request:

Tenant: {tenant_name}
Unit: {unit}
Issue Type: {issue_type}
Urgency: {urgency}
Description: {description}

Write a short, warm, professional acknowledgment email BODY to the tenant.

Rules:
- Do NOT include a subject line
- Do NOT include headers like "1." or "2."
- Do NOT include ** markdown formatting
- Start directly with "Dear [tenant name],"
- Confirm we received their request
- mention the issue type and urgency
- Let them know we'll follow up within 24 hours
- Close warmly
- Sign off as "Andrews Properties Maintenance Team"
"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    triage_response = message.content[0].text
    tenant_email = data.get("email")
    send_emails(tenant_name, tenant_email, issue_type, urgency, triage_response)
    return jsonify({"triage": triage_response})

if __name__ == "__main__":
        app.run(debug=True)



