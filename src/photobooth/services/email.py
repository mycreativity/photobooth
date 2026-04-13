"""Email delivery service.

Uses Python's built-in ``smtplib`` — no external dependencies.
Sends photos as JPEG attachments via any SMTP provider (Gmail,
SendGrid, Mailgun, etc.).

All sending is done in a background thread so the UI never blocks.
"""

from __future__ import annotations

import logging
import smtplib
import threading
from email.message import EmailMessage
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from photobooth.config import EmailConfig

logger = logging.getLogger(__name__)


class EmailService:
    """Sends photos via SMTP email."""

    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.enabled and bool(self._config.smtp_user)

    def send_photos(
        self,
        to_address: str,
        photos: list[bytes],
        event_name: str = "",
        callback=None,
    ) -> None:
        """Send photos to an email address in a background thread.

        Args:
            to_address: Recipient email address.
            photos: List of JPEG byte buffers to attach.
            event_name: Optional event name for the subject line.
            callback: Optional callable(success: bool) called on completion.
        """
        if not self.enabled:
            logger.warning("Email not configured — skipping send")
            if callback:
                callback(False)
            return

        threading.Thread(
            target=self._do_send,
            args=(to_address, photos, event_name, callback),
            name="email-send",
            daemon=True,
        ).start()

    def _do_send(
        self,
        to_address: str,
        photos: list[bytes],
        event_name: str,
        callback,
    ) -> None:
        """Background thread: compose and send the email."""
        cfg = self._config
        try:
            msg = EmailMessage()
            subject = cfg.subject
            if event_name:
                subject = f"{subject} — {event_name}"
            msg["Subject"] = subject
            msg["From"] = cfg.from_address or cfg.smtp_user
            msg["To"] = to_address
            msg.set_content(
                "Here are your photobooth photos!\n\n"
                "Thanks for joining the fun!\n"
            )

            # Attach each photo
            for i, jpeg_data in enumerate(photos, 1):
                if jpeg_data:
                    msg.add_attachment(
                        jpeg_data,
                        maintype="image",
                        subtype="jpeg",
                        filename=f"photo_{i}.jpg",
                    )

            # Send via SMTP
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(cfg.smtp_user, cfg.smtp_password)
                server.send_message(msg)

            logger.info("Email sent to %s (%d photos)", to_address, len(photos))
            if callback:
                callback(True)

        except Exception as e:
            logger.error("Email send failed to %s: %s", to_address, e)
            if callback:
                callback(False)
