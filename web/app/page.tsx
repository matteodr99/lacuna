import type { Metadata } from "next";
import Link from "next/link";
import SampleQuestion from "@/components/SampleQuestion";
import { CERTIFICATIONS } from "@/lib/certifications";
import { SITE_URL } from "@/lib/site";

/**
 * The public landing page — the part of the app search engines are meant
 * to find. Everything on it is static and renders on the server; the only
 * client component is the sample question, and it makes no request.
 *
 * The page argues one thing in three ways: the gap it targets (hero), the
 * product doing it (a real reviewed question, with its sources), and how
 * that trust is built (the pipeline). Nothing here is claimed that the
 * README doesn't also document.
 */

const PRIMARY = CERTIFICATIONS.find((c) => c.available) ?? CERTIFICATIONS[0];
const QUIZ_HREF = `/quiz?certification=${encodeURIComponent(PRIMARY.id)}`;

export const metadata: Metadata = {
  title: {
    absolute: "Lacuna — AWS SAA-C03 practice questions for experienced engineers",
  },
  description:
    "Free AWS Solutions Architect Associate (SAA-C03) practice questions aimed at the details experienced engineers forget — thresholds, edge cases, rules that changed. Every claim checked against the official AWS documentation before it reaches you. No account needed.",
  alternates: { canonical: "/" },
};

const STEPS: { title: string; body: React.ReactNode }[] = [
  {
    title: "Written offline, never during a test",
    body: (
      <>
        Questions are generated ahead of time — with search grounding for any
        specific value or threshold — or written by hand. Taking a test makes
        zero model calls: what you see is served from a bank, so it is fast,
        free, and can be checked before anyone sees it.
      </>
    ),
  },
  {
    title: "Every claim checked against the docs",
    body: (
      <>
        Nothing is served until each threshold, code and behavioural claim has
        been looked up in the official documentation. The pages consulted are
        recorded against the question. Generation alone wasn&apos;t enough:
        during development it produced confident, wrong BGP community values —
        so review is a structural step, not a formality.
      </>
    ),
  },
  {
    title: "Two reasons, not a wall of text",
    body: (
      <>
        After you answer, you read why the option you picked is wrong and why
        the correct one is right — the text a reviewer approved, not something
        generated on the spot. If a question still looks wrong, report it from
        the question itself; a person reads every report.
      </>
    ),
  },
  {
    title: "Adaptive, with the model kept out of the loop",
    body: (
      <>
        Your misses steer which questions you see next. The weak-spots view
        separates a repeated gap from a one-off slip, and a gap in
        understanding from a gap in recall, because the two need different
        revision.
      </>
    ),
  },
];

const FAQ: { q: string; a: string }[] = [
  {
    q: "Are these real SAA-C03 exam questions?",
    a: "No. Lacuna is not an exam dump. Every question is original and written to test a specific documented rule, value or behaviour that the exam objectives cover. What makes them useful is that each one has been checked against the official AWS documentation, not that it resembles the exam.",
  },
  {
    q: "How is a question verified?",
    a: "Each specific claim in a question — a threshold, a limit, a default, a behaviour — is looked up in the official documentation before the question is approved. The pages consulted are recorded with the question, and the review note says what was checked and what was corrected. Questions that fail review are not served.",
  },
  {
    q: "Is AI used while I practise?",
    a: "Not for the questions or the explanations. Questions are generated or written ahead of time and reviewed; answering one makes no model call. The one live model call is the optional weak-spots analysis of your answer history, and its output is an assessment of you, not a fact about AWS.",
  },
  {
    q: "Do I need an account?",
    a: "No. Your progress is kept in your browser under a guest session. Clearing site data starts you over.",
  },
  {
    q: "Which certifications are covered?",
    a: "AWS Solutions Architect Associate (SAA-C03) today. Azure Administrator Associate (AZ-104) and Google Professional Cloud Architect are planned; their banks are not seeded yet.",
  },
  {
    q: "Why 'Lacuna'?",
    a: "A lacuna is a gap — in a text, in knowledge. It is what the weak-spots analysis finds and what the questions are written to fill.",
  },
];

const JSON_LD = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      name: "Lacuna",
      url: SITE_URL,
      description:
        "Adaptive practice questions for cloud certifications, checked against the official documentation.",
    },
    {
      "@type": "FAQPage",
      mainEntity: FAQ.map(({ q, a }) => ({
        "@type": "Question",
        name: q,
        acceptedAnswer: { "@type": "Answer", text: a },
      })),
    },
  ],
};

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
      {children}
    </h2>
  );
}

export default function Home() {
  return (
    <div className="flex flex-col gap-16">
      <script
        type="application/ld+json"
        // Static, authored above — nothing user-supplied reaches it.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
      />

      <section className="flex flex-col gap-6 pt-4">
        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          The details you forget, not the concepts you know
        </h1>
        <p className="max-w-xl text-lg leading-8 text-zinc-600 dark:text-zinc-400">
          Practice questions for the AWS Solutions Architect Associate exam,
          aimed at experienced engineers. Not &ldquo;what is a VPC&rdquo; —
          the thresholds, edge cases and rules that changed last year, each
          one checked against the official documentation before you see it.
        </p>
        <div className="flex flex-wrap items-center gap-4">
          <Link
            href={QUIZ_HREF}
            className="rounded-md bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
          >
            Start practising — {PRIMARY.provider} {PRIMARY.name}
          </Link>
          <a
            href="#how-it-works"
            className="text-sm text-zinc-600 underline-offset-4 hover:underline dark:text-zinc-400"
          >
            How questions are checked
          </a>
        </div>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Free. No account. Progress stays in your browser.
        </p>
      </section>

      <section className="flex flex-col gap-5" aria-labelledby="try-one">
        <div className="flex flex-col gap-1">
          <SectionHeading>
            <span id="try-one">Try one</span>
          </SectionHeading>
          <p className="text-zinc-600 dark:text-zinc-400">
            A question from the bank, exactly as it is served. Easy to get
            wrong if you learned S3 before 2026 — one of the two rules it
            turns on changed that year.
          </p>
        </div>
        <SampleQuestion quizHref={QUIZ_HREF} />
      </section>

      <section id="how-it-works" className="flex flex-col gap-6 scroll-mt-8">
        <SectionHeading>How it works</SectionHeading>
        <ol className="grid gap-4 sm:grid-cols-2">
          {STEPS.map((step, index) => (
            <li
              key={step.title}
              className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <span className="font-mono text-xs text-zinc-400 dark:text-zinc-500">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3 className="font-medium">{step.title}</h3>
              <p className="text-sm leading-6 text-zinc-600 dark:text-zinc-400">
                {step.body}
              </p>
            </li>
          ))}
        </ol>
        <p className="text-sm leading-6 text-zinc-500 dark:text-zinc-400">
          The pipeline, the failures that shaped it and the review records are
          all in the{" "}
          <a
            href="https://github.com/matteodr99/lacuna"
            className="underline decoration-zinc-300 underline-offset-4 hover:decoration-zinc-900 dark:decoration-zinc-600 dark:hover:decoration-zinc-100"
          >
            source repository
          </a>
          .
        </p>
      </section>

      <section className="flex flex-col gap-4" aria-labelledby="certifications">
        <SectionHeading>
          <span id="certifications">Certifications</span>
        </SectionHeading>
        <ul className="flex flex-col gap-3">
          {CERTIFICATIONS.map((cert) => (
            <li key={cert.id}>
              {cert.available ? (
                <Link
                  href={`/quiz?certification=${encodeURIComponent(cert.id)}`}
                  className="group flex items-center justify-between gap-4 rounded-lg border border-zinc-200 bg-white p-5 transition-colors hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-600"
                >
                  <span className="flex flex-col gap-1">
                    <span className="font-medium">
                      <span className="text-zinc-500 dark:text-zinc-400">
                        {cert.provider}
                      </span>{" "}
                      {cert.name}
                    </span>
                    <span className="text-sm text-zinc-600 dark:text-zinc-400">
                      {cert.blurb}
                    </span>
                  </span>
                  <span
                    aria-hidden
                    className="text-zinc-400 transition-transform group-hover:translate-x-0.5"
                  >
                    →
                  </span>
                </Link>
              ) : (
                <div className="flex items-center justify-between gap-4 rounded-lg border border-dashed border-zinc-200 p-5 dark:border-zinc-800">
                  <span className="flex flex-col gap-1">
                    <span className="font-medium text-zinc-500 dark:text-zinc-500">
                      <span>{cert.provider}</span> {cert.name}
                    </span>
                    <span className="text-sm text-zinc-500 dark:text-zinc-500">
                      {cert.blurb}
                    </span>
                  </span>
                  <span className="shrink-0 rounded-full border border-zinc-200 px-2 py-0.5 text-xs text-zinc-500 dark:border-zinc-800">
                    Soon
                  </span>
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-4" aria-labelledby="faq">
        <SectionHeading>
          <span id="faq">Questions</span>
        </SectionHeading>
        <dl className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {FAQ.map(({ q, a }) => (
            <div key={q} className="flex flex-col gap-2 py-5 first:pt-0 last:pb-0">
              <dt className="font-medium">{q}</dt>
              <dd className="text-sm leading-6 text-zinc-600 dark:text-zinc-400">{a}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
