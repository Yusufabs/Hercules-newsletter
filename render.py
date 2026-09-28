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
UNSUBSCRIBE_URL_TEMPLATE = "https://hercules.works/?unsub={email}"
# NOTE: this points at the root domain as a resolvable placeholder. Swap
# it for the real unsubscribe endpoint once it exists -- the link checker
# in verify.py will fail loudly if a URL doesn't resolve.


def _load_template() -> str:
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


def _supporting_points_html(points: list) -> str:
    # Checkmark list, matching the hercules.works blog's "Key Takeaways" bullets.
    rows = "".join(
        f'''<tr>
          <td style="padding:0 0 12px 0; vertical-align:top; width:22px;">
            <span style="color:{config.BRAND_ACCENT_COLOR}; font-size:16px; font-weight:700; line-height:1.55;">&#10003;</span>
          </td>
          <td style="padding:0 0 12px 0; color:{config.BRAND_BODY_COLOR}; font-size:16px; line-height:1.55;">{p}</td>
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
        content.hero_stat_value,
        content.hero_stat_label,
        config.BRAND_ACCENT_COLOR,
        config.BRAND_CALLOUT_BG,
        config.BRAND_CALLOUT_BORDER,
        config.BRAND_HEADING_COLOR,
    )


def cta_url(content: WeeklyContent) -> str:
    # The issue's own UTM-tagged link (cta_url in weekly_content.json) wins;
    # config.DEFAULT_CTA_URL is only the fallback. Clicks are tracked on
    # the user's external analytics platform via those UTM params.
    return content.cta_url or config.DEFAULT_CTA_URL


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
        "{{CTA_URL}}": cta_url(content),
        "{{CTA_LABEL}}": cta_label,
        "{{UNSUBSCRIBE_URL}}": UNSUBSCRIBE_URL_TEMPLATE.format(email=recipient.email),
        "{{BRAND_ACCENT_COLOR}}": config.BRAND_ACCENT_COLOR,
        "{{BRAND_HEADING_COLOR}}": config.BRAND_HEADING_COLOR,
        "{{BRAND_BODY_COLOR}}": config.BRAND_BODY_COLOR,
        "{{BRAND_MUTED_COLOR}}": config.BRAND_MUTED_COLOR,
        "{{BRAND_BORDER_COLOR}}": config.BRAND_BORDER_COLOR,
        "{{BRAND_CALLOUT_BG}}": config.BRAND_CALLOUT_BG,
        "{{BRAND_CALLOUT_BORDER}}": config.BRAND_CALLOUT_BORDER,
        "{{BRAND_FOOTER_BG}}": config.BRAND_FOOTER_BG,
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html
