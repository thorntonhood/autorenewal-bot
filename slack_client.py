"""Slack client for reading permission expiry notifications from App DMs."""

from datetime import datetime, timedelta, timezone
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackClient:
    def __init__(self, bot_token: str):
        self.client = WebClient(token=bot_token)

    def _find_app_dm_channel_ids(self, app_names: list[str]) -> list[str]:
        """Find the DM channel IDs for the given Slack app names."""
        channel_ids = []
        try:
            # List all IM (direct message) conversations
            result = self.client.conversations_list(types="im", limit=200)
            for convo in result.get("channels", []):
                channel_id = convo.get("id")
                user_id = convo.get("user")
                if not user_id:
                    continue
                # Look up the user/bot profile to get the display name
                try:
                    profile = self.client.users_info(user=user_id)
                    name = profile["user"].get("name", "").lower()
                    real_name = profile["user"].get("real_name", "").lower()
                    for app_name in app_names:
                        if app_name.lower() in name or app_name.lower() in real_name:
                            channel_ids.append(channel_id)
                            print(f"[slack] Found App DM for '{app_name}': channel {channel_id}")
                            break
                except SlackApiError:
                    continue
        except SlackApiError as e:
            print(f"[slack] Error listing DM conversations: {e.response['error']}")
        return channel_ids

    def get_expiry_messages(
        self,
        app_names: list[str],
        keywords: list[str],
        lookahead_days: int = 14,
    ) -> list[dict]:
        """Read App DM messages from Okta, Convoy, etc. and return expiry notifications."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookahead_days)
        channel_ids = self._find_app_dm_channel_ids(app_names)

        if not channel_ids:
            print("[slack] No App DM channels found. Check that app_names in config.yaml match exactly.")
            return []

        messages = []
        for channel_id in channel_ids:
            try:
                result = self.client.conversations_history(
                    channel=channel_id,
                    oldest=str(cutoff.timestamp()),
                    limit=100,
                )
                for msg in result.get("messages", []):
                    text = msg.get("text", "")
                    # Only include messages that mention expiry keywords
                    if any(kw.lower() in text.lower() for kw in keywords):
                        messages.append({
                            "channel": channel_id,
                            "text": text,
                            "ts": msg.get("ts"),
                            "blocks": msg.get("blocks", []),
                        })
            except SlackApiError as e:
                print(f"[slack] Error reading channel {channel_id}: {e.response['error']}")

        return messages
