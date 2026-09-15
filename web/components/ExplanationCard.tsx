import Markdown from "@/components/Markdown";
import type { AttemptResult } from "@/lib/api";

function Section({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {title}
      </h3>
      <div className="text-sm leading-6 text-zinc-700 dark:text-zinc-300">
        <Markdown>{body}</Markdown>
      </div>
    </div>
  );
}

/**
 * What the candidate reads after answering.
 *
 * With a per-option breakdown, it shows exactly two things: why the option
 * they picked is wrong, and why the correct one is right. Someone who chose
 * D shouldn't have to find the paragraph about D in a wall that also covers
 * B and C. Without a breakdown (older content), it falls back to the full
 * reviewed explanation.
 *
 * Everything here was stored and reviewed with the question — nothing is
 * generated at test time.
 */
export default function ExplanationCard({
  result,
  selectedIndex,
}: {
  result: AttemptResult;
  selectedIndex: number;
}) {
  const letter = (index: number) => String.fromCharCode(65 + index);
  const picked = result.selected_option_explanation;
  const correct = result.correct_option_explanation;
  const hasBreakdown = correct !== null && (result.is_correct || picked !== null);

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      {hasBreakdown ? (
        <>
          {!result.is_correct && picked && (
            <Section title={`Why ${letter(selectedIndex)} is wrong`} body={picked} />
          )}
          <Section title={`Why ${letter(result.correct_index)} is right`} body={correct} />
        </>
      ) : (
        <Section title="Explanation" body={result.explanation} />
      )}
    </div>
  );
}
