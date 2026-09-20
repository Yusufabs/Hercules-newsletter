"""
Thin wrapper around the actual email-sending API. Isolated here so
switching providers (SendGrid -> Mailchimp -> Postmark -> whatever)
never touches render.py, verify.py, or send.py.
"""

import requests

import config


class ESPError(Exception):
    pass


def send_email(to_email: str, to_name: str, subject: str, html_body: str) -> None:
    if config.DRY_RUN:
        # In dry run, we deliberately do not call any external API.
        # send.py logs what WOULD have been sent instead.
        return

    if config.ESP_PROVIDER == "sendgrid":
        _send_via_sendgrid(to_email, to_name, subject, html_body)
    elif config.ESP_PROVIDER == "mailchimp":
        raise NotImplementedError(
            "Mailchimp sending isn't wired up yet. Mailchimp's transactional "
            "flow (Mandrill) uses a different payload shape than SendGrid — "
            "implement _send_via_mailchimp() following SendGrid's pattern below."
        )
    else:
        raise ESPError(f"Unknown ESP_PROVIDER: {config.ESP_PROVIDER}")


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
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {config.ESP_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    if resp.status_code >= 300:
        raise ESPError(f"SendGrid send failed ({resp.status_code}): {resp.text}")
