# Andrews Properties - Repair Request Triage
# Week 2 - AI-Powered Triage

import os
import anthropic

# Repair request details
tenant_name = "Jane Smith"
unit = "Unit 4B - 123 Banana St."
issue_type = "Plumbing"
urgency = "Urgent"
description = "Kitchen sink is leaking under the cabinet."

# Set up the Anthropic client
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Build the prompt
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
3. A short, professional acknowledgment email to the tenant

Keep the email warm but brief.
"""

# Call Claude
message = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
)

# Print the original ticket
print("=" * 40)
print("ANDREWS PROPERTIES")
print("Repair Request Ticket")
print("=" * 40)
print(f"Tenant:      {tenant_name}")
print(f"Unit:        {unit}")
print(f"Issue:       {issue_type}")
print(f"Urgency:     {urgency}")
print(f"Description: {description}")
print("=" * 40)
print("\nAI TRIAGE RESPONSE:")
print("=" * 40)
print(message.content[0].text)
