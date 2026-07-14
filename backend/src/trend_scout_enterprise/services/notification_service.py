"""Notification service for email and Teams webhook."""

from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.encryption import decrypt_dict, encrypt_dict
from trend_scout_enterprise.models.models import ScanRun
from trend_scout_enterprise.models.schedule import NotificationChannel, NotificationLog


class NotificationService:
    """Service for sending scan-related notifications."""

    def __init__(self, db: Session):
        self.db = db

    def _send_email(self, channel: NotificationChannel, subject: str, body: str) -> None:
        """Send email via SMTP (best-effort)."""
        import smtplib
        from email.mime.text import MIMEText

        config = self._decrypt_config(channel)
        smtp_host = config.get("smtp_host", "smtp.gmail.com")
        smtp_port = config.get("smtp_port", 587)
        username = config.get("username", "")
        password = config.get("password", "")
        to_address = config.get("to_address", "")

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = username
        msg["To"] = to_address

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if username and password:
                server.login(username, password)
            server.send_message(msg)

    def _send_teams_card(self, channel: NotificationChannel, title: str, text: str, color: str = "0078D4") -> None:
        """Send adaptive card to Microsoft Teams webhook."""
        config = self._decrypt_config(channel)
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            raise ValueError("Teams webhook URL is required")

        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": color,
            "summary": title,
            "sections": [
                {
                    "activityTitle": title,
                    "activitySubtitle": datetime.now(timezone.utc).isoformat(),
                    "facts": [{"name": "Status", "value": text}],
                    "markdown": True,
                }
            ],
        }
        response = httpx.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()

    def _decrypt_config(self, channel: NotificationChannel) -> dict[str, Any]:
        return decrypt_dict(channel.config_encrypted) if channel.config_encrypted else {}

    def _should_notify(self, channel: NotificationChannel, scan_run: ScanRun) -> bool:
        if not channel.is_enabled:
            return False
        if scan_run.status == "completed" and not channel.on_scan_success:
            return False
        if scan_run.status != "completed" and not channel.on_scan_failure:
            return False
        return True

    def notify_scan_run(self, scan_run: ScanRun) -> None:
        """Send notifications for a scan run to all enabled channels in the workspace."""
        workspace_id = getattr(scan_run, "workspace_id", None) or getattr(scan_run.source, "workspace_id", None)
        channels = (
            self.db.query(NotificationChannel)
            .filter(NotificationChannel.workspace_id == workspace_id)
            .all()
        )
        for channel in channels:
            if not self._should_notify(channel, scan_run):
                continue
            log = NotificationLog(
                id=self._new_id(),
                channel_id=channel.id,
                scan_run_id=scan_run.id,
                status="pending",
            )
            self.db.add(log)
            self.db.commit()
            try:
                subject = f"Scan {'succeeded' if scan_run.status == 'completed' else 'failed'}: {scan_run.source.name}"
                body = f"Scan for source {scan_run.source.name} finished with status {scan_run.status}.\n"
                if scan_run.suggested_fix:
                    body += f"Suggested fix: {scan_run.suggested_fix}"
                if channel.channel_type == "email":
                    self._send_email(channel, subject, body)
                elif channel.channel_type == "teams_webhook":
                    self._send_teams_card(channel, subject, body)
                log.status = "sent"
            except Exception as exc:
                log.status = "failed"
                log.error_message = str(exc)
            self.db.commit()

    def _new_id(self) -> str:
        from uuid import uuid4

        return uuid4().hex

    def create_channel(self, owner_id: str, channel_type: str, name: str, config: dict, on_success: bool, on_failure: bool, workspace_id: str | None = None) -> NotificationChannel:
        from uuid import uuid4

        channel = NotificationChannel(
            id=uuid4().hex,
            workspace_id=workspace_id,
            owner_id=owner_id,
            channel_type=channel_type,
            name=name,
            config_encrypted=encrypt_dict(config),
            is_enabled=1,
            on_scan_success=1 if on_success else 0,
            on_scan_failure=1 if on_failure else 0,
        )
        self.db.add(channel)
        self.db.commit()
        self.db.refresh(channel)
        return channel

    def list_channels(self, owner_id: str | None = None, workspace_id: str | None = None) -> list[NotificationChannel]:
        q = self.db.query(NotificationChannel)
        if workspace_id is not None:
            q = q.filter(NotificationChannel.workspace_id == workspace_id)
        elif owner_id is not None:
            q = q.filter(NotificationChannel.owner_id == owner_id)
        return q.all()

    def delete_channel(self, owner_id: str | None = None, channel_id: str | None = None, workspace_id: str | None = None) -> None:
        if channel_id is None:
            raise ValueError("channel_id is required")
        channel = self.db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
        if channel and workspace_id is not None and channel.workspace_id != workspace_id:
            channel = None
        if not channel:
            raise ValueError("Notification channel not found")
        self.db.delete(channel)
        self.db.commit()
