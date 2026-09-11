import Markdown from "@/components/Markdown";

/**
 * The explanation that was stored and reviewed with the question. It used
 * to be generated live by the model after a wrong answer — the one piece
 * of model text that reached users without passing review, and the one
 * thing at test time that could fail on quota. Now it's the same text the
 * reviewer read, rendered as Markdown because that's how it's written.
 */
export default function ExplanationCard({ explanation }: { explanation: string }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Explanation
      </h3>
      <div className="text-sm leading-6 text-zinc-700 dark:text-zinc-300">
        <Markdown>{explanation}</Markdown>
      </div>
    </div>
  );
}
