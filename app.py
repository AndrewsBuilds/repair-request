# Andrews Properties - Repair Request Web App
# Week 3 - Flask + AI Triage

import os
import anthropic
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

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

    return jsonify({"triage": message.content[0].text})

if __name__ == "__main__":
        app.run(debug=True)



