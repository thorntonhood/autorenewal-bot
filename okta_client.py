"""Okta client for submitting permission renewal requests."""

import httpx


class OktaClient:
    def __init__(self, domain: str, api_token: str):
        self.base_url = f"https://{domain}/api/v1"
        self.headers = {
            "Authorization": f"SSWS {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_user_id(self, email: str) -> str | None:
        """Look up Okta user ID by email."""
        with httpx.Client() as client:
            resp = client.get(
                f"{self.base_url}/users/{email}",
                headers=self.headers,
            )
            if resp.status_code == 200:
                return resp.json().get("id")
        return None

    def request_group_membership(self, user_id: str, group_id: str) -> bool:
        """Request to add a user to an Okta group (i.e. renew group-based access)."""
        with httpx.Client() as client:
            resp = client.put(
                f"{self.base_url}/groups/{group_id}/users/{user_id}",
                headers=self.headers,
            )
            return resp.status_code == 204

    def request_app_assignment(self, user_id: str, app_id: str) -> bool:
        """Assign/re-assign a user to an Okta application."""
        with httpx.Client() as client:
            resp = client.post(
                f"{self.base_url}/apps/{app_id}/users",
                headers=self.headers,
                json={"id": user_id, "scope": "USER"},
            )
            return resp.status_code in (200, 201)

    def renew_permission(self, permission: dict) -> dict:
        """
        Renew an Okta permission described by the parsed dict.
        Expected keys: user_email, resource_type ('group' or 'app'), resource_id
        """
        user_id = self.get_user_id(permission["user_email"])
        if not user_id:
            return {"success": False, "error": f"User not found: {permission['user_email']}"}

        resource_type = permission.get("resource_type", "group")
        resource_id = permission.get("resource_id", "")

        if resource_type == "group":
            success = self.request_group_membership(user_id, resource_id)
        elif resource_type == "app":
            success = self.request_app_assignment(user_id, resource_id)
        else:
            return {"success": False, "error": f"Unknown resource type: {resource_type}"}

        return {"success": success, "system": "okta", "resource_id": resource_id}
