"""
Illustration generation for the weekly email.

PLACEHOLDER MODULE -- pending real hercules.works blog design handoff.

Right now this builds a simple, on-brand-agnostic inline-SVG "hero stat"
graphic straight from the week's content (the number the newsletter is
actually about), so the pipeline has a real, working illustration end to
end today. Once the real hercules.works blog design system is handed
off, swap config.ILLUSTRATION_MODE to "brand_asset" and this file stops
being used for the hero graphic -- render.py falls through to
render_brand_asset_illustration() instead. No other file needs to change.

Known limitation of the inline-SVG approach: it renders in Apple Mail,
Gmail (web + app), and most modern clients, but Outlook desktop's Word
rendering engine does not support inline SVG and will show the alt text
instead. That's an acceptable tradeoff for an interim placeholder; the
real brand asset should ship as a hosted PNG/JPG with proper alt text to
avoid that gap in production.
"""

import re
import math

_RING_RADIUS = 54
_RING_CIRCUMFERENCE = 2 * math.pi * _RING_RADIUS


def _extract_percent(stat_value: str) -> int:
    """
    Pulls a 0-100 fill amount out of a stat string for the progress ring.
    "54%" -> 54. Non-percent stats ("3x", "8 in 10") fall back to a fixed
    decorative fill since there's no natural 0-100 mapping for them.
    """
    match = re.search(r"(\d{1,3})\s*%", stat_value)
    if match:
        return max(4, min(100, int(match.group(1))))
    return 72  # decorative default for non-percent stats


def render_hero_stat_svg(stat_value: str, stat_label: str, accent_color: str) -> str:
    """
    Returns an HTML snippet (inline SVG wrapped in a centered table cell)
    showing a progress ring with the stat value in the center and its
    label underneath. Safe to drop straight into an email-safe HTML table.
    """
    percent = _extract_percent(stat_value)
    offset = _RING_CIRCUMFERENCE * (1 - percent / 100)

    svg = f'''<svg width="140" height="140" viewBox="0 0 140 140" role="img" aria-label="{stat_label}">
  <circle cx="70" cy="70" r="{_RING_RADIUS}" fill="none" stroke="#eef0fb" stroke-width="12" />
  <circle cx="70" cy="70" r="{_RING_RADIUS}" fill="none" stroke="{accent_color}" stroke-width="12"
    stroke-linecap="round" stroke-dasharray="{_RING_CIRCUMFERENCE:.2f}" stroke-dashoffset="{offset:.2f}"
    transform="rotate(-90 70 70)" />
  <text x="70" y="78" text-anchor="middle" font-family="Helvetica, Arial, sans-serif"
    font-size="28" font-weight="700" fill="#111111">{stat_value}</text>
</svg>'''

    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td align="center" style="padding:8px 32px 24px 32px;">
      {svg}
      <div style="margin-top:10px; font-size:14px; color:#666666; line-height:1.5; max-width:320px;">{stat_label}</div>
    </td>
  </tr>
</table>'''


def render_placeholder_illustration(stat_value: str, stat_label: str, accent_color: str) -> str:
    """Entry point used by render.py when config.ILLUSTRATION_MODE == 'placeholder'."""
    if not stat_value.strip():
        return ""
    return render_hero_stat_svg(stat_value, stat_label, accent_color)


def render_brand_asset_illustration(asset_url: str, alt_text: str) -> str:
    """
    Entry point used by render.py when config.ILLUSTRATION_MODE ==
    'brand_asset'. Wire this up for real once the hercules.works blog
    design is delivered -- likely a hosted image (or a small set of
    them) matching the blog's existing illustration style, rather than
    a generated SVG.
    """
    if not asset_url:
        raise ValueError(
            "ILLUSTRATION_MODE is 'brand_asset' but BRAND_ILLUSTRATION_ASSET_URL "
            "is empty. Set it once the hercules.works blog design assets exist, "
            "or switch back to ILLUSTRATION_MODE=placeholder in the meantime."
        )
    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td align="center" style="padding:8px 32px 24px 32px;">
      <img src="{asset_url}" alt="{alt_text}" width="536" style="max-width:100%; height:auto; border-radius:8px; display:block;">
    </td>
  </tr>
</table>'''
