<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

When we make a decision in this project that wouldn't be obvious to someone reading the code later — an architectural choice, a constraint we hit, a bug that changed how we do something, a rejected approach and why — update PROJECT_CONTEXT.md to record it.

Write the reasoning, not just the outcome: "X because Y" rather than "we use X". Keep it concise, and edit or remove entries that become outdated instead of letting the file grow into a changelog.

Don't record routine implementation details that the code already makes clear.
