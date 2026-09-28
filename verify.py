"""
Verification gate. Nothing sends unless everything here passes.

Every check returns a (passed: bool, message: str) pair so a failure is
always traceable to a specific reason.
"""

import re
from typing import List, Tuple
from urllib.parse import urlparse

import requests

import config
from data_sources import Recipient, WeeklyContent

CheckResult = Tuple[bool, str]


def check_recipient_count(recipients: List[Recipient]) -> CheckResult:
    n = len(recipients)
    if n < config.MIN_EXPECTED_RECIPIENTS:
        return False, f"Recipient count too low ({n}) — likely a broken data pull."
    if n > config.MAX_EXPECTED_RECIPIENTS:
        return False, f"Recipient count implausibly high ({n}) — check for duplicates."
    return True, f"Recipient count OK ({n})."


def check_recipient_emails(recipients: List[Recipient]) -> CheckResult:
    bad = [r.email for r in recipients if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", r.email)]
    if bad:
        preview = ", ".join(bad[:5])
        return False, f"{len(bad)} malformed email(s) found, e.g.: {preview}"
    return True, "All recipient emails look well-formed."


def check_content_fields_present(content: WeeklyContent) -> CheckResult:
    missing = []
    for field in (
        "hook", "insight_paragraph", "closing_line", "source_study",
        "hero_stat_value", "hero_stat_label",
    ):
        if not getattr(content, field, "").strip():
            missing.append(field)
    if not content.supporting_points:
        missing.append("supporting_points")
    if missing:
        return False, f"Missing content fields: {', '.join(missing)}"
    return True, "All content fields present."


def _full_body_text(content: WeeklyContent) -> str:
    return " ".join(
        [content.hook, content.insight_paragraph, *content.supporting_points,
         content.closing_line, content.hero_stat_label]
    )


def check_word_count(content: WeeklyContent) -> CheckResult:
    text = _full_body_text(content)
    count = len(text.split())
    if count < config.MIN_WORD_COUNT:
        return False, f"Draft is only {count} words — too short for a proper 2 minute read (min {config.MIN_WORD_COUNT})."
    if count > config.MAX_WORD_COUNT:
        return False, f"Draft is {count} words — too long for a 2 minute read (max {config.MAX_WORD_COUNT})."
    return True, f"Word count OK ({count} words)."


def check_house_style_text(text: str) -> CheckResult:
    """
    The actual check, independent of content shape: no hyphens/em dashes,
    no AI-sounding stock phrases. Matches your stated copy preferences.
    Shared by every content type -- check_house_style() below wraps it
    for WeeklyContent, and whats_new.py's checks call it directly against
    WhatsNewContent.full_text().
    """
    violations = []

    # Em dash, and hyphens used as a dash (surrounded by spaces), not
    # ordinary hyphenated words like "non-obvious".
    if "—" in text or "–" in text:
        violations.append("em dash or en dash character found")
    if re.search(r"\s-\s", text):
        violations.append("hyphen used as a dash")

    lowered = text.lower()
    found_phrases = [p for p in config.BANNED_PHRASES if p in lowered]
    if found_phrases:
        violations.append(f"banned phrase(s): {', '.join(found_phrases)}")

    if violations:
        return False, "House style violation(s): " + "; ".join(violations)
    return True, "House style check passed."


def check_house_style(content: WeeklyContent) -> CheckResult:
    return check_house_style_text(_full_body_text(content))


def check_links(html: str, timeout_seconds: int = 8) -> CheckResult:
    urls = re.findall(r'href="([^"]+)"', html)
    broken = []
    for url in urls:
        if url.startswith("mailto:") or url.startswith("{{"):
            continue
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            broken.append((url, "not a valid absolute URL"))
            continue
        try:
            resp = requests.head(url, allow_redirects=True, timeout=timeout_seconds)
            if resp.status_code >= 400:
                broken.append((url, f"status {resp.status_code}"))
        except requests.RequestException as exc:
            broken.append((url, str(exc)))
    if broken:
        detail = "; ".join(f"{u} ({reason})" for u, reason in broken[:5])
        return False, f"{len(broken)} broken link(s): {detail}"
    return True, f"All {len(urls)} link(s) resolved." if urls else "No links to check."


def check_whats_new_fields(content) -> CheckResult:
    """Duck-typed on purpose (no import of whats_new.WhatsNewContent here,
    to avoid verify.py depending on every content module) -- just checks
    the pieces a recipient would actually notice if left blank."""
    missing = []
    for field in ("subject", "headline_line1", "headline_line2_italic", "tagline", "signoff"):
        if not getattr(content, field, "").strip():
            missing.append(field)
    if not content.intro_paragraphs:
        missing.append("intro_paragraphs")
    if not content.sections:
        missing.append("sections")
    for i, s in enumerate(content.sections):
        if not s.heading.strip() or not s.paragraphs:
            missing.append(f"sections[{i}]")
    if not content.qualitative.items:
        missing.append("qualitative.items")
    if not content.pricing.tiers:
        missing.append("pricing.tiers")
    if missing:
        return False, f"Missing content fields: {', '.join(missing)}"
    return True, "All content fields present."


def run_whats_new_checks(content, rendered_html: str) -> List[CheckResult]:
    """The whats_new.py equivalent of run_content_checks() -- no word-count
    bound (this is a multi-section product update, not a 2 minute read)."""
    return [
        check_whats_new_fields(content),
        check_house_style_text(content.full_text()),
        check_links(rendered_html),
    ]


def run_content_checks(content: WeeklyContent, rendered_html: str) -> List[CheckResult]:
    """Everything about the email itself, independent of who it goes to.
    test_send.py runs just these, since a team list is deliberately far
    below MIN_EXPECTED_RECIPIENTS."""
    return [
        check_content_fields_present(content),
        check_word_count(content),
        check_house_style(content),
        check_links(rendered_html),
    ]


def run_all_checks(
    recipients: List[Recipient], content: WeeklyContent, rendered_html: str
) -> Tuple[bool, List[CheckResult]]:
    checks = [
        check_recipient_count(recipients),
        check_recipient_emails(recipients),
        *run_content_checks(content, rendered_html),
    ]
    overall = all(passed for passed, _ in checks)
    return overall, checks
