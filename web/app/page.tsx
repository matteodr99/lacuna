import type { Metadata } from "next";
import Link from "next/link";
import SampleQuestion from "@/components/SampleQuestion";
import GapIllustration from "@/components/landing/GapIllustration";
import Pipeline from "@/components/landing/Pipeline";
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

function SectionHeading({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <h2
      id={id}
      className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400"
    >
      {children}
    </h2>
  );
}

/** One column for the landing: wider than the app pages, so the hero can
 * sit text-beside-graphic. Bands that need a full-width background wrap
 * this in their own <section>. */
function Column({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-5xl px-6 ${className}`}>{children}</div>;
}

const FACTS = [
  { value: "0", label: "model calls while you practise" },
  { value: "100%", label: "of served questions checked against the docs" },
  { value: "2", label: "reasons per answer, not a wall of text" },
];

export default function Home() {
  return (
    <div className="flex flex-col">
      <script
        type="application/ld+json"
        // Static, authored above — nothing user-supplied reaches it.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
      />

      {/* Hero */}
      <section>
        <Column className="grid items-center gap-10 py-16 sm:py-20 lg:grid-cols-12 lg:gap-12 lg:py-24">
          <div className="flex flex-col gap-6 lg:col-span-7">
            <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl lg:text-[3.25rem] lg:leading-[1.08]">
              The details you forget, not the concepts you know
            </h1>
            <p className="max-w-lg text-lg leading-8 text-zinc-600 dark:text-zinc-400">
              AWS Solutions Architect Associate practice for engineers who
              already run the stuff — thresholds, edge cases, rules that
              changed — every claim checked against the official docs.
            </p>
            <div className="flex flex-wrap items-center gap-4 pt-1">
              <Link
                href={QUIZ_HREF}
                className="rounded-md bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
              >
                Start practising →
              </Link>
              <a
                href="#try-one"
                className="text-sm text-zinc-600 underline-offset-4 hover:underline dark:text-zinc-400"
              >
                Try a question first
              </a>
            </div>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Free · No account · {PRIMARY.provider} {PRIMARY.name} (SAA-C03)
            </p>
          </div>
          <div className="lg:col-span-5">
            <GapIllustration className="mx-auto w-full max-w-sm lg:max-w-none" />
          </div>
        </Column>
      </section>

      {/* Facts strip */}
      <section className="border-y border-zinc-200 dark:border-zinc-800">
        <Column>
          <dl className="grid divide-y divide-zinc-200 sm:grid-cols-3 sm:divide-x sm:divide-y-0 dark:divide-zinc-800">
            {FACTS.map((fact) => (
              <div key={fact.label} className="flex items-baseline gap-3 py-5 sm:flex-col sm:gap-1 sm:px-6 sm:py-7 sm:first:pl-0 sm:last:pr-0">
                <dt className="order-2 text-sm text-zinc-600 dark:text-zinc-400">{fact.label}</dt>
                <dd className="order-1 text-3xl font-semibold tracking-tight tabular-nums">
                  {fact.value}
                </dd>
              </div>
            ))}
          </dl>
        </Column>
      </section>

      {/* Sample question */}
      <section aria-labelledby="try-one" className="scroll-mt-8">
        <Column className="py-16 sm:py-20">
          <div className="mx-auto flex max-w-3xl flex-col gap-8">
            <div className="flex flex-col gap-2">
              <SectionHeading id="try-one">Try one</SectionHeading>
              <p className="text-xl font-medium tracking-tight text-balance">
                A question from the bank, exactly as it is served.
              </p>
              <p className="text-zinc-600 dark:text-zinc-400">
                Easy to get wrong if you learned S3 before 2026 — one of the
                two rules it turns on changed that year.
              </p>
            </div>
            <SampleQuestion quizHref={QUIZ_HREF} />
          </div>
        </Column>
      </section>

      {/* How it works — full-width band */}
      <section
        id="how-it-works"
        className="scroll-mt-8 border-y border-zinc-200 bg-zinc-100/70 dark:border-zinc-800 dark:bg-zinc-900/50"
      >
        <Column className="flex flex-col gap-10 py-16 sm:py-20">
          <div className="flex flex-col gap-2">
            <SectionHeading>How it works</SectionHeading>
            <p className="max-w-2xl text-xl font-medium tracking-tight text-balance">
              A review step sits between the model and you. It exists because
              generation alone produced confident, wrong BGP values.
            </p>
          </div>
          <Pipeline />
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            The pipeline, the failures that shaped it and the review records
            are in the{" "}
            <a
              href="https://github.com/matteodr99/lacuna"
              className="underline decoration-zinc-300 underline-offset-4 hover:decoration-zinc-900 dark:decoration-zinc-600 dark:hover:decoration-zinc-100"
            >
              source repository
            </a>
            .
          </p>
        </Column>
      </section>

      {/* Certifications + FAQ, side by side on wide screens */}
      <section>
        <Column className="grid gap-16 py-16 sm:py-20 lg:grid-cols-12 lg:gap-12">
          <div className="flex flex-col gap-5 lg:col-span-5" aria-labelledby="certifications">
            <SectionHeading id="certifications">Certifications</SectionHeading>
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
                          <span className="text-zinc-500 dark:text-zinc-400">{cert.provider}</span>{" "}
                          {cert.name}
                        </span>
                        <span className="text-sm text-zinc-600 dark:text-zinc-400">{cert.blurb}</span>
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
                        <span className="text-sm text-zinc-500 dark:text-zinc-500">{cert.blurb}</span>
                      </span>
                      <span className="shrink-0 rounded-full border border-zinc-200 px-2 py-0.5 text-xs text-zinc-500 dark:border-zinc-800">
                        Soon
                      </span>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-col gap-5 lg:col-span-7" aria-labelledby="faq">
            <SectionHeading id="faq">Questions</SectionHeading>
            <div className="divide-y divide-zinc-200 border-y border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
              {FAQ.map(({ q, a }) => (
                <details key={q} className="group py-4">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium [&::-webkit-details-marker]:hidden">
                    {q}
                    <span
                      aria-hidden
                      className="shrink-0 text-zinc-400 transition-transform group-open:rotate-45"
                    >
                      +
                    </span>
                  </summary>
                  <p className="pt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-400">{a}</p>
                </details>
              ))}
            </div>
          </div>
        </Column>
      </section>
    </div>
  );
}
