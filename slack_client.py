"""Slack client for reading permission expiry notifications from App DMs."""

import json
from datetime import datetime, timedelta, timezone
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_LOG_PREFIX = "[autorenewal-bot-log]"


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

    def post_run_log(self, log_channel: str, results: list[dict], username: str) -> None:
        """Post a structured log entry to the log channel after a run."""
        payload = {
            "username": username,
            "succeeded": [r["row"] for r in results if r.get("success") and r.get("row")],
            "failed": [
                {"row": r.get("row", ""), "error": r.get("error", "")}
                for r in results if not r.get("success")
            ],
        }
        text = f"{_LOG_PREFIX} {json.dumps(payload)}"
        try:
            self.client.chat_postMessage(channel=log_channel, text=text)
            print(f"[slack] Posted run log to {log_channel}")
        except SlackApiError as e:
            print(f"[slack] Failed to post run log: {e.response['error']}")

    def read_todays_logs(self, log_channel: str) -> list[dict]:
        """Read all autorenewal-bot log entries posted to the log channel today."""
        midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        entries = []
        try:
            result = self.client.conversations_history(
                channel=log_channel,
                oldest=str(midnight.timestamp()),
                limit=200,
            )
            for msg in result.get("messages", []):
                text = msg.get("text", "")
                if text.startswith(_LOG_PREFIX):
                    try:
                        payload = json.loads(text[len(_LOG_PREFIX):].strip())
                        entries.append(payload)
                    except json.JSONDecodeError:
                        continue
        except SlackApiError as e:
            print(f"[slack] Failed to read log channel: {e.response['error']}")
        return entries

    def post_aggregated_summary(self, recipient: str, entries: list[dict]) -> None:
        """Post a single aggregated daily summary as a DM (or channel)."""
        today = datetime.now().strftime("%b %-d")

        if not entries:
            text = f":robot_face: *AutoRenewal Bot — {today}*\nNo runs reported yet today."
        else:
            all_succeeded = sum(len(e.get("succeeded", [])) for e in entries)
            all_failed = sum(len(e.get("failed", [])) for e in entries)
            lines = [f":robot_face: *AutoRenewal Bot — Daily Summary ({today})*"]

            renewed_lines = []
            failed_lines = []
            nothing_lines = []
            for e in entries:
                user = e.get("username", "unknown")
                succeeded = e.get("succeeded", [])
                failed = e.get("failed", [])
                if not succeeded and not failed:
                    nothing_lines.append(f"`{user}`")
                else:
                    if succeeded:
                        perms = ", ".join(succeeded)
                        renewed_lines.append(f"  • `{user}`: {perms}")
                    for f in failed:
                        row = f.get("row") or "(unknown)"
                        err = f.get("error", "")
                        failed_lines.append(f"  • `{user}`: {row} — {err}")

            if renewed_lines:
                lines.append(f":white_check_mark: *{all_succeeded} renewed:*\n" + "\n".join(renewed_lines))
            if failed_lines:
                lines.append(f":x: *{all_failed} failed:*\n" + "\n".join(failed_lines))
            if nothing_lines:
                lines.append(f":zzz: Nothing expiring for: {', '.join(nothing_lines)}")

            text = "\n".join(lines)

        try:
            self.client.chat_postMessage(channel=recipient, text=text, mrkdwn=True)
            print(f"[slack] Posted aggregated summary to {recipient}")
        except SlackApiError as e:
            print(f"[slack] Failed to post aggregated summary: {e.response['error']}")
