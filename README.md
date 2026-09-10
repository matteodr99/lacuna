# Study Helper

Adaptive practice for cloud certifications (AWS, Azure, GCP), aimed at the gap
experienced engineers actually have.

That gap is rarely conceptual. Someone who has run production workloads for
years understands why an explicit deny wins — what they don't remember is that
a local secondary index can only be created with the table, that S3 removed the
30-day minimum for transitions to Standard-IA but kept the 30-day *billing*
minimum, or which BGP community family applies to inbound versus outbound
routes. Study Helper targets that layer: the granular details stacked on top of
concepts you already know.

Which is also, inconveniently, exactly where language models hallucinate most
confidently. Most of the design below exists because of that.

## How it works

```
seed_questions.py ─┐
 (Gemini, grounded) │
                    ├──▶  question bank  ──▶  review_questions.py  ──▶  served to users
import_questions.py ┘      (all pending)        (a human decides)         (approved only)
 (hand-written JSON)
```

**Questions are generated offline, never per user.** Taking a test triggers zero
model calls: questions are served from a pre-built bank. That fixes cost and
latency, but the real reason is the third one — it puts a human between the
model and the candidate. There is a test that fails on purpose if anyone
reintroduces a model call into the question-serving path.

**Nothing reaches a user without review.** Everything lands as `pending`,
whether a model wrote it or a person did. Being hand-checked buys no exemption:
review is also where an ambiguous or badly worded question gets caught, which is
a different failure from a factually wrong one.

**Adaptivity lives in selection, not generation.** `select_next_question()`
filters to approved and unanswered, then prefers questions tagged with the
user's weak concepts. Same personalisation as generating on the fly, without the
per-question cost, latency, or the risk of an unreviewed answer reaching anyone.

**Users can report a question.** A report raises it in the reviewer's queue and
never unpublishes it — otherwise one user could empty everyone else's bank.
Review catches what a reviewer noticed; a candidate revising one topic in depth
notices things a reviewer didn't.

## Why the review gate exists

It isn't a formality bolted on for appearances. Prompt engineering alone did not
prevent factual errors. Three real failures during development:

1. The model mixed up AWS inbound (`7224:9xxx`) and outbound (`7224:8xxx`) BGP
   community families — and the correct value wasn't even among the options.
2. With a much stricter prompt, it produced a confident claim about SiteLink and
   `NO_EXPORT` behaviour that official AWS documentation doesn't support.
3. With search grounding enabled, it generated a correct answer but volunteered
   two *invented* BGP values in the takeaway, contradicting a correct value the
   same model had produced two calls earlier.

What that led to:

- Search grounding is mandatory for any specific value, threshold or code. It
  reduces hallucination without eliminating it.
- The risk concentrates in **volunteered extras** — facts the model adds that
  nobody asked for — not in the fact being asked about.
- `detail_recall` questions are riskier than conceptual ones, and they are also
  the product's differentiator, so they get the most review attention.
- Human review is the structural answer. Everything else is mitigation.

Grounding also earns its cost in the other direction: it correctly surfaced that
AWS removed the 30-day S3 Standard-IA transition minimum in July 2026, which no
model's training data would have carried.

## Architecture

Two projects, deliberately separate. The backend is Python because that is where
the model SDK and the data layer are comfortable; the frontend is Next.js partly
for a future public landing page, since "AWS SAA practice questions" is a search
term worth ranking for.

| | |
|---|---|
| `study-helper-beta/` | FastAPI + SQLModel + Gemini. Generation, review, serving, analysis. |
| `study-helper-web/` | Next.js (TypeScript, Tailwind, App Router). Talks to the API over HTTP. |
| `PROJECT_CONTEXT.md` | The decisions and constraints neither codebase makes obvious. |

### API

| Endpoint | Purpose |
|---|---|
| `POST /users` | Create a user. |
| `GET /questions/next` | Next approved, unanswered question, steered by weak concepts. Never returns `correct_index` or `explanation`. |
| `POST /attempts` | Submit an answer; returns correctness and, if wrong, an explanation. |
| `POST /questions/{id}/report` | Flag a question as wrong, stale or ambiguous. |
| `GET /users/{id}/weak-spots` | Pattern analysis over answer history. |
| `POST /users/{id}/study-plan` | A time-budgeted plan to the exam date. |

The model is used at exactly two points: offline question generation, and
explaining a wrong answer live — the latter can't be pre-generated because it
depends on which wrong option the candidate picked.

## Running it

Backend, from `study-helper-beta/` with a `GEMINI_API_KEY` in `.env`:

```bash
python -m venv .venv && .venv/bin/pip install fastapi uvicorn sqlmodel google-genai pytest
.venv/bin/python -m uvicorn api:app --reload --port 8000
```

Frontend, from `study-helper-web/` — **Node 20+ and pnpm**, not npm (npm has a
bug with Tailwind's native optional dependencies):

```bash
pnpm install && pnpm dev
```

Tests: `.venv/bin/python -m pytest` — 32 passing.

Filling the bank:

```bash
python seed_questions.py --plan                 # what it would generate
python seed_questions.py --jobs 7,8,11 --delay 13   # generate specific jobs
python import_questions.py batch.json --dry-run     # validate a hand-written batch
python review_questions.py                      # the human gate
python review_questions.py --reported           # re-review what users flagged
```

## Constraints worth knowing

**The Gemini free tier shapes development**: 5 requests/minute, 20/day, per
model. Small enough that a wasted call matters.

**Google Search grounding has its own quota, separate from the model's**, and
that one is the real ceiling. Measured directly: with the daily generate quota
freshly reset, on the same model in the same minute, a plain call succeeded, a
call with a JSON response schema succeeded, and a call with the search tool
returned 429. Switching models does not get around it. Since grounding is
mandatory for any specific value, an exhausted grounding quota blocks generation
entirely — dropping the tool to keep working would remove the one control that
makes generated numbers trustworthy. That is what the hand-written import path
is for.

**A parse failure used to cost two requests, not one.** When model output failed
schema validation, the code spent a second call asking the model to reformat it
— which came back in the same wrong shape. Seventeen jobs with three shape
failures spent the full daily twenty and hit the cap three jobs early. Shape
drift is now repaired locally and deterministically: labelled option objects,
an answer given as a letter, a wrapper object around the classification fields.
`test_parsing.py` pins every shape seen live. The repair renames, unnests and
converts a letter to an index — and stops there. When the model omits a field
outright, validation still fails and the question is dropped, because inventing
it is the exact failure the review gate exists to catch.

## Current state

The bank holds **35 questions, all pending review** — nothing is approved, so
`/questions/next` currently serves nothing and the quiz shows its
bank-exhausted state. 14 were generated with Gemini; 21 were written by hand and
fact-checked against official documentation, each batch carrying a `sources`
array naming the pages every claim was checked against.

Known gaps, in rough priority order: no auth (the browser holds a guest user id
in `localStorage`), no migrations (a schema change currently means deleting
`cert_prep.db`), no study-plan UI despite the endpoint existing, and no public
landing page.
