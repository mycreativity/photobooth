"""Email sending via SMTP (AhaSend)."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from api.config import settings

logger = logging.getLogger(__name__)


def send_otp_email(to_email: str, code: str, magic_link: str) -> bool:
    """Send an OTP code + magic link via SMTP.

    Args:
        to_email: Recipient email address.
        code: 6-digit OTP code.
        magic_link: Full magic link URL.

    Returns:
        True if sent successfully.
    """
    subject = f"Photobooth Login Code: {code}"

    html_body = f"""\
    <div style="font-family: -apple-system, sans-serif; max-width: 400px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #1a1a1a; margin-bottom: 8px;">📸 Photobooth Login</h2>
        <p style="color: #555; font-size: 16px;">Je login code is:</p>
        <div style="background: #f5f5f5; border-radius: 12px; padding: 24px; text-align: center; margin: 24px 0;">
            <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #1a1a1a;">{code}</span>
        </div>
        <p style="color: #555; font-size: 14px;">Of klik op de link:</p>
        <a href="{magic_link}"
           style="display: block; background: #7c3aed; color: white; text-decoration: none;
                  padding: 14px 24px; border-radius: 8px; text-align: center; font-weight: 600;
                  font-size: 16px; margin: 16px 0;">
            Inloggen →
        </a>
        <p style="color: #999; font-size: 12px; margin-top: 24px;">
            Deze code is 5 minuten geldig. Heb je dit niet aangevraagd? Negeer deze email.
        </p>
    </div>
    """

    text_body = f"Je Photobooth login code: {code}\n\nOf gebruik deze link: {magic_link}\n\nGeldig voor 5 minuten."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_pass)
            smtp.send_message(msg)
        logger.info("OTP email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send OTP email to %s: %s", to_email, e)
        return False
