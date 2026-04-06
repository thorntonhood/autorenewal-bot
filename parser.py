"""Uses Claude to parse Slack messages and extract structured permission expiry info."""

import json
import anthropic

SYSTEM_PROMPT = """You are a permissions bot assistant. Your job is to parse Slack notification
messages about expiring permissions and extract structured data.

For each message, extract all expiring permissions mentioned. Return a JSON array where each item has:
- system: the system the permission is for (e.g. "okta", "convoy", "github", "aws", "other")
- user_email: the email address of the user whose access is expiring (if mentioned)
- resource_name: the name of the resource, group, app, or role expiring
- resource_id: the system ID of the resource if present (otherwise empty string)
- resource_type: for okta: "group" or "app"; for others: "role" or "access"
- expiry_date: the expiry date as ISO 8601 string if mentioned (otherwise empty string)
- role: the specific role or permission level if mentioned (otherwise empty string)

If you cannot extract a permission record from a message, return an empty array for it.
Always return valid JSON only, no commentary."""


def parse_expiry_messages(messages: list[dict], model: str) -> list[dict]:
    """
    Send Slack messages to Claude for structured parsing.
    Returns a flat list of permission records to renew.
    """
    if not messages:
        return []

    client = anthropic.Anthropic()
    permissions = []

    for msg in messages:
        text = msg.get("text", "").strip()
        if not text:
            continue

        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Parse this Slack message:\n\n{text}"}
            ],
        )

        raw = response.content[0].text.strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for item in parsed:
                    item["source_message"] = msg.get("permalink", "")
                    item["source_channel"] = msg.get("channel", "")
                    permissions.append(item)
        except json.JSONDecodeError:
            print(f"[parser] Failed to parse Claude response for message: {text[:80]}...")

    return permissions
