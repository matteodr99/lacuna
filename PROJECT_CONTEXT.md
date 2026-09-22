# Project context

Adaptive study platform for cloud certifications (AWS, Azure, GCP). It targets
the gap that experienced candidates actually have: not "I don't understand the
concepts" but "I don't remember the granular details layered on top of concepts
I already know" — route propagation rules, specific thresholds, edge cases.

The project is **Lacuna** — named on 2026-09-15, before the first deploy, so
no public URL would carry the working title "Study Helper". A lacuna is a gap
in knowledge, which is what the weak-spots analysis finds and the product
fills; it is also the one candidate that reads identically in Italian and
English, the two languages this project lives in. The folders were renamed to
`api/` and `web/` at the same time. The Python venv survived because every
invocation goes through `.venv/bin/python -m`, never the shebang scripts.

Two projects, kept separate on purpose:
- `api/` — Python backend (FastAPI + SQLModel + Gemini)
- `web/` — Next.js frontend (TypeScript, Tailwind, App Router)

The backend is working and tested. Do not rewrite it in TypeScript. Next.js does
the UI and talks to FastAPI over HTTP.

## Toolchain traps

`web` uses **pnpm**, not npm (npm has a bug with Tailwind's native
optional dependencies). Use `pnpm install`, `pnpm dev`, `pnpm add`.

Two versions of each tool are on this machine and only one combination works:

- **Node 20**, not the shell default 18 — Next 16 refuses to build on 18.
  `export PATH="$HOME/.nvm/versions/node/v20.19.5/bin:$PATH"`.
- **pnpm 10.33** (the one on the Node 18 path), not the pnpm 12 that ships with
  Node 20. pnpm 12 enforces a `minimumReleaseAge` policy that rejects entries in
  the current lockfile, and a rejected run *empties the top-level node_modules*
  (the `.pnpm` store survives), which breaks a running dev server until
  `pnpm install` is re-run with pnpm 10. So: Node 20 in PATH for the build, but
  invoke the local binary (`./node_modules/.bin/next build`) rather than
  `pnpm build`, which would pick up pnpm 12.

In `api`, the venv was created at an older path, so its `pip`
shebang is dead. Use `.venv/bin/python -m pip` and `.venv/bin/python -m pytest`.

## Architecture decisions that aren't obvious from the code

**Questions are pre-generated offline, not generated per user.**
`seed_questions.py` batch-generates into a question bank; users are served from
that bank via `GET /questions/next`. Taking a test triggers zero Gemini calls.
This is deliberate — it fixes cost, latency, and (most importantly) allows
review before content reaches anyone. There is a test that fails on purpose if
anyone reintroduces a Gemini call into the question-serving path.

**Two ways into the bank, one way out of it.**
Questions enter either by generation — `seed_questions.py`, Gemini, bounded by
the free-tier quota — or by import: `import_questions.py <batch>.json`, for
questions written and fact-checked by hand, costing no quota. The importer
validates the schema, skips duplicates by question text, and is the path to use
when quota is spent or a specific gap needs filling deliberately rather than by
whatever the generator happens to produce.

Both land as `review_status=pending`, and both leave the bank the same way:
through `review_questions.py`. Being hand-written buys no exemption — review is
also where an ambiguous or badly worded question gets caught, which is a
different failure from a factually wrong one.

Import batches carry a `sources` array per question, listing the official doc
pages each claim was checked against, and they are stored in `QuestionSource`
and shown by `review_questions.py` under CHECKED AGAINST. This matters at the
one moment it has to: the reviewer deciding whether a specific threshold is
real is the person who needs the citation, and the importer used to be the one
dropping it. A question with nothing recorded says so explicitly rather than
showing an empty space, because "unverified" and "verified elsewhere" have to
look different. Keep filling the field: a batch without it is
indistinguishable from one written from memory.

**Nothing reaches a user without review against the documentation.**
Only `approved` questions are served. This exists because prompt engineering
alone did not prevent factual errors — see below.

Who reviews changed on 2026-09-11, and the reasoning is worth keeping. The
original rule was that approval is a human action and nothing automated should
set `review_status=approved`. The maintainer then made the call that this gate
was not doing what it claimed: they don't know every certification's material
well enough to catch a wrong BGP community by eye, so a human read-through would
have been a rubber stamp. What actually catches errors is checking each specific
claim against the official documentation — and an agent with web access can do
that page by page, where a person without the domain knowledge can't. So:

- Review is done by Claude against the AWS docs. Every approved question carries
  a `review_note` saying what the verdict rests on, and `QuestionSource` rows
  for the pages consulted where a page was consulted. Questions reviewed without
  fetching a page say so in the note, so "verified" and "looked plausible" stay
  distinguishable.
- Content fixes found during review are applied before approval and recorded
  in the note. The first pass fixed five of 14 generated questions — all with
  the right answer marked and the error in the surrounding reasoning.
- **The human gate moved to user reports.** `review_questions.py --reported` is
  read by the maintainer, and a report never unpublishes anything on its own.
  This is the point where a person decides, and it's where a person is actually
  useful: a candidate's complaint comes with a reason and a specific claim.
- The self-review problem is real and acknowledged: 11 of the 35 questions were
  written by the same agent that reviewed them. The duplicate it missed at
  writing time (id 28, a copy of id 19) was caught at review time, which is
  some evidence the check works, not proof.

`apply_review_2026-09-11.py` is the record of that first pass: what was
approved, what was corrected, and why.

**The candidate sees two reasons, not the whole explanation.** The stored
`explanation` covers the correct answer and every distractor — right for a
reviewer, wrong for someone who picked D and has to find the one paragraph
about D in a wall that also covers B and C. `OptionExplanation` holds one
reason per option, and `POST /attempts` returns just the one for the pick and
the one for the correct answer; the UI falls back to the full text for any
question without rows. A separate table for the usual reason (no migrations;
`create_all` adds tables without touching `Question`). The generation prompt
now asks for `option_explanations` aligned with `options`, optional in the
schema so an older-style reply doesn't cost a repair call, and the shape
repair harvests per-option rationale when the model tucks it inside option
objects. The 34 approved questions were backfilled by hand from their
reviewed explanations — `option_explanations_2026-09-11.json` is the record —
which is restructuring of verified text, not new claims.

**`domain` and `concept_tags` are load-bearing, so neither is free text any more.**
`select_next_question()` prefers questions tagged with the user's weak
concepts and `analyze_weak_spots` reasons over the same strings, so a tag that
differs only in capitalisation is a different concept to the code: matching
under-matches silently, with no error and no symptom beyond worse adaptivity.
Both fields drifted exactly that way — the bank reached 12 distinct `domain`
values for 4 exam domains (the generator invented service categories like
`Storage` and `Messaging`, and produced both `Networking and Content Delivery`
and `Networking & Content Delivery`), alongside `Caching Strategies` /
`caching strategies` and `S3 bucket policies` / `S3 bucket policy`.

Fixed on 2026-09-10, in the two places the drift could enter:

- `EXAM_DOMAINS` in `db_schema.py` is the list of four; `import_questions.py`
  rejects anything else.
- **The generator is no longer asked for the domain.** Each `SEED_PLAN` entry
  carries its own `domain` and `seed_questions.py` writes that, not
  `result.domain`. The plan always knew which exam domain a job belonged to —
  asking the model to name it was what created the mess.
- `canonical_tags()` maps an incoming tag onto the spelling already in the
  bank, on both entry paths. It collapses spelling variants only, automatically.

Tags at different granularity were then merged by hand, per question rather
than globally, because direction is a judgement about each question's content.
The rule that came out of it: **merge toward the specific form only when it is
true of every question carrying the general one.** Where it wasn't, the general
tag was made specific to its own service instead — the Route 53 question
carried bare `Failover` and `Health Checks`, and merging those into
`RDS failover behaviour` or `Auto Scaling group health checks` would have
labelled it as a question about a service it never mentions; it became
`Route 53 failover` and `Route 53 health checks`.

A service-level tag sitting inside a concept-level one (`DynamoDB` within
`DynamoDB partition key design`) is **not** a duplicate, and substring
detection over-reports it. The remaining question tagged `DynamoDB` is about
GSI vs LSI and read consistency, not partition keys; merging it would state
something false about the question to tidy a list.

The existing 14 generated rows were reassigned by reconstructing each job's
domain from the plan and cross-checking against its concept tags, not by
reading the questions and guessing. `test_taxonomy.py` guards all of it,
because this class of regression is invisible at runtime.

**Adaptivity lives in selection, not generation.**
`select_next_question()` filters to approved + unanswered, then prefers
questions tagged with the user's weak concepts. Same personalisation as
generating on the fly, without the API cost.

**AI is used at exactly one point: offline question generation**
(`seed_questions.py` — not the import path, which is AI-free end to end).
Taking a test makes no model call.

The explanation of a wrong answer was a second, live call until 2026-09-11,
justified as "can't be pre-generated because it depends on which wrong option
they picked". That justification was wrong on inspection: the generation
prompt already requires the stored `explanation` to say why *each* distractor
is wrong, so one text covers every pick. Dropping the live call removed three
things at once — the only model output that reached users without review, the
only test-time dependency on Gemini quota (the maintainer hit it on the very
first live demo), and the whole `explanation_error` degradation path. The
candidate now reads exactly the text the reviewer approved.

## Accuracy: the hard-won lesson

The core value proposition is granular technical detail, which is also exactly
where LLMs hallucinate most confidently. Three real failures during development:

1. Mixed up AWS inbound (7224:9xxx) and outbound (7224:8xxx) BGP community
   families; the actually-correct value wasn't even among the options.
2. With a much stricter prompt, produced a confident claim about SiteLink +
   NO_EXPORT behaviour that official AWS docs don't support.
3. With grounding enabled, generated a correct answer but volunteered two
   *invented* BGP values in the takeaway — contradicting a correct value the
   same model had produced two calls earlier.

Conclusions baked into the current design:
- Google Search grounding (`tools=[{"type": "google_search"}]`) is required for
  any specific value/threshold/code. It reduces hallucination but does not
  eliminate it.
- Risk concentrates in **volunteered extras** — facts the model adds that
  nobody asked for — not in the fact being asked about.
- `detail_recall` questions are riskier than `conceptual` ones.
- Checking every claim against the documentation before approval is the
  structural answer; user reports are the safety net. Keep the gate — what
  changed is who operates it, not whether it exists.
- Grounding sometimes beats stale training knowledge: it correctly surfaced that
  AWS removed the 30-day S3 Standard-IA transition minimum in July 2026.

**Users can report a question** (`POST /questions/{id}/report`, plus the
control under the quiz feedback). This closes the gap this section used to
list as outstanding: review catches what a reviewer noticed, while a candidate
revising one topic in depth notices things a reviewer didn't.

Three decisions worth keeping:

- **A report never unpublishes anything.** It raises the question in the
  reviewer's queue and nothing more — otherwise one user could empty everyone
  else's bank. There is a test asserting a reported question is still served.
- **`QuestionReport` is a separate table, not a column on `Question`.** A
  report is an event: several users can flag the same question, each with
  their own reason. It also sidestepped the missing migrations — `create_all`
  adds a new table without touching existing ones, whereas a new column on
  `Question` would have meant deleting `cert_prep.db` and the 24 questions in
  it.
- **A stale `user_id` is dropped, not rejected.** Identity is a guest id from
  `localStorage`, so stale ids are normal, and the report matters more than
  knowing who sent it. Reports from a known user are deduplicated, so a double
  click can't inflate the count the queue sorts on.

`review_questions.py --reported` walks the flagged questions, most-reported
first, and offers keep-or-reject. Those are already approved and being served,
which makes that queue more urgent than the pending one.

## Hard constraint: Gemini free tier

**5 requests/minute, 20 requests/day, per model.** This is small enough to shape
development:
- Every wrong answer tested in the UI costs one Gemini call.
- `seed_questions.py --delay 13` keeps under the per-minute limit and stops
  itself on the first 429 instead of burning the remaining budget.
- When building/testing the frontend, prefer mocked data or already-answered
  questions over repeatedly triggering explanations.
- **Google Search grounding has its own quota, and it is the real ceiling.**
  Isolated on 2026-09-10: with the daily generate quota freshly reset, on the
  same model in the same minute, a plain call succeeded, a call with
  `response_format` succeeded, and a call with
  `tools=[{"type": "google_search"}]` returned 429. The grounding limit is
  separate from `generate_content_free_tier_requests` and independent of the
  model, so **switching models does not get around it** — that is why
  gemini-3.7-flash and gemini-3.8-flash both failed instantly on 2026-09-09
  once 2.5-flash was spent. A 429 whose message names no model or metric is
  this one; a 429 naming `limit: 20, model: …` is the per-model generate limit.
  Diagnose by retrying the same call without `tools`: if it succeeds, it is
  grounding.
- Since grounding is mandatory for any specific value or threshold (see
  Accuracy below), an exhausted grounding quota blocks generation entirely —
  dropping the tool to keep working would remove the one control that made
  generated numbers trustworthy. When it runs out, use `import_questions.py`
  instead of generating without grounding.
- `MODEL` reads `GEMINI_MODEL` from the environment so a switch needs no code
  edit. The code default is `gemini-2.5-flash` (see the weak-spots notes
  below for why), **but that model is closed to new Google projects**: the
  production key, created on 2026-09-15 for the first deploy, got
  `404 … no longer available to new users … use gemini-3.6-flash` on the
  very first `/weak-spots` call. `render.yaml` therefore sets
  `GEMINI_MODEL=gemini-3.6-flash`, verified live the same day (14.7s, sound
  analysis). The local key predates the cutoff and still gets 2.5-flash.
  A `_interact()` fallback doesn't help here: the 404 isn't a 5xx, and it's
  the same answer for every request on that key.
- The AI Studio rate-limit dashboard defaults to *peak usage over 28 days*,
  not today's consumption. Reading it as "requests left today" is wrong, and
  cost one wasted seeding attempt.
- **A parse failure costs two requests, not one.** `_parse_structured()`
  answers a shape it can't validate with a reformatting call, so a run of 17
  jobs with 3 shape failures spends 20 requests and hits the daily cap three
  jobs early. Worse, in the run where this was measured, the repair call came
  back in the *same* wrong shape — two requests spent, question lost. That is
  why `_normalise()` / `_coerce_question_shape()` keep growing: absorbing a
  deviation locally is a quota feature, not tidiness.

### Shape drift is routine, and it is structural, not semantic

gemini-2.5-flash returned the right content under the wrong structure often
enough to matter (4 failures in 17 during one seeding run, which is why it is
no longer the default): options as
`{"label": "A", "text": ...}` objects, the answer as `finalAnswer: "A"`
instead of an index, `problemStatement` instead of `question`, the
classification fields nested under a wrapper, `explanation` as an object of
per-option rationales. `test_parsing.py` pins these — every case in it is a
shape seen live, so deleting one re-opens a hole that costs quota.

The line the repair must not cross: it renames, unnests and converts a letter
to an index, and it stops there. When the model omits `domain` or
`concept_tags` outright, validation still fails and the question is dropped.
Filling those in would mean the bank quietly containing metadata nobody
wrote — the exact failure the review gate exists to catch.

Failures now write the raw model text to `api/failed_generations/`
so a spent request leaves something reviewable instead of only a traceback.

## Backend API

Run: `uvicorn api:app --reload` (port 8000) from `api`, venv active,
`GEMINI_API_KEY` set. CORS already allows `http://localhost:3000`.

Read `api.py` for exact request/response shapes. Endpoints:
- `POST /users`
- `GET /questions/next?user_id=&certification=` — never returns `correct_index`
  or `explanation`; the frontend must not be able to read the answer
- `POST /attempts` — returns correctness + AI explanation if wrong
- `GET /users/{id}/weak-spots`
- `POST /users/{id}/study-plan`

## Current state

Backend done, 41 tests passing (`test_api.py`, `test_parsing.py`,
`test_taxonomy.py`). **The bank reached its 100-question target on 2026-09-22**:
101 questions, 100 approved and 1 rejected as a duplicate. 14 came from the
Gemini seed run of 2026-09-08, 10 were imported by hand on 2026-09-10, 11 more
in `questions_batch_2.json` / `_3.json`, and 66 in three hand-written batches
on 2026-09-22 (`questions_batch_4.json` … `_6.json`, each with its own
`apply_review_2026-09-22*.py`).

Coverage now matches the exam's published domain weighting **exactly** —
30 / 26 / 24 / 20 across Secure / Resilient / High-Performing /
Cost-Optimized — and is 58 % detail-recall, 21 % hard. Keep both ratios when
the bank grows: the weighting is what makes a session representative, and the
detail-recall share is the product.

**Write batches docs-first.** Fetch and read each source page *before*
drafting its question, rather than writing from memory and checking
afterwards. That order is the whole value of the batches: it is how the bank
got questions pivoting on the S3 object ceiling being 50 TB (not 5), NAT
gateways having a regional availability mode, Compute Savings Plans at "up to
66%", Lambda giving one vCPU at 1,769 MB, Aurora Serverless scaling to 0 ACUs
(0.5 was the floor), cross-zone load balancing being *always on at the load
balancer level* for an ALB, a transit gateway carrying 8500 bytes except over
VPN, and S3 Replication Time Control being documented as 99.9 % within 15
minutes (not the 99.99 % it is usually quoted as). Every one of those is a
place where the material candidates revise from is stale — which is the
product's whole claim, and it does not hold if the questions are written from
the same stale memory.

Near-neighbour questions are allowed when the *pivot* differs, not the
service: the bank deliberately holds two AWS Backup questions, two CloudWatch,
two Athena and two Parameter Store, each pair asking about a different fact.
What is not allowed is a general tag beside a specific one — three batches in
a row needed a tag fix before approval (`cost optimization` next to
`storage cost optimization`, `monitoring` next to `security monitoring`,
`cross-Region replication` folded onto the S3 tag by `canonical_tags()`).
Check `concept_tags` against the approved bank before running the review
script; it is the one recurring defect in hand-written batches.

Services still untouched, if the bank ever grows past 100: SNS and SQS
FIFO specifics, Kinesis Data Firehose, Redshift, Compute Optimizer,
IAM Identity Center, Network Firewall, Outposts, Local Zones.

The weak-spots page has only been exercised on its failure path — its happy
path needs a `GEMINI_API_KEY` and one live call.

Data note: `cert_prep.db` is SQLite for dev, no migrations set up. Schema
changes currently mean deleting the file — or, as every addition since the
reports table has done, adding a new table instead of a column, which
`create_all` handles. Alembic is still the right answer before real users.

**Deployed on 2026-09-15**: API at `https://lacuna-api.onrender.com`
(Render, blueprint from `render.yaml`), frontend at
`https://lacuna-zeta.vercel.app` (Vercel, root directory `web`,
`NEXT_PUBLIC_API_URL` set — it is inlined at build time, so changing it
means a redeploy without build cache, which cost one round the first time).
`ALLOWED_ORIGINS` on Render carries the Vercel origin. The full quiz flow
and `/weak-spots` were exercised in the browser against production the same
day. The free Render instance sleeps after 15 minutes idle; the first
request after that waits ~10s on "Loading question…", which is the reason
for the uptime ping `render.yaml` mentions.

**Production is Postgres on Neon, at zero cost, and the choice was forced.**
The constraint was "spend nothing". The free backend host (Render) wipes its
disk on every restart, so SQLite there would lose users and history — and the
guest-session repair exists precisely because that happened locally. Neon's
free Postgres is the persistent piece; SQLModel needs no model changes, only
`DATABASE_URL` (rewritten to the psycopg 3 driver scheme, since Neon hands out
`postgresql://`). The bank is copied there with `migrate_bank.py`, which
carries questions, sources and option explanations only, preserves ids so
the foreign keys line up, and moves Postgres's sequences past them so the next
approval doesn't collide. Users and attempts are never copied: they belong to
whichever database the users are actually in.

## Frontend goals

1. ~~Quiz flow: pick certification → answer → feedback → AI explanation if wrong~~
2. ~~Weak-spots dashboard~~
3. ~~A public landing page (part of why Next.js was chosen over Vite — SEO for
   terms like "AWS SAA practice questions")~~ — done 2026-09-15, see below.

## Frontend decisions

**No auth: the browser holds a guest user id.** The API identifies users by a
numeric id, so on first visit the client creates a throwaway user
(`guest-<uuid>@lacuna.local`) and keeps the id in `localStorage`
(`lib/session.ts`). Clearing site data creates a new learner and loses history —
acceptable while there's nothing to protect, and the seam real auth replaces.

The stored id is only as durable as the database behind it, and the dev
database gets recreated. A browser that had visited once kept sending an id
that no longer existed and was stuck on "User not found" for good — found the
first time the maintainer opened the app in their own browser rather than the
one used during development. `withGuestUser()` now treats that answer as
"start over": discard the id, create a fresh guest, retry once. It also keeps
that 404 apart from the other one the quiz sees, "bank exhausted", which is a
normal end state; before, a stale session could read as "you've answered every
question".

**The landing page at `/` is static, and its sample question is a copy.**
The page's one interactive element is a real reviewed question answered in
place (id 30, the S3 Standard-IA one — the product's thesis in a single
question: one 30-day rule was removed in 2026, the other wasn't). It lives in
`lib/sample-question.ts` as a verbatim copy rather than being fetched,
because the Render instance sleeps and the first thing a visitor from a
search result would see is a cold start. The cost is that the copy can drift
if the bank's question 30 is ever corrected — the file says so. Its answer
being public is accepted: it is one of 34, and the sources shown with it
are the point.

SEO is the landing page only: `sitemap.ts` lists `/`, `robots.ts` disallows
`/quiz` and `/weak-spots` (per-session state behind a guest id, nothing a
crawler should index). `lib/site.ts` holds the public origin for canonical,
Open Graph and the sitemap; `NEXT_PUBLIC_SITE_URL` overrides it when the
domain changes. The share card is `app/opengraph-image.tsx`, generated from
the hero's words so it can't drift from the page.

**Amber is the one accent, and it means "the thing to pin down".** Chosen
on 2026-09-15 over indigo/ink: the highlighter on the page is the most
immediate study cue, and it doesn't collide with the two semantic colours
already in use (emerald = correct, red = wrong). The rule that keeps it a
language rather than decoration: it appears only where a specific detail
is being marked — the gaps and labels in the hero illustration, the
`Detail recall` badge (never `Conceptual`), the option you've selected but
not yet submitted, the "Checked against" sources box, section eyebrows and
the pipeline icons. Never for running text (amber on white fails contrast)
and never on the primary button. Tokens: `amber-500`/`amber-400` for
strokes, `amber-700`/`amber-300` for text, light/dark respectively.

**The logo is four tiles, one of them missing** — direction A of the
exploration on 2026-09-15, chosen over a missing-letter wordmark, philological
brackets and a line-with-a-gap because it is the hero illustration reduced
to a mark, so the site and the mark say the same thing. The geometry lives
in three places that can't share code: `components/Logo.tsx` (header,
Tailwind tokens), `app/icon.svg` (favicon, its own dark-mode media query)
and the Satori-rendered `app/opengraph-image.tsx` / `app/apple-icon.tsx`.
Change all of them together. The exploration canvas with the three
unchosen directions is a Claude Design artifact, linked from the session
memory rather than the repo.

The layout no longer fixes the content width: `components/Container.tsx`
is the reading column the app pages opt into, and the landing sets its own
(wider hero beside an inline-SVG illustration, full-bleed bands). The
illustration and the pipeline icons are inline SVG styled with the same
zinc utilities as the text, so light/dark needs no second asset.

`.claude/launch.json` starts `next dev` through the Node 20 binary and
Next's real JS entry (`node_modules/next/dist/bin/next`), not the
`.bin/next` shim — that shim is a shell script and Node refuses it.

**`/weak-spots` is the one live model call left, and it is treated as such.**
Verified working for the first time on 2026-09-15 — the analysis was good:
repeated misses on IAM evaluation flagged as a true gap, a single miss on S3
bucket policies correctly downgraded to an isolated mistake. Getting there
surfaced three things, all fixed the same day:

- *The model can hang instead of failing.* "gemini-3.7-flash is currently
  experiencing high demand" arrived once as a fast 500 and once as a request
  that sat for minutes. Both are the model's problem, not the request's, so
  `_interact()` retries once on `FALLBACK_MODEL` after a 5xx or a client
  timeout. A 429 is deliberately not retried: grounding quota is shared across
  models, so a blind retry would usually spend a request to fail the same way.
- *The default model was the wrong one.* Across three days gemini-3.7-flash
  never completed a single call in this project while 2.5-flash completed
  dozens, so 2.5 is now the default and 3.7 the fallback. Evidence, not
  preference.
- *A page must not cost a request per visit.* The analysis is a pure function
  of the answer history, so `WeakSpotSnapshot` stores it keyed on the attempt
  count: revisits are instant and free, a new answer invalidates. Before this,
  a refresh cost as much as generating a question — and React strict mode in
  dev fired the effect twice, so two.

Timeouts are per use: 60s for grounded generation, 45s for the two
interactive calls (weak spots, study plan) — 20s was tried first and cut off
real 19-second answers. There is nothing to degrade to on that page, so a
failure says what failed instead of showing an empty dashboard.

**Unhandled 500s set the CORS header themselves.** Starlette generates them
above `CORSMiddleware`, so the browser saw an opaque "failed to fetch" and the
frontend blamed an unreachable API for a server that had answered. The handler
in `api.py` echoes the allowed origin so the real status survives.

**Question text is Markdown and must be rendered as such.** The generator emits
bold thresholds, bulleted requirements and fenced JSON (IAM policies). Rendered
as plain text, backticks and `**` land in the middle of exactly the detail the
question turns on. `components/Markdown.tsx` renders it with `react-markdown`;
raw HTML stays disabled, since the content is model-generated.

The project is also a portfolio piece for LinkedIn, so the UI should be
presentable, and the accuracy/review story is worth surfacing in the product
itself rather than hiding.
