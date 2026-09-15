import Link from "next/link";
import { CERTIFICATIONS } from "@/lib/certifications";

export default function Home() {
  return (
    <div className="flex flex-col gap-12">
      <section className="flex flex-col gap-4">
        <h1 className="text-3xl font-semibold tracking-tight text-balance">
          The details you forget, not the concepts you know
        </h1>
        <p className="max-w-xl text-zinc-600 dark:text-zinc-400">
          Practice questions for cloud certifications, aimed at experienced
          engineers: route propagation rules, thresholds, edge cases — the
          granular layer on top of concepts you already understand.
        </p>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Choose a certification
        </h2>
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

      {/* The review gate is the product's actual differentiator against
          "ask an LLM for practice questions", so it's stated up front
          rather than buried in a README. */}
      <section className="rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="font-medium">Why the questions are trustworthy</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-400">
          Questions are generated offline, with search grounding for any
          specific value or threshold, and then{" "}
          <strong className="font-medium text-zinc-900 dark:text-zinc-100">
            every specific claim is checked against the official documentation
            before the question can be served
          </strong>
          . Taking a test makes zero model calls. Generation alone was not
          enough — during development it produced confident, wrong BGP
          community values — so review is a structural step, not a formality.
          If something still slips through, you can report it from the
          question itself, and a person reads every report.
        </p>
      </section>
    </div>
  );
}
