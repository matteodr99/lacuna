# Project context

Adaptive study platform for cloud certifications (AWS, Azure, GCP). It targets
the gap that experienced candidates actually have: not "I don't understand the
concepts" but "I don't remember the granular details layered on top of concepts
I already know" — route propagation rules, specific thresholds, edge cases.

Two projects, kept separate on purpose:
- `study-helper-beta/` — Python backend (FastAPI + SQLModel + Gemini)
- `study-helper-web/` — Next.js frontend (TypeScript, Tailwind, App Router)

The backend is working and tested. Do not rewrite it in TypeScript. Next.js does
the UI and talks to FastAPI over HTTP.

## Toolchain traps

`study-helper-web` uses **pnpm**, not npm (npm has a bug with Tailwind's native
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

In `study-helper-beta`, the venv was created at an older path, so its `pip`
shebang is dead. Use `.venv/bin/python -m pip` and `.venv/bin/python -m pytest`.

## Architecture decisions that aren't obvious from the code

**Questions are pre-generated offline, not generated per user.**
`seed_questions.py` batch-generates into a question bank; users are served from
that bank via `GET /questions/next`. Taking a test triggers zero Gemini calls.
This is deliberate — it fixes cost, latency, and (most importantly) allows human
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

**Nothing reaches a user without human review.**
`review_questions.py` is a CLI to approve/reject; only `approved` questions are
served. This exists because prompt engineering alone did not prevent factual
errors — see below. Approval is a human action by design: nothing automated,
including an agent working in this repo, should set `review_status=approved`.

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

**AI is used at exactly two points:**
1. Offline question generation (`seed_questions.py`) — not the import path,
   which is AI-free end to end
2. Explaining a wrong answer, live, when the user gets one wrong — this can't be
   pre-generated because it depends on which wrong option they picked.

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
- Human review is the structural answer. Keep the review gate.
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
  edit. Default is `gemini-3.7-flash` — chosen because 2.5-flash produced the
  shape drift below, but **not yet verified against a successful call**.
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

Failures now write the raw model text to `study-helper-beta/failed_generations/`
so a spent request leaves something reviewable instead of only a traceback.

## Backend API

Run: `uvicorn api:app --reload` (port 8000) from `study-helper-beta`, venv active,
`GEMINI_API_KEY` set. CORS already allows `http://localhost:3000`.

Read `api.py` for exact request/response shapes. Endpoints:
- `POST /users`
- `GET /questions/next?user_id=&certification=` — never returns `correct_index`
  or `explanation`; the frontend must not be able to read the answer
- `POST /attempts` — returns correctness + AI explanation if wrong
- `GET /users/{id}/weak-spots`
- `POST /users/{id}/study-plan`

## Current state

Backend done, 34 tests passing (`test_api.py`, `test_parsing.py`,
`test_taxonomy.py`). The
question bank holds 35 questions, all `pending`: 14 from the Gemini seed run of
2026-09-08, 10 imported by hand on 2026-09-10, 6 more (`questions_batch_2.json`)
covering the six jobs the seed run never produced, and 5
(`questions_batch_3.json`) on ground the SEED_PLAN never covered at all. Nothing is approved, so
`/questions/next` currently serves nothing and the quiz shows its
bank-exhausted state until `review_questions.py` is run. Frontend has the quiz flow and
the weak-spots dashboard; the public landing page is still to do.

The weak-spots page has only been exercised on its failure path — its happy
path needs a `GEMINI_API_KEY` and one live call.

Data note: `cert_prep.db` is SQLite for dev, no migrations set up. Schema
changes currently mean deleting the file. Alembic before production.

## Frontend goals

1. ~~Quiz flow: pick certification → answer → feedback → AI explanation if wrong~~
2. ~~Weak-spots dashboard~~
3. A public landing page (part of why Next.js was chosen over Vite — SEO for
   terms like "AWS SAA practice questions"). The current `/` is a certification
   picker, not that page.

## Frontend decisions

**No auth: the browser holds a guest user id.** The API identifies users by a
numeric id, so on first visit the client creates a throwaway user
(`guest-<uuid>@study-helper.local`) and keeps the id in `localStorage`
(`lib/session.ts`). Clearing site data creates a new learner and loses history —
acceptable while there's nothing to protect, and the seam real auth replaces.

**A failed explanation is not an error.** On the Gemini free tier an exhausted
quota is routine, and correctness is already known without a model call, so
`POST /attempts` catches an `explain_wrong_answer` failure and returns
`explanation_error` alongside the result instead of a 500. The answer still
counts and the UI says why the explanation is missing. `/weak-spots` can't
degrade the same way — the whole page is that one call — so it reports the
quota as the likely cause.

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
