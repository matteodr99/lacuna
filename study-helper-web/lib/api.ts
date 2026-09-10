/**
 * Typed client for the FastAPI backend (study-helper-beta/api.py).
 *
 * The shapes here mirror the Pydantic models on the server. Note that
 * QuestionPublic deliberately has no correct_index / explanation: the
 * answer only comes back from POST /attempts, so nothing in this app can
 * leak it into the DOM.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type QuestionType = "conceptual" | "detail_recall";
export type Difficulty = "easy" | "medium" | "hard";

export type User = {
  id: number;
  email: string;
  target_certification: string | null;
  exam_date: string | null;
  created_at: string;
};

export type Question = {
  id: number;
  question: string;
  options: string[];
  domain: string;
  concept_tags: string[];
  question_type: QuestionType;
  difficulty: Difficulty;
};

export type WrongAnswerExplanation = {
  why_wrong: string;
  why_correct: string;
  key_takeaway: string;
};

export type AttemptResult = {
  is_correct: boolean;
  correct_index: number;
  explanation: WrongAnswerExplanation | null;
  /** Set when the answer was wrong but the explanation call failed —
   *  typically the Gemini free-tier quota. The answer still counted. */
  explanation_error: string | null;
};

export type WeakSpot = {
  concept: string;
  reason: string;
  confidence: "high" | "medium" | "low";
  type: "true_gap" | "forgetting_risk" | "isolated_mistake";
  gap_level: "conceptual" | "detail_recall";
};

export type WeakSpotAnalysis = {
  priority_concepts: WeakSpot[];
  overall_readiness_note: string;
};

/** Thrown for any non-2xx response, carrying the FastAPI `detail` string.
 * Status is kept because 404 on /questions/next means "bank exhausted",
 * which the quiz UI treats as a normal end state rather than an error. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, `Can't reach the API at ${BASE_URL}. Is uvicorn running?`);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body; statusText is the best we have
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export function createUser(body: {
  email: string;
  target_certification?: string;
  exam_date?: string;
}): Promise<User> {
  return request<User>("/users", { method: "POST", body: JSON.stringify(body) });
}

export function fetchNextQuestion(userId: number, certification: string): Promise<Question> {
  const query = new URLSearchParams({
    user_id: String(userId),
    certification,
  });
  return request<Question>(`/questions/next?${query}`);
}

export function submitAttempt(body: {
  user_id: number;
  question_id: number;
  selected_index: number;
}): Promise<AttemptResult> {
  return request<AttemptResult>("/attempts", { method: "POST", body: JSON.stringify(body) });
}

export type ReportReason = "wrong_answer" | "outdated" | "ambiguous" | "typo" | "other";

export type ReportResult = {
  id: number;
  /** True when this user had already flagged this question — the report
   *  wasn't duplicated. Worth telling them so, rather than silently
   *  pretending a second submission landed. */
  already_reported: boolean;
};

export function reportQuestion(body: {
  question_id: number;
  reason: ReportReason;
  detail?: string;
  user_id?: number;
}): Promise<ReportResult> {
  const { question_id, ...rest } = body;
  return request<ReportResult>(`/questions/${question_id}/report`, {
    method: "POST",
    body: JSON.stringify(rest),
  });
}

export function fetchWeakSpots(userId: number): Promise<WeakSpotAnalysis> {
  return request<WeakSpotAnalysis>(`/users/${userId}/weak-spots`);
}
