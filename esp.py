"""
Thin wrapper around the actual email-sending API. Isolated here so
switching providers (Gmail SMTP -> SendGrid -> Brevo -> Mailchimp ->
whatever) never touches render.py, verify.py, or send.py.

Provider choice: team test sends currently go through gmail_smtp --
your own Gmail/Google Workspace account, free, no signup, no domain
setup, just an app password (see TESTING.md). sendgrid is the intended
production provider (dropped its permanent free tier in May 2025) once
the real recipient API and personnel CSV are wired up. brevo is a free,
no-DNS-required alternative if gmail_smtp's sending limits (500-2000/day)
ever aren't enough for testing.
"""

import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

import requests

import config


class ESPError(Exception):
    pass


def send_email(to_email: str, to_name: str, subject: str, html_body: str) -> None:
    if config.DRY_RUN:
        # In dry run, we deliberately do not call any external API.
        # send.py logs what WOULD have been sent instead.
        return

    if config.ESP_PROVIDER == "gmail_smtp":
        _send_via_gmail_smtp(to_email, to_name, subject, html_body)
    elif config.ESP_PROVIDER == "sendgrid":
        _send_via_sendgrid(to_email, to_name, subject, html_body)
    elif config.ESP_PROVIDER == "brevo":
        _send_via_brevo(to_email, to_name, subject, html_body)
    elif config.ESP_PROVIDER == "mailchimp":
        raise NotImplementedError(
            "Mailchimp sending isn't wired up yet. Mailchimp's transactional "
            "flow (Mandrill) uses a different payload shape than SendGrid — "
            "implement _send_via_mailchimp() following SendGrid's pattern below."
        )
    else:
        raise ESPError(f"Unknown ESP_PROVIDER: {config.ESP_PROVIDER}")


_GMAIL_SMTP_HOST = "smtp.gmail.com"
_GMAIL_SMTP_PORT = 465  # implicit TLS ("SMTP over SSL")


def _send_via_gmail_smtp(to_email: str, to_name: str, subject: str, html_body: str) -> None:
    """
    Sends through your own Gmail/Google Workspace account. FROM_EMAIL
    must be the exact mailbox you're authenticating as (Gmail signs you
    in as yourself, it can't send "as" an unrelated address the way an
    ESP's verified sender can) -- for team testing this is just your own
    address, not newsletter@hercules.works. GMAIL_APP_PASSWORD is a
    16-character app password from myaccount.google.com/apppasswords,
    which requires 2-Step Verification to be turned on first; Google
    retired plain-password SMTP login in 2025.

    Sending limits (Google's, not this pipeline's): 500 recipients/day
    for a personal Gmail account, 2,000/day for Google Workspace -- both
    far above what a team test needs, and this is not meant for the real
    audience-wide send.
    """
    if not config.FROM_EMAIL or not config.GMAIL_APP_PASSWORD:
        raise ESPError(
            "FROM_EMAIL and GMAIL_APP_PASSWORD are both required for "
            "gmail_smtp -- see TESTING.md for how to generate an app "
            "password."
        )

    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((config.FROM_NAME, config.FROM_EMAIL))
    msg["To"] = formataddr((to_name, to_email)) if to_name else to_email

    try:
        with smtplib.SMTP_SSL(_GMAIL_SMTP_HOST, _GMAIL_SMTP_PORT, timeout=15) as server:
            server.login(config.FROM_EMAIL, config.GMAIL_APP_PASSWORD)
            server.sendmail(config.FROM_EMAIL, [to_email], msg.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise ESPError(
            f"Gmail SMTP login failed ({exc}) -- check FROM_EMAIL matches the "
            f"account the app password belongs to, and that the app password "
            f"itself is current (they're revoked if 2-Step Verification is "
            f"turned off)."
        ) from exc
    except smtplib.SMTPException as exc:
        raise ESPError(f"Gmail SMTP send failed: {exc}") from exc
    except OSError as exc:  # DNS/connection failures, not raised by smtplib itself
        raise ESPError(f"Gmail SMTP connection errored: {exc}") from exc


def _send_via_sendgrid(to_email: str, to_name: str, subject: str, html_body: str) -> None:
    if not config.ESP_API_KEY:
        raise ESPError("ESP_API_KEY is not set — cannot send via SendGrid.")

    payload = {
        "personalizations": [
            {"to": [{"email": to_email, "name": to_name}], "subject": subject}
        ],
        "from": {"email": config.FROM_EMAIL, "name": config.FROM_NAME},
        "content": [{"type": "text/html", "value": html_body}],
    }
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {config.ESP_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
    except requests.RequestException as exc:
        # Surface network errors as ESPError so send.py records this one
        # recipient as failed and keeps going, instead of crashing mid-list.
        raise ESPError(f"SendGrid request errored: {exc}") from exc
    if resp.status_code >= 300:
        raise ESPError(f"SendGrid send failed ({resp.status_code}): {resp.text}")


def _send_via_brevo(to_email: str, to_name: str, subject: str, html_body: str) -> None:
    if not config.ESP_API_KEY:
        raise ESPError("ESP_API_KEY is not set — cannot send via Brevo.")

    payload = {
        "sender": {"email": config.FROM_EMAIL, "name": config.FROM_NAME},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_body,
    }
    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": config.ESP_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise ESPError(f"Brevo request errored: {exc}") from exc
    if resp.status_code >= 300:
        # Brevo's most common rejection here is an unverified FROM_EMAIL --
        # the sender must be verified in the Brevo dashboard first (an
        # emailed link/OTP, no DNS needed). The response body says which.
        raise ESPError(f"Brevo send failed ({resp.status_code}): {resp.text}")
