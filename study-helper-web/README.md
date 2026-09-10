# study-helper-web

Next.js frontend for Study Helper. See the [root README](../README.md) for what
the project is and why it is built this way.

## Running

**Node 20+ and pnpm**, not npm — npm has a bug with Tailwind's native optional
dependencies.

```bash
pnpm install
pnpm dev
```

The API base URL comes from `NEXT_PUBLIC_API_URL` in `.env.local`, defaulting to
`http://localhost:8000`. The backend must be running: start it from
`study-helper-beta/` before loading a quiz.

## What's here

| | |
|---|---|
| `app/page.tsx` | Certification picker, plus the accuracy story that motivates the product. |
| `app/quiz/` | The quiz flow: answer, feedback, explanation when wrong, report control. |
| `app/weak-spots/` | Pattern analysis over answer history. |
| `lib/api.ts` | Typed client mirroring the FastAPI response models. |
| `lib/session.ts` | Guest user id in `localStorage` — there is no auth yet. |
| `components/Markdown.tsx` | Question text is Markdown, including fenced JSON for IAM policies. |

## Things that will surprise you

**Questions run out.** A 404 from `/questions/next` means every approved
question has been answered. That is a normal end state, not an error — the bank
only serves human-reviewed questions rather than inventing more on demand.

**The answer is not in the DOM.** `/questions/next` never returns
`correct_index` or `explanation`; both arrive only after an attempt is
submitted, so the frontend cannot leak the answer.

**A missing explanation is not a failure.** When the model API is out of quota,
`POST /attempts` still returns correctness with an `explanation_error`, and the
UI says why the explanation is missing. The answer still counted.
