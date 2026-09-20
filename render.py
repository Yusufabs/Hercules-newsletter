"""
Merges a WeeklyContent object and a single Recipient into a finished HTML
email and a subject line.
"""

import config
import illustrations
from data_sources import Recipient, WeeklyContent

TEMPLATE_PATH = "template.html"

ACTIVE_CTA_LABEL = "Run your next study"
DORMANT_CTA_LABEL = "See what's new since you left"
BASE_CTA_URL = "https://hercules.works/"
UNSUBSCRIBE_URL_TEMPLATE = "https://hercules.works/?unsub={email}"
# NOTE: these point at the root domain as a resolvable placeholder. Swap
# them for the real dashboard/unsubscribe endpoints once they exist -- the
# link checker in verify.py will fail loudly if a URL doesn't resolve.


def _load_template() -> str:
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


def _supporting_points_html(points: list) -> str:
    rows = "".join(
        f'''<tr>
          <td style="padding:0 0 12px 0;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#fafafe; border-radius:8px;">
              <tr>
                <td width="6" style="background-color:{config.BRAND_ACCENT_COLOR}; border-radius:8px 0 0 8px;">&nbsp;</td>
                <td style="padding:12px 16px; color:#333333; font-size:15px; line-height:1.55;">{p}</td>
              </tr>
            </table>
          </td>
        </tr>'''
        for p in points
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>'


def _hero_illustration_html(content: WeeklyContent) -> str:
    if config.ILLUSTRATION_MODE == "brand_asset":
        alt_text = content.hero_stat_label or content.hook
        return illustrations.render_brand_asset_illustration(
            config.BRAND_ILLUSTRATION_ASSET_URL, alt_text
        )
    return illustrations.render_placeholder_illustration(
        content.hero_stat_value, content.hero_stat_label, config.BRAND_ACCENT_COLOR
    )


def render_subject(content: WeeklyContent) -> str:
    # The subject line IS the hook. No "Weekly Update #12" filler.
    return content.hook


def render_email(recipient: Recipient, content: WeeklyContent) -> str:
    html = _load_template()
    cta_label = DORMANT_CTA_LABEL if recipient.is_dormant else ACTIVE_CTA_LABEL

    replacements = {
        "{{HOOK}}": content.hook,
        "{{HERO_ILLUSTRATION_HTML}}": _hero_illustration_html(content),
        "{{INSIGHT_PARAGRAPH}}": content.insight_paragraph,
        "{{SUPPORTING_POINTS_HTML}}": _supporting_points_html(content.supporting_points),
        "{{CLOSING_LINE}}": content.closing_line,
        "{{SOURCE_STUDY}}": content.source_study,
        "{{CTA_URL}}": BASE_CTA_URL,
        "{{CTA_LABEL}}": cta_label,
        "{{UNSUBSCRIBE_URL}}": UNSUBSCRIBE_URL_TEMPLATE.format(email=recipient.email),
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html
