"""
Main entry point. Run this weekly via the GitHub Actions workflow in
.github/workflows/send-newsletter.yml (see README.md).

    python send.py

Behavior is controlled entirely by config.py / environment variables:
- NEWSLETTER_DATA_SOURCE=api|sample
- NEWSLETTER_DRY_RUN=true|false
"""

import datetime as dt
import json
import os
import sys

import config
import data_sources
import render
import verify
import esp


def log(message: str) -> None:
    os.makedirs(config.LOG_DIR, exist_ok=True)
    timestamp = dt.datetime.now().isoformat(timespec="seconds")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(os.path.join(config.LOG_DIR, "send_log.txt"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    log(f"Starting newsletter run. DATA_SOURCE_MODE={config.DATA_SOURCE_MODE} DRY_RUN={config.DRY_RUN}")

    # 1. Pull data
    try:
        recipients = data_sources.get_recipients()
        content = data_sources.get_weekly_content()
    except Exception as exc:
        log(f"ABORTED — data pull failed: {exc}")
        return 1
    log(f"Pulled {len(recipients)} recipients and this week's approved content.")

    # 2. Render (using the first recipient's variant as a representative
    #    sample for the link-check pass; each recipient still gets their
    #    own personalized render at send time below)
    if not recipients:
        log("ABORTED — no recipients to render a sample for.")
        return 1
    sample_html = render.render_email(recipients[0], content)

    # 3. Verify — nothing below this line runs if any check fails
    passed, results = verify.run_all_checks(recipients, content, sample_html)
    for ok, message in results:
        log(f"{'PASS' if ok else 'FAIL'} — {message}")
    if not passed:
        log("ABORTED — one or more verification checks failed. No emails sent.")
        return 1

    # 4. Send (or simulate, in dry run)
    subject = render.render_subject(content)
    sent_count = 0
    failed = []
    for recipient in recipients:
        html = render.render_email(recipient, content)
        try:
            esp.send_email(recipient.email, recipient.name, subject, html)
            sent_count += 1
        except esp.ESPError as exc:
            failed.append((recipient.email, str(exc)))

    if config.DRY_RUN:
        log(f"DRY RUN complete — would have sent to {len(recipients)} recipient(s). "
            f"Subject: \"{subject}\"")
    else:
        log(f"Send complete — {sent_count} sent, {len(failed)} failed.")
        if failed:
            for email, reason in failed[:10]:
                log(f"  FAILED: {email} — {reason}")
        if sent_count > 0:
            _archive_sent_content()


def _archive_sent_content() -> None:
    """Keeps a dated copy of what actually went out, since weekly_content.json
    gets overwritten by the next issue. Archive lives in git history too."""
    os.makedirs(config.SENT_ARCHIVE_DIR, exist_ok=True)
    date_stamp = dt.date.today().isoformat()
    archive_path = os.path.join(config.SENT_ARCHIVE_DIR, f"{date_stamp}.json")
    with open(config.WEEKLY_CONTENT_PATH, encoding="utf-8") as src:
        data = src.read()
    with open(archive_path, "w", encoding="utf-8") as dest:
        dest.write(data)
    log(f"Archived sent content to {archive_path}")

    # 5. Write a machine-readable run summary for the feedback-loop step
    summary = {
        "timestamp": dt.datetime.now().isoformat(),
        "dry_run": config.DRY_RUN,
        "recipient_count": len(recipients),
        "dormant_count": sum(1 for r in recipients if r.is_dormant),
        "subject": subject,
        "sent_count": sent_count,
        "failed_count": len(failed),
    }
    with open(os.path.join(config.LOG_DIR, "last_run_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
