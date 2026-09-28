"""
Illustration generation for the weekly email.

Brand colors here are real, pulled from the hercules.works blog page
component (app/blog/[slug]/page.tsx) via config.py's BRAND_* tokens. The
graphic itself is still a generated stand-in: an inline-SVG "hero stat"
progress ring built straight from the week's content (the number the
newsletter is actually about), styled like the blog's "Key Takeaways"
callout box. This keeps the pipeline fully working today without real
per-issue illustration artwork. Once that artwork exists, set
config.ILLUSTRATION_MODE to "brand_asset" and this file stops being used
for the hero graphic -- render.py falls through to
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


def render_hero_stat_svg(
    stat_value: str,
    stat_label: str,
    accent_color: str,
    callout_bg: str,
    callout_border: str,
    heading_color: str,
) -> str:
    """
    Returns an HTML snippet: a progress ring with the stat value in the
    center, inside a callout card styled after the hercules.works blog's
    "Key Takeaways" box (soft tinted background, tinted border, 14px
    radius). Safe to drop straight into an email-safe HTML table.
    """
    percent = _extract_percent(stat_value)
    offset = _RING_CIRCUMFERENCE * (1 - percent / 100)
    ring_track = "#ffffff"

    svg = f'''<svg width="128" height="128" viewBox="0 0 140 140" role="img" aria-label="{stat_label}">
  <circle cx="70" cy="70" r="{_RING_RADIUS}" fill="none" stroke="{ring_track}" stroke-width="12" />
  <circle cx="70" cy="70" r="{_RING_RADIUS}" fill="none" stroke="{accent_color}" stroke-width="12"
    stroke-linecap="round" stroke-dasharray="{_RING_CIRCUMFERENCE:.2f}" stroke-dashoffset="{offset:.2f}"
    transform="rotate(-90 70 70)" />
  <text x="70" y="78" text-anchor="middle" font-family="Helvetica, Arial, sans-serif"
    font-size="26" font-weight="700" fill="{heading_color}">{stat_value}</text>
</svg>'''

    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td style="padding:0 32px 24px 32px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
        style="background-color:{callout_bg}; border:1px solid {callout_border}; border-radius:14px;">
        <tr>
          <td align="center" style="padding:24px;">
            <div style="font-size:12px; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; color:{accent_color}; margin-bottom:14px;">This week's number</div>
            {svg}
            <div style="margin-top:12px; font-size:14px; color:{heading_color}; line-height:1.5; max-width:320px; font-weight:500;">{stat_label}</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>'''


def render_placeholder_illustration(
    stat_value: str,
    stat_label: str,
    accent_color: str,
    callout_bg: str,
    callout_border: str,
    heading_color: str,
) -> str:
    """Entry point used by render.py when config.ILLUSTRATION_MODE == 'placeholder'."""
    if not stat_value.strip():
        return ""
    return render_hero_stat_svg(stat_value, stat_label, accent_color, callout_bg, callout_border, heading_color)


def render_whats_new_hero_svg() -> str:
    """
    Hero graphic for the "What's New" product-update campaign (see
    whats_new.py) -- a simplified, vector-friendly reinterpretation of the
    hercules.works homepage hero (a hand holding a browser-window card
    with a sparkle, in front of a pink circle), minus the photographic
    hand, which doesn't hold up as hand-built SVG at email size. Colors
    are sampled directly from that homepage screenshot, not guessed:
    cream #FDF9EC, blue frame #1339F0, red card #F23B2E, pink circle
    #FBAAC5. Same Outlook-desktop caveat as render_hero_stat_svg: no
    inline SVG support there, alt text shows instead.
    """
    sparkle_points = "150.0,96.0 157.1,118.9 180.0,126.0 157.1,133.1 150.0,156.0 142.9,133.1 120.0,126.0 142.9,118.9"
    return '''<svg width="300" height="220" viewBox="0 0 300 220" role="img" aria-label="A sparkle inside a browser-window card">
  <circle cx="195" cy="115" r="95" fill="#FBAAC5" />
  <g transform="rotate(-6 150 115)">
    <rect x="40" y="40" width="220" height="150" rx="18" fill="#1339F0" />
    <circle cx="60" cy="58" r="5" fill="#ffffff" />
    <circle cx="78" cy="58" r="5" fill="#ffffff" />
    <circle cx="96" cy="58" r="5" fill="#ffffff" />
    <rect x="56" y="78" width="188" height="96" rx="10" fill="#F23B2E" />
    <polygon points="''' + sparkle_points + '''" fill="#ffffff" />
  </g>
</svg>'''


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
