"""Convoy client for submitting permission renewal requests.

NOTE: Update the API calls below to match your Convoy instance's actual
endpoints and request schema. Convoy is often self-hosted, so paths may vary.
"""

import httpx


class ConvoyClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def renew_permission(self, permission: dict) -> dict:
        """
        Submit a permission renewal request to Convoy.
        Expected keys: user_email, resource_name, role (optional)

        TODO: Update the endpoint and payload to match your Convoy setup.
        """
        payload = {
            "requester": permission.get("user_email"),
            "resource": permission.get("resource_name"),
            "role": permission.get("role", ""),
            "justification": "Auto-renewal via AutoRenewal Bot — access expiring soon.",
        }

        with httpx.Client() as client:
            # TODO: Replace with your actual Convoy access request endpoint
            resp = client.post(
                f"{self.base_url}/api/v1/access-requests",
                headers=self.headers,
                json=payload,
            )
            if resp.status_code in (200, 201):
                return {"success": True, "system": "convoy", "request_id": resp.json().get("id")}
            return {
                "success": False,
                "system": "convoy",
                "error": f"HTTP {resp.status_code}: {resp.text}",
            }
