"""
The "What's New on Hercules.works" product-update campaign: a distinct
content shape and template from the weekly research-finding newsletter
(see data_sources.WeeklyContent / render.py / template.html), kept in
its own module so building this doesn't touch that recurring pipeline
at all.

Where the weekly newsletter is one hero stat and a single CTA, this is
several feature sections plus pricing, each with its own CTA, aimed at
a mixed audience -- existing hercules.works users and people who have
never used it. test_send.py drives both kinds through the same team-only
safety rails via --kind weekly|whats_new.
"""

import json
from dataclasses import dataclass, field
from typing import List

import config
import illustrations
from data_sources import Recipient
from render import UNSUBSCRIBE_URL_TEMPLATE  # shared with the weekly template

TEMPLATE_PATH = "template_whats_new.html"
CONTENT_PATH = "content/whats_new_content.json"


@dataclass
class Section:
    heading: str
    paragraphs: List[str]
    cta_label: str = ""
    cta_url: str = ""


@dataclass
class Qualitative:
    heading: str
    intro: str
    items: List[str]
    cta_label: str
    cta_url: str


@dataclass
class PricingTier:
    name: str
    price: str
    body: str


@dataclass
class Pricing:
    heading: str
    free_trial_name: str
    free_trial_price: str
    free_trial_body: str
    tiers: List[PricingTier]
    cta_label: str
    cta_url: str


@dataclass
class WhatsNewContent:
    subject: str
    greeting_fallback: str
    headline_line1: str
    headline_line2_italic: str
    tagline: str
    intro_paragraphs: List[str]
    sections: List[Section]
    qualitative: Qualitative
    pricing: Pricing
    signoff: str

    def full_text(self) -> str:
        """Every word a recipient actually reads, for the house-style and
        length checks in verify.py -- CTA labels and headings included,
        since those are exactly where a stray em dash tends to sneak in."""
        parts = [self.headline_line1, self.headline_line2_italic, self.tagline,
                 *self.intro_paragraphs]
        for s in self.sections:
            parts += [s.heading, *s.paragraphs, s.cta_label]
        q = self.qualitative
        parts += [q.heading, q.intro, *q.items, q.cta_label]
        p = self.pricing
        parts += [p.heading, p.free_trial_body, p.cta_label]
        parts += [f"{t.name} {t.price} {t.body}" for t in p.tiers]
        parts.append(self.signoff)
        return " ".join(parts)

    def override_ctas(self, url: str) -> None:
        """Points every CTA in the email at one URL -- used for test sends
        (--cta-url) so a team's clicks don't land on the real per-feature
        UTM links before the campaign has actually gone out."""
        for s in self.sections:
            if s.cta_url:
                s.cta_url = url
        self.qualitative.cta_url = url
        self.pricing.cta_url = url


def get_whats_new_content(path: str = CONTENT_PATH) -> WhatsNewContent:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return WhatsNewContent(
        subject=data["subject"],
        greeting_fallback=data.get("greeting_fallback", "there"),
        headline_line1=data["headline_line1"],
        headline_line2_italic=data["headline_line2_italic"],
        tagline=data["tagline"],
        intro_paragraphs=data["intro_paragraphs"],
        sections=[Section(**s) for s in data["sections"]],
        qualitative=Qualitative(**data["qualitative"]),
        pricing=Pricing(
            heading=data["pricing"]["heading"],
            free_trial_name=data["pricing"]["free_trial_name"],
            free_trial_price=data["pricing"]["free_trial_price"],
            free_trial_body=data["pricing"]["free_trial_body"],
            tiers=[PricingTier(**t) for t in data["pricing"]["tiers"]],
            cta_label=data["pricing"]["cta_label"],
            cta_url=data["pricing"]["cta_url"],
        ),
        signoff=data["signoff"],
    )


def render_subject(content: WhatsNewContent) -> str:
    return content.subject


def _load_template() -> str:
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


def _paragraphs_html(paragraphs: List[str], color: str) -> str:
    return "".join(
        f'<div style="font-size:16px; color:{color}; line-height:1.65; margin:0 0 14px 0;">{p}</div>'
        for p in paragraphs
    )


def _cta_button_html(label: str, url: str) -> str:
    if not label or not url:
        return ""
    return f'''<a href="{url}" style="display:inline-block; background-color:#000000; color:#ffffff; text-decoration:none; padding:12px 26px; border-radius:999px; font-size:14px; font-weight:600; margin-top:4px;">{label}</a>'''


def _section_html(section: Section) -> str:
    return f'''<tr>
  <td style="padding:0 32px 28px 32px;">
    <div style="font-size:20px; font-weight:700; color:{config.BRAND_HEADING_COLOR}; line-height:1.35; margin:0 0 10px 0;">{section.heading}</div>
    {_paragraphs_html(section.paragraphs, config.BRAND_BODY_COLOR)}
    {_cta_button_html(section.cta_label, section.cta_url)}
  </td>
</tr>'''


def _sections_html(sections: List[Section]) -> str:
    return "".join(_section_html(s) for s in sections)


def _qualitative_html(q: Qualitative) -> str:
    rows = "".join(
        f'''<tr>
          <td style="padding:0 0 12px 0; vertical-align:top; width:22px;">
            <span style="color:#F23B2E; font-size:16px; font-weight:700; line-height:1.55;">&#10003;</span>
          </td>
          <td style="padding:0 0 12px 0; color:{config.BRAND_BODY_COLOR}; font-size:15px; line-height:1.55;">{item}</td>
        </tr>'''
        for item in q.items
    )
    return f'''<tr>
  <td style="padding:0 32px 28px 32px;">
    <div style="font-size:20px; font-weight:700; color:{config.BRAND_HEADING_COLOR}; line-height:1.35; margin:0 0 10px 0;">{q.heading}</div>
    <div style="font-size:16px; color:{config.BRAND_BODY_COLOR}; line-height:1.65; margin:0 0 16px 0;">{q.intro}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>
    <div style="margin-top:8px;">{_cta_button_html(q.cta_label, q.cta_url)}</div>
  </td>
</tr>'''


def _pricing_html(p: Pricing) -> str:
    tier_rows = "".join(
        f'''<tr>
          <td style="padding:10px 0; border-top:1px solid {config.BRAND_BORDER_COLOR};">
            <span style="font-size:15px; font-weight:700; color:{config.BRAND_HEADING_COLOR};">{t.name}</span>
            <span style="font-size:13px; color:{config.BRAND_MUTED_COLOR};"> &middot; {t.price}</span><br>
            <span style="font-size:14px; color:{config.BRAND_BODY_COLOR}; line-height:1.5;">{t.body}</span>
          </td>
        </tr>'''
        for t in p.tiers
    )
    return f'''<tr>
  <td style="padding:0 32px 28px 32px;">
    <div style="font-size:20px; font-weight:700; color:{config.BRAND_HEADING_COLOR}; line-height:1.35; margin:0 0 14px 0;">{p.heading}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#FDF9EC; border:1px solid #FBAAC5; border-radius:14px; margin-bottom:6px;">
      <tr>
        <td style="padding:18px 20px;">
          <span style="font-size:15px; font-weight:700; color:{config.BRAND_HEADING_COLOR};">{p.free_trial_name} &middot; {p.free_trial_price}</span><br>
          <span style="font-size:14px; color:{config.BRAND_BODY_COLOR}; line-height:1.55;">{p.free_trial_body}</span>
        </td>
      </tr>
    </table>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{tier_rows}</table>
    <div style="margin-top:16px;">{_cta_button_html(p.cta_label, p.cta_url)}</div>
  </td>
</tr>'''


def _greeting(recipient: Recipient, fallback: str) -> str:
    first_name = (recipient.name or "").strip().split(" ")[0]
    return f"Hi {first_name or fallback},"


def render_whats_new_email(recipient: Recipient, content: WhatsNewContent) -> str:
    html = _load_template()
    replacements = {
        "{{GREETING}}": _greeting(recipient, content.greeting_fallback),
        "{{HEADLINE_LINE1}}": content.headline_line1,
        "{{HEADLINE_LINE2_ITALIC}}": content.headline_line2_italic,
        "{{TAGLINE}}": content.tagline,
        "{{HERO_ILLUSTRATION_HTML}}": illustrations.render_whats_new_hero_svg(),
        "{{INTRO_HTML}}": _paragraphs_html(content.intro_paragraphs, config.BRAND_BODY_COLOR),
        "{{SECTIONS_HTML}}": _sections_html(content.sections),
        "{{QUALITATIVE_HTML}}": _qualitative_html(content.qualitative),
        "{{PRICING_HTML}}": _pricing_html(content.pricing),
        "{{SIGNOFF}}": content.signoff,
        "{{UNSUBSCRIBE_URL}}": UNSUBSCRIBE_URL_TEMPLATE.format(email=recipient.email),
        "{{BRAND_HEADING_COLOR}}": config.BRAND_HEADING_COLOR,
        "{{BRAND_BODY_COLOR}}": config.BRAND_BODY_COLOR,
        "{{BRAND_MUTED_COLOR}}": config.BRAND_MUTED_COLOR,
        "{{BRAND_BORDER_COLOR}}": config.BRAND_BORDER_COLOR,
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html
