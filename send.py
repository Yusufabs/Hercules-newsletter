"""
Main entry point. Run this weekly via the GitHub Actions workflow in
.github/workflows/send-newsletter.yml (see README.md).

    python send.py

Behavior is controlled entirely by config.py / environment variables:
- NEWSLETTER_DATA_SOURCE=api|sample
- NEWSLETTER_DRY_RUN=true|false

Every run that gets past verification writes a delivery report to
logs/: one row per recipient saying who they are and whether the send
to them succeeded. See _open_delivery_report() below.
"""

import csv
import datetime as dt
import json
import os
import sys

import config
import data_sources
import render
import verify
import esp

# Per-recipient send statuses written to the delivery report.
STATUS_SENT = "sent"                  # accepted by the ESP for delivery
STATUS_FAILED = "failed"              # ESP rejected it or the request errored
STATUS_DRY_RUN = "dry_run_not_sent"   # would have been sent; dry run sends nothing


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
    hercules_count = sum(1 for r in recipients if r.source == "hercules")
    personnel_count = sum(1 for r in recipients if r.source == "personnel_csv")
    log(f"Pulled {len(recipients)} recipients ({hercules_count} hercules.works, "
        f"{personnel_count} top-level personnel) and this week's approved content.")

    # 2. Render (using the first recipient's variant as a representative
    #    sample for the link-check pass; each recipient still gets their
    #    own personalized render at send time below)
    if not recipients:
        log("ABORTED — no recipients to render a sample for.")
        return 1
    sample_html = render.render_email(recipients[0], content)
    log(f"CTA link: {render.cta_url(content)}")

    # 3. Verify — nothing below this line runs if any check fails
    passed, results = verify.run_all_checks(recipients, content, sample_html)
    for ok, message in results:
        log(f"{'PASS' if ok else 'FAIL'} — {message}")
    if not passed:
        log("ABORTED — one or more verification checks failed. No emails sent.")
        return 1

    # 4. Send (or simulate, in dry run)
    subject = render.render_subject(content)
    report_path, sent_count, failed = send_to_all(recipients, content, subject)

    if config.DRY_RUN:
        log(f"DRY RUN complete — would have sent to {len(recipients)} recipient(s). "
            f"Subject: \"{subject}\"")
    else:
        log(f"Send complete — {sent_count} sent, {len(failed)} failed.")
        for email, reason in failed[:10]:
            log(f"  FAILED: {email} — {reason}")
        if sent_count > 0:
            _archive_sent_content()

    # 5. Machine-readable run summary
    summary = {
        "timestamp": dt.datetime.now().isoformat(),
        "dry_run": config.DRY_RUN,
        "subject": subject,
        "cta_url": render.cta_url(content),
        "recipient_count": len(recipients),
        "hercules_recipient_count": hercules_count,
        "personnel_recipient_count": personnel_count,
        "dormant_count": sum(1 for r in recipients if r.is_dormant),
        "sent_count": 0 if config.DRY_RUN else sent_count,
        "failed_count": len(failed),
        "delivery_report": report_path,
    }
    with open(os.path.join(config.LOG_DIR, "last_run_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    _write_github_step_summary(summary)

    return 1 if failed else 0


def send_to_all(recipients, content, subject, report_tag="", render_email=None):
    """
    Renders and sends to every recipient, recording each outcome in the
    delivery report as it happens so the report survives a mid-run crash.
    Shared by this file's real send (always the weekly renderer) and
    test_send.py's team sends (weekly or whats_new, via render_email), so
    a test exercises exactly the code path a real send uses.

    Returns (report_path, sent_count, failed) where failed is a list of
    (email, reason) pairs.
    """
    render_email = render_email or render.render_email
    sent_count = 0
    failed = []
    report_path, report_file, writer = _open_delivery_report(report_tag)
    with report_file:
        for recipient in recipients:
            html = render_email(recipient, content)
            try:
                esp.send_email(recipient.email, recipient.name, subject, html)
                status, error = (STATUS_DRY_RUN if config.DRY_RUN else STATUS_SENT), ""
                sent_count += 1
            except esp.ESPError as exc:
                status, error = STATUS_FAILED, str(exc)
                failed.append((recipient.email, error))
            writer.writerow({
                "email": recipient.email,
                "name": recipient.name,
                "audience": recipient.source,
                "segment": "dormant" if recipient.is_dormant else "active",
                "status": status,
                "error": error,
            })
            report_file.flush()
    log(f"Delivery report written to {report_path}")
    return report_path, sent_count, failed


def _open_delivery_report(report_tag=""):
    """
    Opens logs/delivery_report_<timestamp>[_<tag>][_dryrun].csv -- the answer to
    "who did this issue go out to, and did it work for each of them?".
    It holds recipient emails, so it lives in logs/ (gitignored) and
    leaves GitHub only as the run's uploaded artifact, never in a commit.

    "sent" means SendGrid accepted the message for delivery. A later
    bounce (bad mailbox, full inbox) only shows up in SendGrid's own
    activity/bounce views, not here.
    """
    os.makedirs(config.LOG_DIR, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    suffix = (f"_{report_tag}" if report_tag else "") + ("_dryrun" if config.DRY_RUN else "")
    path = os.path.join(config.LOG_DIR, f"delivery_report_{stamp}{suffix}.csv")
    f = open(path, "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=["email", "name", "audience", "segment", "status", "error"])
    writer.writeheader()
    return path, f, writer


def _write_github_step_summary(summary: dict) -> None:
    """Counts only (no emails) on the Actions run page, so you can see how
    a send went at a glance. The full list is in the run's artifact."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    heading = "Dry run: nothing was sent" if summary["dry_run"] else "Newsletter sent"
    delivered_label = "Would have sent" if summary["dry_run"] else "Sent successfully"
    delivered = summary["recipient_count"] - summary["failed_count"] if summary["dry_run"] else summary["sent_count"]
    lines = [
        f"## {heading}",
        "",
        f"**Subject:** {summary['subject']}",
        "",
        "| | Count |",
        "|---|---|",
        f"| Total recipients | {summary['recipient_count']} |",
        f"| hercules.works users | {summary['hercules_recipient_count']} |",
        f"| Top-level personnel (CSV) | {summary['personnel_recipient_count']} |",
        f"| {delivered_label} | {delivered} |",
        f"| Failed | {summary['failed_count']} |",
        "",
        "Full per-recipient list: download the **newsletter-run-log** artifact "
        "below and open `delivery_report_*.csv`.",
    ]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


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


if __name__ == "__main__":
    sys.exit(main())
