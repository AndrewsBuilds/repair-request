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

Please provide:
1. Confirmed issue category
2. Priority level: Critical / High / Standard / Low
3. A short professional acknowledgment email to the tenant

Keep the email warm but brief.
"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return jsonify({"triage": message.content[0].text})

if __name__ == "__main__":
        app.run(debug=True)



