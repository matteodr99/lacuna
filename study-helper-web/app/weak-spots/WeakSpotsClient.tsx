"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, fetchWeakSpots, type WeakSpot, type WeakSpotAnalysis } from "@/lib/api";
import { getOrCreateUserId } from "@/lib/session";

const TYPE_LABEL: Record<WeakSpot["type"], string> = {
  true_gap: "Real gap",
  forgetting_risk: "Forgetting risk",
  isolated_mistake: "Isolated slip",
};

const GAP_LABEL: Record<WeakSpot["gap_level"], string> = {
  conceptual: "Conceptual",
  detail_recall: "Detail recall",
};

type State =
  | { status: "loading" }
  | { status: "ready"; analysis: WeakSpotAnalysis }
  /** 400 from the API: the analysis needs answer history to work from. */
  | { status: "empty" }
  | { status: "error"; message: string };

export default function WeakSpotsClient() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const userId = await getOrCreateUserId();
        const analysis = await fetchWeakSpots(userId);
        if (!cancelled) setState({ status: "ready", analysis });
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 400) {
          setState({ status: "empty" });
          return;
        }
        setState({
          status: "error",
          message:
            // Unlike a wrong answer, this whole page depends on one live
            // model call, so there's nothing to degrade to — say what
            // failed instead of showing an empty dashboard.
            error instanceof ApiError && error.status >= 500
              ? "The analysis couldn't be generated — the model API is unavailable or out of quota (free tier: 5 requests/min, 20/day). Your history is safe; try again later."
              : error instanceof Error
                ? error.message
                : "Something went wrong",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Weak spots</h1>
        <p className="max-w-xl text-sm text-zinc-600 dark:text-zinc-400">
          Patterns across your answer history — repeated mistakes separated from
          one-off slips, and gaps in understanding separated from gaps in recall,
          because the two need different revision.
        </p>
      </div>

      {state.status === "loading" && (
        <p className="text-zinc-500 dark:text-zinc-400">Analysing your history…</p>
      )}

      {state.status === "empty" && (
        <div className="flex flex-col items-start gap-4">
          <p className="text-zinc-600 dark:text-zinc-400">
            Nothing to analyse yet — answer a few questions first.
          </p>
          <Link
            href="/"
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
          >
            Start practising
          </Link>
        </div>
      )}

      {state.status === "error" && (
        <p className="text-red-700 dark:text-red-400">{state.message}</p>
      )}

      {state.status === "ready" && (
        <>
          <ul className="flex flex-col gap-3">
            {state.analysis.priority_concepts.map((spot) => (
              <li
                key={spot.concept}
                className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-medium">{spot.concept}</h2>
                  <span className="rounded-full border border-zinc-200 px-2 py-0.5 text-xs text-zinc-600 dark:border-zinc-800 dark:text-zinc-400">
                    {TYPE_LABEL[spot.type]}
                  </span>
                  <span className="rounded-full border border-zinc-200 px-2 py-0.5 text-xs text-zinc-600 dark:border-zinc-800 dark:text-zinc-400">
                    {GAP_LABEL[spot.gap_level]}
                  </span>
                  <span className="text-xs text-zinc-500 dark:text-zinc-500">
                    {spot.confidence} confidence
                  </span>
                </div>
                <p className="text-sm leading-6 text-zinc-700 dark:text-zinc-300">
                  {spot.reason}
                </p>
              </li>
            ))}
          </ul>

          <p className="rounded-lg bg-zinc-100 p-5 text-sm leading-6 text-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-300">
            {state.analysis.overall_readiness_note}
          </p>
        </>
      )}
    </div>
  );
}
