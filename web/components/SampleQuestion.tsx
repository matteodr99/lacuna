"use client";

import { useState } from "react";
import Link from "next/link";
import QuestionCard from "@/components/QuestionCard";
import ExplanationCard from "@/components/ExplanationCard";
import {
  SAMPLE_CORRECT_INDEX,
  SAMPLE_OPTION_EXPLANATIONS,
  SAMPLE_QUESTION,
  SAMPLE_SOURCES,
} from "@/lib/sample-question";

/**
 * The landing page's one interactive element: a real, reviewed question
 * answered in place. Picking an option reveals the same two explanations
 * the quiz shows, plus the documentation pages the review checked — the
 * thing the copy above it claims, demonstrated rather than asserted.
 *
 * No API call and no guest user: the answer is in the page, which is fine
 * for a single published sample and is what keeps this instant on a
 * free-tier backend that sleeps.
 */
export default function SampleQuestion({ quizHref }: { quizHref: string }) {
  const [selected, setSelected] = useState<number | null>(null);
  const revealed = selected !== null;
  const isCorrect = selected === SAMPLE_CORRECT_INDEX;

  return (
    <div className="flex flex-col gap-5">
      <QuestionCard
        question={SAMPLE_QUESTION}
        selectedIndex={selected}
        correctIndex={revealed ? SAMPLE_CORRECT_INDEX : null}
        disabled={revealed}
        onSelect={setSelected}
      />

      {revealed ? (
        <div className="flex flex-col gap-4">
          <p
            className={`font-medium ${
              isCorrect
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-red-700 dark:text-red-400"
            }`}
            aria-live="polite"
          >
            {isCorrect ? "Correct." : "Not quite."}
          </p>
          <ExplanationCard
            selectedIndex={selected}
            result={{
              is_correct: isCorrect,
              correct_index: SAMPLE_CORRECT_INDEX,
              explanation: SAMPLE_OPTION_EXPLANATIONS[SAMPLE_CORRECT_INDEX],
              selected_option_explanation: SAMPLE_OPTION_EXPLANATIONS[selected],
              correct_option_explanation: SAMPLE_OPTION_EXPLANATIONS[SAMPLE_CORRECT_INDEX],
            }}
          />
          <div className="flex flex-col gap-2 rounded-lg border border-dashed border-zinc-300 p-5 dark:border-zinc-700">
            <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Checked against
            </h3>
            <ul className="flex flex-col gap-1 text-sm">
              {SAMPLE_SOURCES.map((source) => (
                <li key={source.url}>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-zinc-700 underline decoration-zinc-300 underline-offset-4 hover:decoration-zinc-900 dark:text-zinc-300 dark:decoration-zinc-600 dark:hover:decoration-zinc-100"
                  >
                    {source.title}
                  </a>
                </li>
              ))}
            </ul>
            <p className="mt-1 text-xs leading-5 text-zinc-500 dark:text-zinc-400">
              Every served question carries the pages its claims were verified
              on. Reviewed 11 September 2026.
            </p>
          </div>
          <div>
            <Link
              href={quizHref}
              className="inline-block rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
            >
              Keep going →
            </Link>
          </div>
        </div>
      ) : (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Pick an answer to see the explanation and the documentation it was
          checked against.
        </p>
      )}
    </div>
  );
}
