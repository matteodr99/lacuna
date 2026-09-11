"""
FastAPI layer wiring the Gemini functions (gemini_integration_example.py)
to the database (db_schema.py).

Setup:
    pip install fastapi uvicorn --break-system-packages
    uvicorn api:app --reload

Design note: GET /questions/next returns QuestionPublic, which omits
correct_index and explanation. Both come back only once an attempt is
submitted — otherwise the frontend could just read the answer out of the
response. The explanation returned is the one stored with the question,
which passed review alongside it; no model is called at test time.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db_schema import (
    Attempt,
    OptionExplanation,
    Question,
    QuestionReport,
    ReportReason,
    ReviewStatus,
    StudyPlan as StudyPlanDB,
    User,
    create_db_and_tables,
    engine,
    get_answer_history_for_user,
    select_next_question,
)
from gemini_integration_example import (
    StudyPlan,
    WeakSpotAnalysis,
    analyze_weak_spots,
    generate_study_plan,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


logger = logging.getLogger(__name__)

app = FastAPI(title="Cert Prep API", lifespan=lifespan)

# The browser blocks cross-origin requests by default, so without this the
# Next.js dev server (localhost:3000) can't call this API (localhost:8000)
# at all. Keep this list explicit — never use ["*"] once real users and
# credentials are involved. Add the deployed frontend URL here at launch.
ALLOWED_ORIGINS = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    """Return unexpected errors as JSON *with* the CORS header.

    Unhandled exceptions are turned into a response by Starlette's
    ServerErrorMiddleware, which sits outside CORSMiddleware — so the
    default 500 carries no Access-Control-Allow-Origin and the browser
    reports an opaque network failure instead of the error. The frontend
    then blames an unreachable API for a server that in fact answered.
    Setting the header here is what makes the real status visible."""
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    headers = {}
    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error"}, headers=headers
    )


def get_session():
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------

class CreateUserRequest(BaseModel):
    email: str
    target_certification: Optional[str] = None
    exam_date: Optional[str] = None


@app.post("/users", response_model=User)
def create_user(body: CreateUserRequest, session: Session = Depends(get_session)):
    user = User(**body.model_dump())
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ---------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------

class QuestionPublic(BaseModel):
    id: int
    question: str
    options: list[str]
    domain: str
    concept_tags: list[str]
    question_type: str
    difficulty: str


@app.get("/questions/next", response_model=QuestionPublic)
def get_next_question(
    user_id: int,
    certification: str,
    session: Session = Depends(get_session),
):
    """Serve the next question from the approved bank. No Gemini call —
    questions are generated offline by seed_questions.py and reviewed
    before they get here, so this is instant and costs nothing.

    Adaptivity: if the user has answer history, their weak concepts steer
    the pick. That's the same personalisation the live-generation version
    gave, without the per-question API cost, latency, or the risk of an
    unreviewed hallucination reaching a paying user."""
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    history = get_answer_history_for_user(session, user_id)
    weak_concepts = [h["concept"] for h in history if not h["correct"]]

    question = select_next_question(
        session=session,
        user_id=user_id,
        certification=certification,
        weak_concepts=weak_concepts or None,
    )
    if question is None:
        raise HTTPException(
            status_code=404,
            detail="No approved questions available for this certification (bank exhausted or not seeded)",
        )
    return QuestionPublic(
        id=question.id,
        question=question.question_text,
        options=question.options,
        domain=question.domain,
        concept_tags=question.concept_tags,
        question_type=question.question_type,
        difficulty=question.difficulty,
    )


# ---------------------------------------------------------------------
# Attempts
# ---------------------------------------------------------------------

class SubmitAttemptRequest(BaseModel):
    user_id: int
    question_id: int
    selected_index: int


class AttemptResult(BaseModel):
    is_correct: bool
    correct_index: int
    # The full explanation stored and reviewed with the question. Kept as the
    # fallback for questions that have no per-option breakdown yet.
    explanation: str
    # Why the option the candidate picked is wrong (or right), and why the
    # correct one is right — so the UI can show just those two instead of
    # the whole text about every distractor. None when the question has no
    # per-option rows; the client then shows `explanation`.
    selected_option_explanation: Optional[str] = None
    correct_option_explanation: Optional[str] = None


@app.post("/attempts", response_model=AttemptResult)
def submit_attempt(body: SubmitAttemptRequest, session: Session = Depends(get_session)):
    question = session.get(Question, body.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    if session.get(User, body.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    attempt = Attempt(
        user_id=body.user_id,
        question_id=body.question_id,
        selected_index=body.selected_index,
    )
    session.add(attempt)
    session.commit()

    by_option = {
        row.option_index: row.text
        for row in session.exec(
            select(OptionExplanation).where(OptionExplanation.question_id == question.id)
        ).all()
    }
    return AttemptResult(
        is_correct=body.selected_index == question.correct_index,
        correct_index=question.correct_index,
        explanation=question.explanation,
        selected_option_explanation=by_option.get(body.selected_index),
        correct_option_explanation=by_option.get(question.correct_index),
    )


# ---------------------------------------------------------------------
# Reporting a question
#
# The accuracy notes call this a gap to close before real users arrive.
# Review catches what a reviewer noticed; a candidate revising a topic in
# depth notices things a reviewer didn't, and until now had no way to say
# so. A report doesn't unpublish anything on its own — it moves the
# question to the top of the review queue, where a human decides.
# ---------------------------------------------------------------------

class ReportQuestionRequest(BaseModel):
    reason: ReportReason
    detail: Optional[str] = Field(default=None, max_length=2000)
    user_id: Optional[int] = None


class ReportResult(BaseModel):
    id: int
    already_reported: bool


@app.post("/questions/{question_id}/report", response_model=ReportResult, status_code=201)
def report_question(
    question_id: int,
    body: ReportQuestionRequest,
    session: Session = Depends(get_session),
):
    if session.get(Question, question_id) is None:
        raise HTTPException(status_code=404, detail="Question not found")

    # An unknown user_id is dropped rather than rejected. Identity here is
    # a guest id from the browser's localStorage, so a stale one is normal,
    # and losing the report would cost more than losing the attribution.
    user_id = body.user_id
    if user_id is not None and session.get(User, user_id) is None:
        user_id = None

    if user_id is not None:
        existing = session.exec(
            select(QuestionReport).where(
                QuestionReport.question_id == question_id,
                QuestionReport.user_id == user_id,
                QuestionReport.resolved == False,  # noqa: E712 — SQL comparison, not a bool test
            )
        ).first()
        if existing is not None:
            # Idempotent: a second click, or a reload, must not inflate the
            # count that the review queue sorts on.
            return ReportResult(id=existing.id, already_reported=True)

    report = QuestionReport(
        question_id=question_id,
        user_id=user_id,
        reason=body.reason,
        detail=body.detail,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return ReportResult(id=report.id, already_reported=False)


# ---------------------------------------------------------------------
# Weak spots — this is where the DB layer's fix actually pays off:
# get_answer_history_for_user() supplies real question_type per entry.
# ---------------------------------------------------------------------

@app.get("/users/{user_id}/weak-spots", response_model=WeakSpotAnalysis)
def get_weak_spots(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    history = get_answer_history_for_user(session, user_id)
    if not history:
        raise HTTPException(status_code=400, detail="No answer history yet — answer some questions first")
    return analyze_weak_spots(certification=user.target_certification or "", answer_history=history)


# ---------------------------------------------------------------------
# Study plan
# ---------------------------------------------------------------------

class StudyPlanRequest(BaseModel):
    daily_minutes: int


@app.post("/users/{user_id}/study-plan", response_model=StudyPlan)
def create_study_plan(user_id: int, body: StudyPlanRequest, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.exam_date:
        raise HTTPException(status_code=400, detail="User has no exam_date set")

    history = get_answer_history_for_user(session, user_id)
    weak_spots = analyze_weak_spots(certification=user.target_certification or "", answer_history=history)
    priority = [c.concept for c in weak_spots.priority_concepts]
    solid = list({h["concept"] for h in history if h["concept"] not in priority})

    plan = generate_study_plan(
        exam_date=user.exam_date,
        daily_minutes=body.daily_minutes,
        priority_concepts=priority,
        solid_concepts=solid,
    )

    db_plan = StudyPlanDB(
        user_id=user_id,
        exam_date=user.exam_date,
        feasible=plan.feasible,
        warning=plan.warning,
        weekly_plan=[w.model_dump() for w in plan.weekly_plan],
    )
    session.add(db_plan)
    session.commit()
    return plan