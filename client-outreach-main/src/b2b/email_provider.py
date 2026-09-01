"""Email Provider Abstraction, Staged Console Provider, and Safe Outreach Sending Service.

Enforces strict human approval gatekeeper, quota protection, and full audit persistence in SQLite.
"""

from __future__ import annotations

import json
import logging
import smtplib
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, Optional

from b2b.gatekeeper import ApprovalGateError, OutreachGatekeeper
from b2b.models import (
    ApprovalStatus,
    BusinessRecord,
    BusinessStatus,
    FollowUpRecord,
    FollowUpStatus,
    OutreachRecord,
    SendStatus,
)
from config import PROJECT_ROOT, get_config

logger = logging.getLogger(__name__)


class BaseEmailProvider(ABC):
    """Abstract interface for outreach email delivery providers."""

    name: str = "base_email"

    @abstractmethod
    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_email: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Dispatch email and return delivery response metadata dictionary."""
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Check whether provider credentials and configurations are valid."""
        pass


class ConsoleEmailProvider(BaseEmailProvider):
    """Mock/Dry-Run email provider: logs to console and stores staged payloads in output/outreach_staged/."""

    name: str = "console_dry_run"

    def __init__(self, output_dir: Optional[Path | str] = None) -> None:
        if output_dir:
            self.staged_dir = Path(output_dir)
        else:
            self.staged_dir = PROJECT_ROOT / "output" / "outreach_staged"
        self.staged_dir.mkdir(parents=True, exist_ok=True)

    def validate_credentials(self) -> bool:
        return True

    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_email: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        msg_id = f"mock_msg_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        payload = {
            "message_id": msg_id,
            "provider": self.name,
            "to_email": to_email,
            "from_email": from_email or "outreach@automation.local",
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html,
            "sent_at": now_iso,
            "status": "delivered_mock",
            "extra": kwargs,
        }

        # Persist staged payload file
        out_file = self.staged_dir / f"{msg_id}.json"
        out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        logger.info("[MOCK EMAIL DELIVERED] ID=%s To=%s Subject=%s", msg_id, to_email, subject)
        return {
            "status": "success",
            "provider": self.name,
            "provider_message_id": msg_id,
            "staged_file": str(out_file),
            "sent_at": now_iso,
            "is_mock": True,
        }


class SMTPEmailProvider(BaseEmailProvider):
    """Real SMTP email provider when explicitly configured."""

    name: str = "smtp"

    def __init__(
        self,
        *,
        host: Optional[str] = None,
        port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        use_tls: bool = True,
    ) -> None:
        cfg = get_config().get("email", {})
        self.host = host or cfg.get("smtp_host", "smtp.gmail.com")
        self.port = int(port or cfg.get("smtp_port", 587))
        self.username = username or cfg.get("smtp_username", "")
        self.password = password or cfg.get("smtp_password", "")
        self.from_email = from_email or cfg.get("from_email", self.username)
        self.use_tls = use_tls

    def validate_credentials(self) -> bool:
        return bool(self.host and self.username and self.password)

    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_email: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self.validate_credentials():
            raise ValueError("SMTP credentials not configured (missing host, username, or password).")

        sender = from_email or self.from_email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email

        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(self.host, self.port, timeout=15) as server:
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.sendmail(sender, [to_email], msg.as_string())

        msg_id = f"smtp_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "status": "success",
            "provider": self.name,
            "provider_message_id": msg_id,
            "sent_at": now_iso,
            "is_mock": False,
        }


class OutreachSendingService:
    """Orchestrates human approval checks, quota guards, provider dispatch, and database updates."""

    def __init__(
        self,
        db: Any,
        *,
        provider: Optional[BaseEmailProvider] = None,
        gatekeeper: Optional[OutreachGatekeeper] = None,
        live: bool = False,
    ) -> None:
        self.db = db
        self.gatekeeper = gatekeeper or OutreachGatekeeper()
        self.live = live

        if provider is not None:
            self.provider = provider
        elif live:
            self.provider = SMTPEmailProvider()
        else:
            self.provider = ConsoleEmailProvider()

    def send_outreach(
        self,
        outreach_id: str,
        *,
        force_dry_run: bool = False,
        override_recipient: Optional[str] = None,
    ) -> OutreachRecord:
        """Safely send an outreach record after verifying human approval."""
        outreach = self.db.get_outreach(outreach_id)
        if outreach is None:
            raise ValueError(f"Outreach record not found: {outreach_id}")

        # 1. Mandatory Gatekeeper Check
        is_ok, reason = self.gatekeeper.can_send(outreach)
        if not is_ok:
            raise ApprovalGateError(f"Approval gate blocked outreach {outreach_id}: {reason}")

        # 2. Check for Test Delivery Mode override
        import os
        test_recipient = (override_recipient or os.getenv("TEST_EMAIL_RECIPIENT", "")).strip()
        is_test_mode = bool(test_recipient and test_recipient.lower() != outreach.recipient_email.lower())
        effective_to = test_recipient if test_recipient else outreach.recipient_email

        subject = outreach.subject
        body_text = outreach.body_text
        body_html = outreach.body_html

        if is_test_mode:
            banner = f"[TEST DELIVERY MODE — Intended Prospect: {outreach.recipient_email}]\n\n"
            subject = f"[TEST MODE] {subject}"
            body_text = banner + body_text
            if body_html:
                html_banner = (
                    f"<div style='background:#fef3c7;border:2px solid #f59e0b;padding:12px;margin-bottom:16px;border-radius:6px;font-family:sans-serif;color:#92400e;'>"
                    f"<strong>⚠️ TEST DELIVERY MODE</strong><br>"
                    f"Original Intended Recipient: <code>{outreach.recipient_email}</code><br>"
                    f"Delivered to Test Inbox: <code>{effective_to}</code>"
                    f"</div>"
                )
                body_html = html_banner + body_html

        # 3. Select effective provider
        if force_dry_run:
            active_provider = ConsoleEmailProvider()
        else:
            active_provider = self.provider

        try:
            res = active_provider.send_email(
                to_email=effective_to,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            sent_at = res.get("sent_at") or datetime.now(timezone.utc).isoformat()
            provider_msg_id = res.get("provider_message_id")

            # 4. Update Database Status
            updated = self.db.update_outreach_send_status(
                outreach_id,
                SendStatus.SENT,
                sent_at=sent_at,
                provider_message_id=provider_msg_id,
                last_error=None,
            )
            self.db.update_business_status(outreach.business_id, BusinessStatus.SENT)
            return updated
        except Exception as exc:
            logger.error("Outreach send failed for %s: %s", outreach_id, exc)
            self.db.update_outreach_send_status(
                outreach_id,
                SendStatus.FAILED,
                last_error=str(exc),
            )
            raise

    def send_followup(
        self,
        followup_id: str,
        *,
        force_dry_run: bool = False,
        override_recipient: Optional[str] = None,
    ) -> FollowUpRecord:
        """Safely send an approved follow-up record."""
        followup = self.db.get_followup(followup_id)
        if followup is None:
            raise ValueError(f"Follow-up record not found: {followup_id}")

        if followup.status != FollowUpStatus.APPROVED:
            raise ApprovalGateError(
                f"Follow-up {followup_id} cannot be sent: status is '{followup.status.value}', requires 'approved'."
            )

        outreach = self.db.get_outreach(followup.outreach_id)
        if outreach is None:
            raise ValueError(f"Parent outreach record not found: {followup.outreach_id}")

        if force_dry_run:
            active_provider = ConsoleEmailProvider()
        else:
            active_provider = self.provider

        effective_to = override_recipient.strip() if override_recipient else outreach.recipient_email

        try:
            res = active_provider.send_email(
                to_email=effective_to,
                subject=followup.subject,
                body_text=followup.body_text,
                body_html=followup.body_html,
            )
            sent_at = res.get("sent_at") or datetime.now(timezone.utc).isoformat()
            provider_msg_id = res.get("provider_message_id")

            updated = self.db.update_followup_status(
                followup_id,
                FollowUpStatus.SENT,
                sent_at=sent_at,
                provider_message_id=provider_msg_id,
                last_error=None,
            )
            return updated
        except Exception as exc:
            logger.error("Follow-up send failed for %s: %s", followup_id, exc)
            self.db.update_followup_status(
                followup_id,
                FollowUpStatus.PENDING_REVIEW,
                last_error=str(exc),
            )
            raise
