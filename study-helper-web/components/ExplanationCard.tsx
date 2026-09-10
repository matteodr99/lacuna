import type { WrongAnswerExplanation } from "@/lib/api";

function Section({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {title}
      </h3>
      <p className="text-sm leading-6 text-zinc-700 dark:text-zinc-300">{body}</p>
    </div>
  );
}

export default function ExplanationCard({
  explanation,
}: {
  explanation: WrongAnswerExplanation;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <Section title="Why your answer is wrong" body={explanation.why_wrong} />
      <Section title="Why the correct one is right" body={explanation.why_correct} />
      <div className="rounded-md bg-zinc-100 p-4 dark:bg-zinc-800/60">
        <Section title="Key takeaway" body={explanation.key_takeaway} />
      </div>
    </div>
  );
}
