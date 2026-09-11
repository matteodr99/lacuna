"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import QuestionCard from "@/components/QuestionCard";
import ExplanationCard from "@/components/ExplanationCard";
import ReportQuestion from "@/components/ReportQuestion";
import {
  ApiError,
  fetchNextQuestion,
  submitAttempt,
  type AttemptResult,
  type Question,
} from "@/lib/api";
import { getOrCreateUserId } from "@/lib/session";

type Phase =
  | { status: "loading" }
  | { status: "answering" }
  | { status: "submitting" }
  | { status: "feedback"; result: AttemptResult }
  /** 404 from /questions/next: every approved question has been answered.
   *  A normal end state, not an error. */
  | { status: "exhausted" }
  | { status: "error"; message: string };

export default function QuizClient({
  certification,
  label,
}: {
  certification: string;
  label: string;
}) {
  const [phase, setPhase] = useState<Phase>({ status: "loading" });
  const [question, setQuestion] = useState<Question | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [score, setScore] = useState({ correct: 0, answered: 0 });
  // The ref is what the fetch effect reads, so a new round reuses the guest
  // user instead of creating another one; the state copy is what render
  // reads, since a ref's value isn't allowed to drive output.
  const userIdRef = useRef<number | null>(null);
  const [userId, setUserId] = useState<number | null>(null);
  // Advancing is modelled as a counter the fetch effect depends on, rather
  // than an async function called from the effect and from a click: that
  // keeps every setState after an await, so no cascading render.
  const [round, setRound] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resolvedUserId =
          userIdRef.current ?? (await getOrCreateUserId(certification));
        userIdRef.current = resolvedUserId;
        const next = await fetchNextQuestion(resolvedUserId, certification);
        if (cancelled) return;
        setUserId(resolvedUserId);
        setQuestion(next);
        setSelected(null);
        setPhase({ status: "answering" });
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 404) {
          setPhase({ status: "exhausted" });
          return;
        }
        setPhase({
          status: "error",
          message: error instanceof Error ? error.message : "Something went wrong",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [certification, round]);

  function goToNextQuestion() {
    setPhase({ status: "loading" });
    setRound((r) => r + 1);
  }

  async function handleSubmit() {
    if (selected === null || question === null || userIdRef.current === null) return;
    setPhase({ status: "submitting" });
    try {
      const result = await submitAttempt({
        user_id: userIdRef.current,
        question_id: question.id,
        selected_index: selected,
      });
      setScore((s) => ({
        correct: s.correct + (result.is_correct ? 1 : 0),
        answered: s.answered + 1,
      }));
      setPhase({ status: "feedback", result });
    } catch (error) {
      setPhase({
        status: "error",
        message: error instanceof Error ? error.message : "Something went wrong",
      });
    }
  }

  const result = phase.status === "feedback" ? phase.result : null;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between gap-4 text-sm text-zinc-500 dark:text-zinc-400">
        <span>{label}</span>
        {score.answered > 0 && (
          <span aria-live="polite">
            {score.correct}/{score.answered} correct
          </span>
        )}
      </div>

      {phase.status === "loading" && (
        <p className="text-zinc-500 dark:text-zinc-400">Loading question…</p>
      )}

      {phase.status === "exhausted" && (
        <div className="flex flex-col items-start gap-4">
          <h1 className="text-2xl font-semibold tracking-tight">
            You&rsquo;ve answered every approved question
          </h1>
          <p className="max-w-xl text-zinc-600 dark:text-zinc-400">
            The bank only serves questions that have passed review against the
            official documentation, so it runs out rather than inventing more on
            the spot. More are added as they pass.
          </p>
          <div className="flex gap-3">
            <Link
              href="/weak-spots"
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
            >
              See your weak spots
            </Link>
            <Link
              href="/"
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium dark:border-zinc-700"
            >
              Home
            </Link>
          </div>
        </div>
      )}

      {phase.status === "error" && (
        <div className="flex flex-col items-start gap-4">
          <h1 className="text-2xl font-semibold tracking-tight">Something broke</h1>
          <p className="max-w-xl text-zinc-600 dark:text-zinc-400">{phase.message}</p>
          <button
            type="button"
            onClick={goToNextQuestion}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
          >
            Next question
          </button>
        </div>
      )}

      {question && (phase.status === "answering" || phase.status === "submitting" || phase.status === "feedback") && (
        <>
          <QuestionCard
            question={question}
            selectedIndex={selected}
            correctIndex={result ? result.correct_index : null}
            disabled={phase.status !== "answering"}
            onSelect={setSelected}
          />

          {result && (
            <div className="flex flex-col gap-4">
              <p
                className={`font-medium ${
                  result.is_correct
                    ? "text-emerald-700 dark:text-emerald-400"
                    : "text-red-700 dark:text-red-400"
                }`}
                aria-live="polite"
              >
                {result.is_correct ? "Correct." : "Not quite."}
              </p>
              <ExplanationCard explanation={result.explanation} />
              {/* Keyed on the question so the form resets when the next one
                  loads, instead of showing the previous question's thanks. */}
              <ReportQuestion
                key={question.id}
                questionId={question.id}
                userId={userId}
              />
            </div>
          )}

          <div className="flex items-center gap-3">
            {phase.status === "feedback" ? (
              <button
                type="button"
                onClick={goToNextQuestion}
                className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
              >
                Next question
              </button>
            ) : (
              <button
                type="button"
                disabled={selected === null || phase.status === "submitting"}
                onClick={() => void handleSubmit()}
                className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
              >
                {phase.status === "submitting" ? "Checking…" : "Submit answer"}
              </button>
            )}

          </div>
        </>
      )}
    </div>
  );
}
