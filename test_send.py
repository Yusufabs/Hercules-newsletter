"""
Team test sends: put the current draft in real inboxes before it goes
anywhere near real recipients.

    python3 test_send.py                      # preview only: who it'd go to + rendered HTML, sends nothing
    python3 test_send.py --send               # actually send to everyone in test_recipients.json
    python3 test_send.py --send --only you@hercules.works
    python3 test_send.py --send --cta-url "https://hercules.works/?utm_source=newsletter&utm_campaign=test"
    python3 test_send.py --kind whats_new --send   # send the "What's New" product-update campaign instead

Recipients come ONLY from config.TEST_RECIPIENTS_PATH (a list you
control, gitignored). This script never calls the hercules.works pull or
reads the personnel CSV, and refuses to run if any address is outside
config.TEST_ALLOWED_DOMAINS. Subjects are prefixed "[TEST] ", nothing is
archived to content/sent/, and the delivery report is tagged "_test".
See TESTING.md for what to check once the emails land.

--kind selects which content module drives the send: "weekly" (default)
is the single-stat research newsletter (data_sources.py / render.py /
template.html); "whats_new" is the multi-section product-update campaign
(whats_new.py / template_whats_new.html). Both go through the exact same
team-only safety rails below.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

import config
import data_sources
import render
import send
import verify
import whats_new
from data_sources import Recipient

_SEGMENTS = ("active", "dormant")

# One entry per content type test_send.py can drive, so the loading,
# rendering, and CTA logic for each stays in its own module (data_sources
# + render for "weekly", whats_new.py for "whats_new") and this file only
# wires the right functions together.
_CAMPAIGNS = {
    "weekly": {
        "load_content": data_sources.get_weekly_content,
        "render_email": render.render_email,
        "subject": render.render_subject,
        "run_checks": verify.run_content_checks,
        "describe_ctas": lambda content: f"CTA link: {render.cta_url(content)}",
        "override_cta": lambda content, url: setattr(content, "cta_url", url),
    },
    "whats_new": {
        "load_content": whats_new.get_whats_new_content,
        "render_email": whats_new.render_whats_new_email,
        "subject": whats_new.render_subject,
        "run_checks": verify.run_whats_new_checks,
        "describe_ctas": lambda content: "CTA links: " + ", ".join(dict.fromkeys(
            [s.cta_url for s in content.sections if s.cta_url]
            + [content.qualitative.cta_url, content.pricing.cta_url]
        )),
        "override_cta": lambda content, url: content.override_ctas(url),
    },
}


class TestListError(Exception):
    pass


def load_team(only=None):
    try:
        with open(config.TEST_RECIPIENTS_PATH, encoding="utf-8") as f:
            rows = json.load(f)
    except FileNotFoundError:
        raise TestListError(
            f"No team list at {config.TEST_RECIPIENTS_PATH}. Copy "
            f"sample_data/test_recipients.example.json there and fill in your team."
        )

    if not config.TEST_ALLOWED_DOMAINS:
        raise TestListError(
            "TEST_ALLOWED_DOMAINS is empty. Set it (e.g. in .env: "
            "TEST_ALLOWED_DOMAINS=hercules.works) so a test can never reach "
            "an address outside your team."
        )

    team, problems = [], []
    for row in rows:
        email = (row.get("email") or "").strip()
        segment = (row.get("segment") or "active").strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            problems.append(f"malformed email: {email!r}")
            continue
        if email.split("@", 1)[1].lower() not in config.TEST_ALLOWED_DOMAINS:
            problems.append(f"{email} is outside TEST_ALLOWED_DOMAINS ({', '.join(config.TEST_ALLOWED_DOMAINS)})")
            continue
        if segment not in _SEGMENTS:
            problems.append(f"{email}: segment must be one of {_SEGMENTS}, got {segment!r}")
            continue
        team.append(Recipient(
            email=email,
            name=(row.get("name") or "").strip(),
            last_login=dt.date.today(),
            is_dormant=(segment == "dormant"),
            source="team_test",
        ))
    if problems:
        # Refuse the whole run rather than silently skipping someone: a bad
        # row usually means the list itself is wrong.
        raise TestListError("Team list rejected:\n  " + "\n  ".join(problems))

    if only:
        wanted = {e.lower() for e in only}
        team = [r for r in team if r.email.lower() in wanted]
        missing = wanted - {r.email.lower() for r in team}
        if missing:
            raise TestListError(f"--only address(es) not in the team list: {', '.join(sorted(missing))}")

    if not team:
        raise TestListError("Team list is empty.")
    if len(team) > config.TEST_MAX_RECIPIENTS:
        raise TestListError(
            f"{len(team)} test recipients exceeds TEST_MAX_RECIPIENTS "
            f"({config.TEST_MAX_RECIPIENTS}). Is this really your team list?"
        )
    return team


def write_previews(team, content, render_email, tag=""):
    """One preview file per CTA variant actually being sent, so you can
    open exactly what each person got."""
    paths = []
    os.makedirs(config.LOG_DIR, exist_ok=True)
    suffix = f"_{tag}" if tag else ""
    for segment in _SEGMENTS:
        sample = next((r for r in team if r.is_dormant == (segment == "dormant")), None)
        if sample is None:
            continue
        path = os.path.join(config.LOG_DIR, f"test_preview{suffix}_{segment}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_email(sample, content))
        paths.append(path)
    return paths


def _missing_credential():
    """Which env var esp.py needs for config.ESP_PROVIDER, if it's unset.
    Mirrors esp.py's own per-provider checks so a test send fails here,
    before wasting a send attempt, rather than deep inside esp.py."""
    if config.ESP_PROVIDER == "gmail_smtp":
        return "GMAIL_APP_PASSWORD is not set" if not config.GMAIL_APP_PASSWORD else None
    if config.ESP_PROVIDER in ("sendgrid", "brevo"):
        return "ESP_API_KEY is not set" if not config.ESP_API_KEY else None
    return None  # unknown provider: let esp.py's own error surface per-recipient


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Send the current draft to your team only.")
    parser.add_argument("--kind", choices=sorted(_CAMPAIGNS), default="weekly",
                        help="Which content type to send: 'weekly' (single-stat research "
                             "newsletter, default) or 'whats_new' (product-update campaign).")
    parser.add_argument("--send", action="store_true",
                        help="Actually send. Without this, only previews and lists recipients.")
    parser.add_argument("--only", action="append", metavar="EMAIL",
                        help="Limit to these team members (repeatable).")
    parser.add_argument("--cta-url",
                        help="Override every CTA link for this test only, so team clicks "
                             "don't count toward the real campaign's UTM tags.")
    parser.add_argument("--allow-failing-checks", action="store_true",
                        help="Send even if content checks fail (to test layout on a draft "
                             "that isn't final). Never available for real sends.")
    args = parser.parse_args(argv)
    campaign = _CAMPAIGNS[args.kind]

    config.DRY_RUN = not args.send
    send.log(f"Starting TEST run. kind={args.kind} send={args.send} team_list={config.TEST_RECIPIENTS_PATH}")

    try:
        team = load_team(args.only)
        content = campaign["load_content"]()
    except (TestListError, OSError, ValueError, KeyError) as exc:
        send.log(f"TEST ABORTED — {exc}")
        return 1
    if args.cta_url:
        campaign["override_cta"](content, args.cta_url.strip())
    send.log(f"Team: {len(team)} recipient(s) — " + ", ".join(
        f"{r.email} ({'dormant' if r.is_dormant else 'active'})" for r in team))
    send.log(campaign["describe_ctas"](content))

    preview_tag = "" if args.kind == "weekly" else args.kind
    for path in write_previews(team, content, campaign["render_email"], tag=preview_tag):
        send.log(f"Preview written to {path}")

    results = campaign["run_checks"](content, campaign["render_email"](team[0], content))
    for ok, message in results:
        send.log(f"{'PASS' if ok else 'FAIL'} — {message}")
    if not all(ok for ok, _ in results):
        if not args.allow_failing_checks:
            send.log("TEST ABORTED — content checks failed (a real send would be blocked too). "
                     "Fix the draft, or rerun with --allow-failing-checks to test layout anyway.")
            return 1
        send.log("Content checks failed, continuing because --allow-failing-checks was given.")

    if args.send:
        missing_cred = _missing_credential()
        if missing_cred:
            send.log(f"TEST ABORTED — {missing_cred} (add it to .env).")
            return 1

    subject = config.TEST_SUBJECT_PREFIX + campaign["subject"](content)
    report_path, sent_count, failed = send.send_to_all(
        team, content, subject, report_tag=f"test_{args.kind}" if args.kind != "weekly" else "test",
        render_email=campaign["render_email"],
    )

    if args.send:
        send.log(f"TEST send complete — {sent_count} sent, {len(failed)} failed. Subject: \"{subject}\"")
        for email, reason in failed:
            send.log(f"  FAILED: {email} — {reason}")
    else:
        send.log(f"TEST preview only — nothing sent. Rerun with --send to deliver to "
                 f"these {len(team)} people.")

    with open(os.path.join(config.LOG_DIR, "last_test_summary.json"), "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": dt.datetime.now().isoformat(),
            "kind": args.kind,
            "sent": args.send,
            "subject": subject,
            "ctas": campaign["describe_ctas"](content),
            "recipient_count": len(team),
            "sent_count": sent_count if args.send else 0,
            "failed_count": len(failed),
            "failed": [{"email": e, "reason": r} for e, r in failed],
            "delivery_report": report_path,
        }, f, indent=2)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
