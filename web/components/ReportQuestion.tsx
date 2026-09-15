"use client";

import { useState } from "react";
import { reportQuestion, type ReportReason } from "@/lib/api";

/**
 * Lets a candidate flag a question as wrong, stale or ambiguous.
 *
 * Deliberately shown only after answering: before that, the correct answer
 * is hidden, so a report could only be about wording — and a button
 * sitting next to an unanswered question mostly collects frustration.
 *
 * A report never pulls the question from the bank; it moves it to the top
 * of the reviewer's queue. The copy says so, because a user who thinks
 * they've deleted something behaves differently from one who knows they've
 * sent a note.
 */
const REASONS: { value: ReportReason; label: string }[] = [
  { value: "wrong_answer", label: "The marked answer is wrong" },
  { value: "outdated", label: "Out of date with current docs" },
  { value: "ambiguous", label: "Ambiguous or unclear" },
  { value: "typo", label: "Typo or formatting" },
  { value: "other", label: "Something else" },
];

type Phase =
  | { status: "idle" }
  | { status: "open" }
  | { status: "sending" }
  | { status: "sent"; alreadyReported: boolean }
  | { status: "error"; message: string };

export default function ReportQuestion({
  questionId,
  userId,
}: {
  questionId: number;
  userId: number | null;
}) {
  const [phase, setPhase] = useState<Phase>({ status: "idle" });
  const [reason, setReason] = useState<ReportReason>("wrong_answer");
  const [detail, setDetail] = useState("");

  async function submit() {
    setPhase({ status: "sending" });
    try {
      const result = await reportQuestion({
        question_id: questionId,
        reason,
        detail: detail.trim() || undefined,
        user_id: userId ?? undefined,
      });
      setPhase({ status: "sent", alreadyReported: result.already_reported });
    } catch (error) {
      setPhase({
        status: "error",
        message: error instanceof Error ? error.message : "Couldn't send the report",
      });
    }
  }

  if (phase.status === "sent") {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400" aria-live="polite">
        {phase.alreadyReported
          ? "You'd already flagged this one — it's in the review queue."
          : "Thanks — flagged for review. A human reads every report."}
      </p>
    );
  }

  if (phase.status === "idle") {
    return (
      <button
        type="button"
        onClick={() => setPhase({ status: "open" })}
        className="self-start text-sm text-zinc-500 underline underline-offset-4 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-100"
      >
        Something wrong with this question?
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">What&rsquo;s wrong?</span>
        <select
          value={reason}
          onChange={(event) => setReason(event.target.value as ReportReason)}
          className="rounded-md border border-zinc-300 bg-white p-2 dark:border-zinc-700 dark:bg-zinc-900"
        >
          {REASONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">
          Detail <span className="font-normal text-zinc-500">(optional)</span>
        </span>
        <textarea
          value={detail}
          onChange={(event) => setDetail(event.target.value)}
          rows={3}
          maxLength={2000}
          placeholder="If you have a source, this is the most useful thing you can add."
          className="rounded-md border border-zinc-300 bg-white p-2 dark:border-zinc-700 dark:bg-zinc-900"
        />
      </label>

      {phase.status === "error" && (
        <p className="text-sm text-red-700 dark:text-red-400">{phase.message}</p>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={phase.status === "sending"}
          onClick={() => void submit()}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {phase.status === "sending" ? "Sending…" : "Send report"}
        </button>
        <button
          type="button"
          onClick={() => setPhase({ status: "idle" })}
          className="text-sm text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          Cancel
        </button>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          This flags it for review — it stays in the bank until a human decides.
        </span>
      </div>
    </div>
  );
}
