# Hercules Weekly Newsletter — Automation

Conversational drafting, machine-verified distribution. You hand Claude
this week's report in chat, Claude drafts an eye-catching 2 minute read
with a data illustration, you approve it, and GitHub Actions sends it to
every logged-in hercules.works user automatically every Thursday
morning. Nothing about picking the story or writing the copy is
automated on purpose — that stays a judgment call between you and
Claude. Everything after approval is automatic.

> **Status: blueprint.** This restructure lays out every file and the
> full pipeline end to end, proven with the bundled sample report. Two
> real-world integration details are still open — see "Before your
> first real send" below — before this can send a real issue.

## The weekly workflow

1. **Hand Claude the report as a PDF.** In this project, invoke
   `/weekly-newsletter` and attach the week's report PDF (or just
   attach it and ask for this week's newsletter — the skill at
   `.claude/skills/weekly-newsletter/SKILL.md` governs the workflow
   either way). Claude reads the full PDF directly, finds the sharpest
   non-obvious finding, drafts the copy, and builds the hero
   illustration from the week's key stat.

2. **Claude shows you a real preview**, not a text description — the
   actual rendered HTML email, published so you can see exactly what a
   recipient's inbox will show. You review and ask for changes as many
   times as you want.

3. **You approve.** The final JSON is saved to
   `content/weekly_content.json` (the schema is in
   `sample_data/weekly_content.example.json`). This is the only manual
   step in the whole pipeline.

4. **Claude runs a dry-run verification pass** before calling it done,
   so you know it would pass before it's ever scheduled to send.

5. **Thursday morning, GitHub Actions sends it.** The workflow pulls
   the live logged-in user list from hercules.works, runs the same
   verification gate again, and sends via SendGrid if everything
   passes. No one has to remember to run anything.

## Verification gate (`verify.py`)

Every run checks, before anything sends:
- Recipient count is in a plausible range (catches a broken data pull)
- Every recipient email is well-formed
- All required content fields are present, including the hero stat
- Word count is 220-480 words (a real 2 minute read, not a stub or an essay)
- **House style**: no em dashes, no hyphen-as-dash, none of the banned
  AI-sounding phrases in `config.BANNED_PHRASES` ("dive into," "delve,"
  "unlock," etc.)
- Every link in the rendered email actually resolves

A single failure aborts the send and logs exactly which check failed and
why.

## Files

| File | Purpose |
|---|---|
| `.claude/skills/weekly-newsletter/SKILL.md` | The full conversational drafting workflow Claude follows each week — extraction rules, style rules, illustration, preview, approval loop. |
| `config.py` | Settings: data source mode, illustration mode, ESP settings, word count bounds, banned phrase list. |
| `data_sources.py` | Recipients come from a live hercules.works DB pull via API — no CSV export step, ever. A `sample` mode (`sample_data/sample_recipients.json`) exists only for local testing. Weekly content comes from the approved JSON file, not an auto-pull — that step is deliberately manual. |
| `illustrations.py` | Generates the hero illustration. Currently an inline-SVG stat graphic built from the week's number; swaps to the real hercules.works blog design once that's handed off — see "Pending" below. |
| `render.py` | Merges approved content + illustration into `template.html`, branches CTA by active/dormant recipient. |
| `template.html` | The email itself: eyebrow + "2 min read" badge, hook, hero illustration, insight paragraph, supporting points, closing pull-quote, CTA. |
| `verify.py` | The gate described above. |
| `esp.py` | SendGrid wrapper, swappable. |
| `send.py` | Orchestrates all of the above; archives what was actually sent into `content/sent/`. |
| `content/weekly_content.json` | This week's **approved, current** content — what the Thursday send reads. Overwritten each week; history lives in `content/sent/` and git log. |
| `content/sent/` | Dated archive of every issue that actually went out. |
| `sample_data/sample_report.txt` | Example of the kind of report you'd hand to Claude (real ones arrive as PDF). |
| `sample_data/weekly_content.example.json` | Reference example of the approved-content schema. |
| `sample_data/sample_recipients.json` | Sample recipient data for local dry runs (`NEWSLETTER_DATA_SOURCE=sample`) — never used in production. |
| `.github/workflows/send-newsletter.yml` | The Thursday-morning automation. Runs on a schedule, plus a manual `workflow_dispatch` (with a dry-run toggle) for testing. |
| `.env.example` | Every environment variable / secret the pipeline needs, documented. |

## Running it locally

```bash
pip install requests

# Dry run against the sample data (no real emails sent, full verification runs)
NEWSLETTER_DATA_SOURCE=sample NEWSLETTER_DRY_RUN=true python3 send.py

# Real send (once the API + secrets below are wired up)
python3 send.py
```

## Before your first real send

Two things are genuinely open — everything else in this blueprint
already works end to end against the sample data:

1. **The hercules.works/Poseidon recipient endpoint.** You confirmed
   live API/DB access exists, but `_get_recipients_from_api()` in
   `data_sources.py` is still a stub — it needs the real endpoint path,
   auth header shape, and response field names. The docstring there
   shows the expected shape; filling it in is a one-function change.
2. **The real hercules.works blog illustration design.** You mentioned
   you'll hand this off separately. Until then, `illustrations.py`
   generates a placeholder inline-SVG stat graphic so the pipeline is
   fully working today. Once the design arrives, set
   `NEWSLETTER_ILLUSTRATION_MODE=brand_asset` and
   `BRAND_ILLUSTRATION_ASSET_URL` — no other file changes.

Beyond those two:

3. Set `ESP_API_KEY` to a real, domain-authenticated SendGrid sender.
4. Update `BASE_CTA_URL` and `UNSUBSCRIBE_URL_TEMPLATE` in `render.py` to
   the real dashboard and unsubscribe endpoints — the link checker will
   refuse to send if either doesn't resolve.
5. Push this folder to a GitHub repo and add the secrets listed in
   `.env.example` (`HERCULES_API_KEY`, `ESP_API_KEY`, etc.) as GitHub
   Actions repo secrets — the workflow reads them from there, never from
   a committed file.
6. Run the workflow once manually (`workflow_dispatch`, dry-run **on**)
   and read the uploaded log before ever running it with dry-run off.

## Scheduling

**Assumed:** "Thursday morning" = 08:00 IST (Asia/Kolkata). GitHub
Actions cron always runs in UTC, so `.github/workflows/send-newsletter.yml`
uses `30 2 * * 4` (02:30 UTC Thursday = 08:00 IST). If that's the wrong
time zone or hour, it's a one-line change to that cron expression.

The schedule always reads whatever is currently committed in
`content/weekly_content.json` — there's no separate "trigger the send"
step. That's why the approval step (drafting with Claude, earlier in the
week) and the send step (Thursday morning) are deliberately decoupled:
approve with margin, and Thursday's send takes care of itself.

## Best practices for the drafting step

- **Pick for surprise, not for size.** A smaller study with one genuinely
  counterintuitive finding beats a bigger study with a predictable one.
- **One insight per issue, not a roundup.** Resist cramming in a second
  finding "since it's interesting too."
- **Keep the review pass to one read-through.** The verification gate
  already catches length and style drift mechanically. Your read-through
  is for "does this actually feel true and interesting," not proofreading.
- **Give Claude the full report, not a summary of it.** The best
  counterintuitive findings are often buried past the executive summary.
- **Set a fixed weekly cadence for each stage** (e.g. report handed over
  by Monday, preview approved by Tuesday, Thursday morning send takes
  care of itself). A loose "whenever it's ready" cadence is how weekly
  newsletters quietly become biweekly ones.
