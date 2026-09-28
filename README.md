# Hercules Weekly Newsletter — Automation

Conversational drafting, machine-verified distribution. You hand Claude
this week's report in chat, Claude drafts an eye-catching 2 minute read
with a data illustration, you approve it, and GitHub Actions sends it
automatically every Thursday morning to two merged audiences — every
hercules.works user, and the top-level personnel (by title) from a
separate external CSV. Both get the exact same content; only the
recipient list differs. Nothing about picking the story or writing the
copy is automated on purpose — that stays a judgment call between you
and Claude. Everything after approval is automatic.

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
| `data_sources.py` | Recipients merge two sources: hercules.works users via a live DB pull (API only, no CSV export step, ever — `sample` mode is local-testing-only), and top-level personnel filtered by job title out of a separate external CSV — everyone else in that file is excluded. Weekly content comes from the approved JSON file, not an auto-pull — that step is deliberately manual. |
| `illustrations.py` | Generates the hero illustration. Currently an inline-SVG stat graphic built from the week's number; swaps to the real hercules.works blog design once that's handed off — see "Pending" below. |
| `render.py` | Merges approved content + illustration into `template.html`, branches CTA by active/dormant recipient. |
| `template.html` | The email itself: eyebrow + "2 min read" badge, hook, hero illustration, insight paragraph, supporting points, closing pull-quote, CTA. |
| `verify.py` | The gate described above. |
| `esp.py` | Gmail SMTP (free, team testing), SendGrid (intended for production), and Brevo (free alternative) wrappers, swappable via `ESP_PROVIDER`. |
| `send.py` | Orchestrates all of the above; archives what was actually sent into `content/sent/`. |
| `test_send.py` | Team-only test sends of the current draft. See `TESTING.md`. |
| `TESTING.md` | Test-send flow, what to check in each mail app, and a results log. |
| `content/weekly_content.json` | This week's **approved, current** content — what the Thursday send reads. Overwritten each week; history lives in `content/sent/` and git log. |
| `content/sent/` | Dated archive of every issue that actually went out. |
| `sample_data/sample_report.txt` | Example of the kind of report you'd hand to Claude (real ones arrive as PDF). |
| `sample_data/weekly_content.example.json` | Reference example of the approved-content schema. |
| `sample_data/sample_recipients.json` | Sample hercules.works user data for local dry runs (`NEWSLETTER_DATA_SOURCE=sample`) — never used in production. |
| `sample_data/sample_personnel.csv` | Example external personnel file with mixed seniority, to test the top-level title filter. Swap for the real file at `PERSONNEL_CSV_PATH`. |
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

## Testing with your team

Before a real send, put the draft in your team's inboxes with
`python3 test_send.py` (preview) and then `python3 test_send.py --send`.
It only ever sends to `test_recipients.json` and refuses any address
outside `TEST_ALLOWED_DOMAINS`. Test sends go through your own Gmail or
Google Workspace account (free, no signup) rather than a real ESP -- the
production send will move to one (SendGrid, most likely) once the
hercules.works recipient API and personnel CSV are wired up. The full
flow, setup, and a what-to-check list for each mail app are in
`TESTING.md`.

## Who it went to: the delivery report

Every run that passes verification writes
`logs/delivery_report_<date>_<time>.csv` (dry runs add `_dryrun`), one
row per recipient:

| Column | Meaning |
|---|---|
| `email`, `name` | The recipient |
| `audience` | `hercules` (hercules.works user) or `personnel_csv` (top-level personnel) |
| `segment` | `active` or `dormant`, which decides which CTA label they got |
| `status` | `sent` (SendGrid accepted it), `failed` (see `error`), or `dry_run_not_sent` |
| `error` | Why a send failed, if it did |

Rows are written as each send happens, so the report stays accurate
even if a run dies partway. The counts (total, per audience, sent,
failed) also go to `logs/last_run_summary.json` and to the Actions run
page's summary. To see the full list for a GitHub run, open the run and
download the **newsletter-run-log** artifact (kept 90 days). The report
holds email addresses, so it's never committed to git.

"Sent" means SendGrid accepted the message. A later bounce (dead
mailbox, full inbox) appears only in SendGrid's Activity Feed. A run
with any failed recipient exits non-zero, so the Actions run shows red.

## CTA link (UTM)

Each issue's CTA button uses the `cta_url` field in
`content/weekly_content.json`. That's the UTM-tagged link you supply,
and you track clicks on it in your own analytics platform. If the
field is blank, the button falls back to `NEWSLETTER_CTA_URL`
(default `https://hercules.works/`, no UTM). The verification gate
checks that the link resolves before anything sends.

## Top-level personnel filter (`sample_data/sample_personnel.csv`)

The external CSV is a separate audience from hercules.works users —
everyone in it gets excluded except rows whose title matches
`config.TOP_LEVEL_TITLE_KEYWORDS` (founder, C-suite, VP, director, head
of, etc. — case-insensitive substring match). `data_sources.py` looks
for a title column under a few common spellings automatically (`title`,
`designation`, `role`, `job_title`, `position`); if the real file uses
something else, add it to `_TITLE_COLUMN_CANDIDATES`. Both audiences
receive the identical rendered email — this only changes who's on the
list, logged separately in `logs/send_log.txt` and
`logs/last_run_summary.json` as `hercules_recipient_count` /
`personnel_recipient_count`. Set `NEWSLETTER_INCLUDE_PERSONNEL_CSV=false`
to disable this source entirely for a given run.

## Before your first real send

Three things are genuinely open — everything else in this blueprint
already works end to end against the sample data:

1. **The hercules.works/Poseidon recipient endpoint.** You confirmed
   live API/DB access exists, but `_get_recipients_from_api()` in
   `data_sources.py` is still a stub — it needs the real endpoint path,
   auth header shape, and response field names. The docstring there
   shows the expected shape; filling it in is a one-function change.
2. **The real external personnel CSV.** Point `PERSONNEL_CSV_PATH` at
   it, confirm its title column is one of the spellings
   `_TITLE_COLUMN_CANDIDATES` checks (or add the real one), and sanity
   check `TOP_LEVEL_TITLE_KEYWORDS` against the actual title values —
   the sample list is a reasonable starting guess, not a guarantee.
3. **Real per-issue illustration artwork.** Brand *colors* are already
   the real hercules.works ones (pulled from the blog page design). The
   hero graphic itself is still a generated stat-ring placeholder in
   `illustrations.py`. Once real illustration artwork exists, set
   `NEWSLETTER_ILLUSTRATION_MODE=brand_asset` and
   `BRAND_ILLUSTRATION_ASSET_URL` — no other file changes.

Beyond those three:

4. Set `ESP_API_KEY` to a real, domain-authenticated SendGrid sender.
5. Update `UNSUBSCRIBE_URL_TEMPLATE` in `render.py` to the real
   unsubscribe endpoint, and put this issue's UTM link in `cta_url` — the link checker will
   refuse to send if either doesn't resolve.
6. Push this folder to a GitHub repo and add the secrets listed in
   `.env.example` (`HERCULES_API_KEY`, `ESP_API_KEY`, etc.) as GitHub
   Actions repo secrets — the workflow reads them from there, never from
   a committed file.
7. Run the workflow once manually (`workflow_dispatch`, dry-run **on**)
   and read the uploaded log before ever running it with dry-run off.

## Scheduling — currently manual-only, by request

**All automatic triggers are off.** The Thursday cron schedule
(previously `30 2 * * 4`, 08:00 IST) has been removed from
`.github/workflows/send-newsletter.yml` — commented out, not deleted, so
it's easy to reference. The workflow now only runs when a human clicks
**Run workflow** in the Actions tab, and even then it won't send until
the approval gate below is granted. Nothing sends unattended.

## Approval gate (required before any real send)

Every run of the workflow — manual today, scheduled again in future if
you choose to bring that back — is gated behind a GitHub **environment**
called `production-send`. This needs a one-time setup that only you can
do (it's a repo setting, not something in code):

1. On GitHub: **Settings → Environments → New environment**.
2. Name it exactly `production-send` (must match the workflow file).
3. Under **Deployment protection rules**, turn on **Required reviewers**
   and add yourself (and anyone else who should be able to approve a
   send).
4. Save.

After that, every run — including a manual `workflow_dispatch` with
dry-run off — pauses at "Waiting for approval" in the Actions tab and
notifies the required reviewers. Nothing sends until someone approves it
there. This is the durable version of "ask before sending": it holds
even if the schedule gets re-enabled later, and even if someone other
than you has push access to this repo.

Claude will not run a real (non-dry-run) send directly either — see the
guardrail in `.claude/skills/weekly-newsletter/SKILL.md`.

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
