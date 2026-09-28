---
name: weekly-newsletter
description: Turn this week's raw report into the Hercules newsletter -- extract the sharpest finding, draft 2-minute-read copy, build the hero illustration, render an HTML preview, iterate with the user until approved, then save the approved content for Thursday's automated send.
---

# Weekly newsletter workflow

Invoked when the user hands over this week's report (pasted, attached, or
referenced by path) and wants the newsletter drafted. Follow this end to
end; don't skip the approval loop, and don't send anything yourself --
sending is fully automated by `.github/workflows/send-newsletter.yml`
every Thursday morning, reading whatever is currently approved in
`content/weekly_content.json`.

## 1. Read the full report

The report arrives as a PDF attachment each week. Read the entire file
directly with the Read tool (it handles PDFs natively; for anything
past 10 pages, pass a `pages` range and work through it in batches
rather than skimming). If a page is a scanned image with no extractable
text, or you need tables pulled out cleanly, load the `pdf` skill for
OCR/extraction instead of guessing at content you can't actually read.

Read the entire report, not a summary of it. The sharpest finding is
often buried past the executive summary, and a pre-summarized version
risks losing exactly the thing worth leading with.

## 2. Find the one finding worth the whole issue

Identify the single most surprising, counterintuitive, or non-obvious
finding. Not the headline stat by default -- the one a busy person would
actually stop scrolling for. If the headline stat genuinely is the most
interesting thing, use it, but check first.

Pull 2 to 4 supporting points that build the case for why that finding
matters. These should add new information, not restate the headline.

**One insight per issue, not a roundup.** The 2 minute read format only
works if there's a single throughline. Resist folding in a second
finding "since it's interesting too." If nothing in the report would
make you personally pause mid-scroll, say so -- that's a skip-this-week
situation, not a send-anyway one.

## 3. Draft the copy

Structure, 300 to 400 words total:
- A one line hook. Not a description of the study -- the insight itself,
  stated plainly. This becomes both the headline and the email subject.
- A short paragraph unpacking the main insight and why it's surprising.
- 2 to 4 supporting points, each 1 to 2 sentences.
- One closing line connecting the insight to why the reader, personally,
  should care.
- A hero stat: pull the single number the issue is actually about (e.g.
  "54%") plus a short caption for it (under ~12 words). This drives the
  illustration -- see step 4.

Style rules, no exceptions:
- No hyphens or em dashes used as a dash (ordinary hyphenated words like
  "non-obvious" are fine).
- No AI-sounding phrases: "dive into," "delve," "unlock," "in today's
  fast-paced world," "game-changer," "unpack," "leverage," and the rest
  of `config.BANNED_PHRASES`.
- Confident, declarative tone. No hedging ("may suggest," "could
  indicate").
- No statistical jargon in the body (no "p-value," "confidence
  interval," "sample size").
- No methodology caveats in the body.

Reuse this exact prompt/structure every week -- consistency here is what
makes it read as a newsletter, not a series of one-off emails.

## 4. Build the illustration

The hero illustration is generated from the hero stat via
`illustrations.py` (`config.ILLUSTRATION_MODE=placeholder` today). You
don't need to design anything by hand -- just make sure `hero_stat_value`
and `hero_stat_label` are set well, since they're what the graphic shows.

Once the user hands off the real hercules.works blog design system,
switch `ILLUSTRATION_MODE` to `brand_asset` and set
`BRAND_ILLUSTRATION_ASSET_URL` -- nothing else in this workflow changes.

## 5. Render a real preview and show it

Write the draft to `content/weekly_content.json` matching the schema in
`sample_data/weekly_content.example.json` (title, hook,
insight_paragraph, supporting_points, closing_line, source_study,
hero_stat_value, hero_stat_label, cta_url).

`cta_url` is the CTA button's link, and the user supplies it: a
UTM-tagged URL they track on their own external analytics platform. Ask
for it if they haven't given it, and paste it in exactly as given; never
invent or edit UTM parameters. Left blank, the button falls back to
`config.DEFAULT_CTA_URL`, which carries no UTM tags, so don't hand off
an issue without it unless the user says to.

Then render an actual preview so the user sees exactly what a recipient
would see, not a text description of it:

```bash
NEWSLETTER_DATA_SOURCE=sample NEWSLETTER_DRY_RUN=true python3 -c "
import render, data_sources
content = data_sources.get_weekly_content()
recipients = data_sources.get_recipients()
html = render.render_email(recipients[0], content)
open('preview.html', 'w').write(html)
print('Subject:', render.render_subject(content))
"
```

Publish `preview.html` as an Artifact so the user can see the actual
rendered email (load the `artifact-design` skill first, as usual). Don't
restyle it -- it needs to show what will actually land in an inbox, not
an artifact-themed reinterpretation of it.

## 6. Iterate until approved

Read it back with the user's eye, not a proofreader's: does this
actually feel true and interesting? The mechanical checks (length,
banned phrases, links) run automatically in step 7 -- this pass is for
judgment calls the gate can't make. Revise `content/weekly_content.json`
and re-render as many times as needed.

## 7. On approval: verify, then hand off to automation

Run the verification gate before telling the user this issue is ready:

```bash
NEWSLETTER_DATA_SOURCE=sample NEWSLETTER_DRY_RUN=true python3 send.py
```

This is a dry run -- it pulls recipients (hercules.works users plus
top-level personnel from the external CSV, merged -- see
`data_sources.py`), renders, and runs every check in `verify.py` (word
count, house style, required fields, link resolution) without sending
anything. Both recipient audiences get the identical rendered email --
this step doesn't branch content by audience. If it passes, tell the
user exactly that, including the recipient count and where the dry-run
delivery report landed (`logs/delivery_report_*_dryrun.csv`, the
exact list of who this issue would go to), and remind them the actual send happens automatically
via GitHub Actions next Thursday morning against whatever is currently
committed in `content/weekly_content.json` -- so the last thing to do is
commit (and push, if they want it live before Thursday) that file. If
anything fails, fix the draft and rerun this step; don't hand off a
failing draft.

## 7b. Optional: team test send

If the user wants to see the draft in real inboxes first, use
`test_send.py` (full flow and checklist in `TESTING.md`). Always run it
without `--send` first and show the user who it would go to. Only add
`--send` when the user has asked for a test send in this conversation;
that request covers that one test send, not later ones. Test sends go
only to `test_recipients.json`, limited to `TEST_ALLOWED_DOMAINS`, so
this is the one real send this skill may run. Suggest `--cta-url` with
a separate test UTM link so team clicks don't count toward the real
issue's campaign. Afterwards, ask the user what the team saw against
the TESTING.md checklist and fix whatever broke.

## 8. Draft the paired blog post

Same week, same underlying finding, longer form. Once the newsletter
content is approved, use a marketing content skill (e.g.
`marketing:content-creation`) to draft a full blog post from the same
report, matching the hercules.works blog's content shape (as used in
`app/blog/[slug]/page.tsx`): a title, an SEO title/description/keyword
set (matching the `blogMetaData` shape at the top of that file), a
`description` (the lead paragraph), 3-5 `keyTakeaways`, a handful of
`faqs` ({q, a} pairs), and the full `content` body -- longer and more
thorough than the newsletter, since it doesn't have the 2 minute read
constraint. Save the draft to `content/blog/<slug>.md` (front matter for
title/description/keywords/keyTakeaways/faqs, body below) so it's easy
to review and then hand-paste into `blogData.ts` and the `blogMetaData`
array -- this project doesn't have write access to the actual
hercules.works site repo. Show the draft to the user the same way as the
newsletter preview: don't assume approval, iterate on request.

## Guardrail: never send for real without explicit approval

Every command in this skill uses `NEWSLETTER_DRY_RUN=true`. That's not
incidental -- do not run `send.py` (or anything that calls `esp.py`)
with dry-run off, apart from the team-only `test_send.py --send`
described in 7b, or otherwise cause a real email to go out, as part of
following this skill. The only real sends happen through the GitHub
Actions workflow's manual `workflow_dispatch`, itself gated behind the
`production-send` environment's required-reviewer approval (see README
"Approval gate"). All automatic (scheduled) triggers are currently
disabled by explicit request -- do not re-enable the `schedule:` block
in `.github/workflows/send-newsletter.yml` unless the user explicitly
asks for it back.
