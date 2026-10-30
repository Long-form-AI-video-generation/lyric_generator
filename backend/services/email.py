"""Transactional email service supporting SMTP (Gmail/Custom) with Jinja2 templates."""
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
from jinja2 import Environment, FileSystemLoader

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Configure Jinja2 environment for email templates
templates_dir = settings.backend_dir / "templates" / "emails"
jinja_env = Environment(
    loader=FileSystemLoader(str(templates_dir)),
    autoescape=True,
)


def _send_via_smtp(to_email: str, subject: str, html_content: str, plain_text: str) -> bool:
    """Send email using standard SMTP (e.g. Gmail with App Password)."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.email_from or settings.smtp_user
        msg["To"] = to_email

        part1 = MIMEText(plain_text, "plain")
        part2 = MIMEText(html_content, "html")
        msg.attach(part1)
        msg.attach(part2)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, [to_email], msg.as_string())

        logger.info(f"[EMAIL SERVICE] Invite email successfully sent via SMTP to {to_email}")
        return True
    except Exception as exc:
        logger.error(f"[EMAIL SERVICE] Failed to send email via SMTP to {to_email}: {exc}", exc_info=True)
        return False


def send_invite_email(to_email: str, raw_token: str) -> bool:
    """Send an HTML invitation email via SMTP with plain-text fallback."""
    invite_url = f"{settings.frontend_base_url}/accept-invite?token={raw_token}"
    subject = "Your invitation to LyricVid Private Beta"

    template = jinja_env.get_template("invite.html")
    html_content = template.render(
        email=to_email,
        invite_url=invite_url,
    )

    plain_text = (
        f"You're invited to LyricVid Private Beta!\n\n"
        f"To accept your invitation and set your account password, open this link:\n"
        f"{invite_url}\n\n"
        f"This link expires in 7 days."
    )

    # Dispatch via SMTP if credentials are configured
    if settings.smtp_user and settings.smtp_password:
        return _send_via_smtp(to_email, subject, html_content, plain_text)

    # Development fallback: log link to console
    logger.warning(
        "[EMAIL SERVICE] SMTP credentials not configured in .env. Skipping email dispatch.\n"
        f"--> Intended recipient: {to_email}\n"
        f"--> Generated invite link: {invite_url}"
    )
    return False
