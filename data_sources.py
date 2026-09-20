"""
Data source abstraction.

Two very different kinds of data flow through this pipeline, and they're
sourced differently on purpose:

1. Recipients (who to send to) -- pulled live from the hercules.works
   user DB via DATA_SOURCE_MODE=api. There is no CSV export step, live
   or otherwise -- production always reads the DB directly through the
   API. DATA_SOURCE_MODE=sample exists only so the rest of the pipeline
   (render/verify/send) can be tested locally without hitting the real
   DB; it reads sample_data/sample_recipients.json instead.

2. Weekly content (what to say) -- this is NOT auto-pulled. Each week
   you hand the report to Claude in chat (see
   .claude/skills/weekly-newsletter/SKILL.md), review the rendered
   preview, and once you approve it the final JSON gets saved to
   WEEKLY_CONTENT_PATH. This module just loads that file. There is
   deliberately no "auto-generate the insight" code path -- picking the
   finding and drafting the copy is a human-in-the-loop conversation
   with Claude, not something to automate away.
"""

import json
import datetime as dt
from dataclasses import dataclass
from typing import List

import config


@dataclass
class Recipient:
    email: str
    name: str
    last_login: dt.date
    is_dormant: bool


@dataclass
class WeeklyContent:
    title: str                     # internal label, not shown to users
    hook: str                      # one line hook, the headline
    insight_paragraph: str         # the main unpacking paragraph
    supporting_points: List[str]   # 2-4 supporting bullets
    closing_line: str              # closing sentence
    source_study: str              # study name, shown in the footer
    hero_stat_value: str = ""      # the headline number, e.g. "54%" -- drives the illustration
    hero_stat_label: str = ""      # short caption for that number, e.g. "tossed a snack that wasn't spoiled"


def get_recipients() -> List[Recipient]:
    if config.DATA_SOURCE_MODE == "api":
        return _get_recipients_from_api()
    elif config.DATA_SOURCE_MODE == "sample":
        return _get_recipients_from_sample()
    else:
        raise ValueError(f"Unknown DATA_SOURCE_MODE: {config.DATA_SOURCE_MODE}")


def get_weekly_content() -> WeeklyContent:
    """
    Loads the approved weekly content JSON -- the output of the
    report-in, Claude-drafts, you-approve loop. See
    .claude/skills/weekly-newsletter/SKILL.md for that workflow and
    README.md for the full picture.
    """
    with open(config.WEEKLY_CONTENT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return WeeklyContent(
        title=data["title"],
        hook=data["hook"],
        insight_paragraph=data["insight_paragraph"],
        supporting_points=data["supporting_points"],
        closing_line=data["closing_line"],
        source_study=data["source_study"],
        hero_stat_value=data.get("hero_stat_value", ""),
        hero_stat_label=data.get("hero_stat_label", ""),
    )


# --- Sample implementation (recipients only, local dry runs) ------------

def _get_recipients_from_sample() -> List[Recipient]:
    """
    Stand-in for the real DB pull, used only for local testing. Expects
    sample_data/sample_recipients.json: a list of
    {"email", "name", "last_login" (YYYY-MM-DD)} objects.
    """
    recipients = []
    cutoff = dt.date.today() - dt.timedelta(days=config.DORMANT_THRESHOLD_DAYS)
    with open(config.SAMPLE_RECIPIENTS_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    for row in rows:
        last_login = dt.date.fromisoformat(row["last_login"])
        recipients.append(
            Recipient(
                email=row["email"].strip(),
                name=row.get("name", "").strip(),
                last_login=last_login,
                is_dormant=last_login < cutoff,
            )
        )
    return recipients


# --- Live API implementation (recipients, real hercules.works pull) -----

def _get_recipients_from_api() -> List[Recipient]:
    """
    TODO (before first live send): this is the one piece of the pipeline
    that needs real hercules.works / Poseidon integration details --
    confirm and fill in:
      - the actual endpoint path off HERCULES_API_BASE (or POSEIDON_API_BASE)
      - the auth header shape (bearer token shown below is a guess)
      - the response field names for email / display name / last login

    Expected shape once wired up, mirroring _get_recipients_from_sample()'s
    output:

        import requests
        resp = requests.get(
            f"{config.HERCULES_API_BASE}/users/logins",
            headers={"Authorization": f"Bearer {config.HERCULES_API_KEY}"},
            params={"since_days": 90},
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()

        cutoff = dt.date.today() - dt.timedelta(days=config.DORMANT_THRESHOLD_DAYS)
        recipients = []
        for row in rows:
            last_login = dt.date.fromisoformat(row["last_login"])
            recipients.append(
                Recipient(
                    email=row["email"].strip(),
                    name=row.get("name", "").strip(),
                    last_login=last_login,
                    is_dormant=last_login < cutoff,
                )
            )
        return recipients
    """
    raise NotImplementedError(
        "Live API mode is selected (DATA_SOURCE_MODE=api) but "
        "_get_recipients_from_api() is still a stub -- the exact "
        "hercules.works/Poseidon endpoint, auth, and response shape "
        "haven't been confirmed yet. See the docstring above for the "
        "expected shape, or set NEWSLETTER_DATA_SOURCE=sample to keep "
        "testing against sample_data/sample_recipients.json in the "
        "meantime."
    )
