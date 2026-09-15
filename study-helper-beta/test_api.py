"""
Tests for api.py using mocked Gemini calls — verifies routing, DB
persistence, and response shapes without a real API key or slow/costly
LLM calls. Prompt accuracy itself was already validated separately in
AI Studio; these tests are about the plumbing, not the AI content.

Run: pytest test_api.py -v
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import api
from db_schema import (
    Difficulty,
    OptionExplanation,
    Question as DBQuestion,
    QuestionReport,
    QuestionType,
    ReportReason,
    ReviewStatus,
)
from gemini_integration_example import (
    Question,
    StudyPlan,
    WeakSpot,
    WeakSpotAnalysis,
    WeeklyPlan,
)


@pytest.fixture
def client():
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(test_engine)
    api.engine = test_engine

    def get_test_session():
        with Session(test_engine) as session:
            yield session

    api.app.dependency_overrides[api.get_session] = get_test_session
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


MOCK_QUESTION = Question(
    question="Which BGP community sets High Local Preference on a Transit VIF?",
    options=["7224:7300", "7224:7100", "7224:9300", "7224:8200"],
    correct_index=0,
    explanation="7224:7300 sets High Local Preference for Private/Transit VIF routing.",
    domain="Hybrid Connectivity",
    concept_tags=["Transit Gateway route propagation", "BGP community tags"],
    question_type="detail_recall",
    difficulty="hard",
)

MOCK_WEAK_SPOTS = WeakSpotAnalysis(
    priority_concepts=[
        WeakSpot(
            concept="Transit Gateway route propagation",
            reason="Missed twice in a row",
            confidence="high",
            type="true_gap",
            gap_level="detail_recall",
        )
    ],
    overall_readiness_note="Solid on fundamentals, needs targeted review on BGP community families.",
)

MOCK_STUDY_PLAN = StudyPlan(
    feasible=True,
    warning=None,
    weekly_plan=[
        WeeklyPlan(
            week=1,
            focus_concepts=["Transit Gateway route propagation"],
            daily_minutes=60,
            activity_mix="45m review, 15m practice",
        )
    ],
)


def _seed_question(client, review_status=ReviewStatus.approved):
    """Insert a question straight into the bank. Users no longer trigger
    generation — seed_questions.py does that offline — so tests seed the
    bank directly instead of mocking a generate endpoint."""
    with Session(api.engine) as session:
        q = DBQuestion(
            certification="AWS ANS-C01",
            domain="Hybrid Connectivity",
            question_text=MOCK_QUESTION.question,
            options=MOCK_QUESTION.options,
            correct_index=MOCK_QUESTION.correct_index,
            explanation=MOCK_QUESTION.explanation,
            concept_tags=MOCK_QUESTION.concept_tags,
            question_type=QuestionType.detail_recall,
            difficulty=Difficulty.hard,
            review_status=review_status,
        )
        session.add(q)
        session.commit()
        session.refresh(q)
        return {"id": q.id}


def test_create_user(client):
    r = client.post("/users", json={"email": "test@example.com", "target_certification": "AWS ANS-C01", "exam_date": "2026-11-15"})
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com"


def test_next_question_hides_answer(client):
    user = client.post("/users", json={"email": "n@example.com"}).json()
    _seed_question(client)
    r = client.get("/questions/next", params={"user_id": user["id"], "certification": "AWS ANS-C01"})
    assert r.status_code == 200
    body = r.json()
    assert "correct_index" not in body
    assert "explanation" not in body
    assert body["question"] == MOCK_QUESTION.question


def test_unapproved_questions_are_never_served(client):
    """The whole point of the review gate: pending/rejected questions must
    not reach a user, no matter that they exist in the bank."""
    user = client.post("/users", json={"email": "gate@example.com"}).json()
    _seed_question(client, review_status=ReviewStatus.pending)
    _seed_question(client, review_status=ReviewStatus.rejected)
    r = client.get("/questions/next", params={"user_id": user["id"], "certification": "AWS ANS-C01"})
    assert r.status_code == 404


def test_taking_a_test_makes_no_gemini_call(client, monkeypatch):
    """Serving a question and grading an answer must not hit the model at
    all — that's the entire point of the bank. The explanation used to be a
    live call on wrong answers; now it's the reviewed text stored with the
    question. Blow up loudly if anything reaches the Gemini client."""
    import gemini_integration_example as gie

    def explode(*a, **kw):
        raise AssertionError("Gemini was called while taking a test")
    monkeypatch.setattr(gie, "get_client", explode)

    user = client.post("/users", json={"email": "free@example.com"}).json()
    question = _seed_question(client)
    r = client.get("/questions/next", params={"user_id": user["id"], "certification": "AWS ANS-C01"})
    assert r.status_code == 200
    r = client.post("/attempts", json={"user_id": user["id"], "question_id": question["id"], "selected_index": 2})
    assert r.status_code == 200


def test_wrong_attempt_returns_the_reviewed_explanation(client):
    """The explanation is the text stored with the question — the one that
    passed review with it — not a fresh model output."""
    user = client.post("/users", json={"email": "a@example.com"}).json()
    question = _seed_question(client)

    r = client.post("/attempts", json={"user_id": user["id"], "question_id": question["id"], "selected_index": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["is_correct"] is False
    assert body["correct_index"] == 0
    assert body["explanation"] == MOCK_QUESTION.explanation
    assert "explanation_error" not in body


def _seed_option_explanations(question_id):
    texts = ["7224:7300 is the documented Local Preference community for Private/Transit VIFs.",
             "7224:7100 sets Low Local Preference, the opposite of what is asked.",
             "7224:9300 is a Public VIF scope community; it has no Local Preference meaning on a Transit VIF.",
             "7224:8200 is an AWS-to-customer community for Public VIF outbound routing."]
    with Session(api.engine) as session:
        for i, t in enumerate(texts):
            session.add(OptionExplanation(question_id=question_id, option_index=i, text=t))
        session.commit()
    return texts


def test_wrong_attempt_returns_only_the_picked_and_correct_reasons(client):
    """The candidate who picked C should read why C is wrong and why A is
    right — not the paragraphs about B and D."""
    user = client.post("/users", json={"email": "c@example.com"}).json()
    question = _seed_question(client)
    texts = _seed_option_explanations(question["id"])

    r = client.post("/attempts", json={"user_id": user["id"], "question_id": question["id"], "selected_index": 2})
    body = r.json()
    assert body["selected_option_explanation"] == texts[2]
    assert body["correct_option_explanation"] == texts[0]
    assert body["explanation"] == MOCK_QUESTION.explanation   # full text still there as fallback


def test_attempt_without_per_option_rows_falls_back_to_full_explanation(client):
    """Older content has no per-option breakdown; the fields are None and
    the client shows the full explanation instead."""
    user = client.post("/users", json={"email": "d@example.com"}).json()
    question = _seed_question(client)

    r = client.post("/attempts", json={"user_id": user["id"], "question_id": question["id"], "selected_index": 1})
    body = r.json()
    assert body["selected_option_explanation"] is None
    assert body["correct_option_explanation"] is None
    assert body["explanation"] == MOCK_QUESTION.explanation


def test_correct_attempt_also_returns_the_explanation(client):
    """Stored text costs nothing to return, and the reasoning about the
    distractors is worth reading even when the pick was right."""
    user = client.post("/users", json={"email": "b@example.com"}).json()
    question = _seed_question(client)

    r = client.post("/attempts", json={"user_id": user["id"], "question_id": question["id"], "selected_index": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["is_correct"] is True
    assert body["explanation"] == MOCK_QUESTION.explanation


@patch("api.analyze_weak_spots", return_value=MOCK_WEAK_SPOTS)
def test_weak_spots_uses_real_question_type(mock_weak, client):
    """The whole point of the DB layer: verify the history passed to
    analyze_weak_spots carries real question_type from the DB, not a guess."""
    user = client.post("/users", json={"email": "c@example.com", "target_certification": "AWS ANS-C01"}).json()
    question = _seed_question(client)
    client.post("/attempts", json={"user_id": user["id"], "question_id": question["id"], "selected_index": 2})

    r = client.get(f"/users/{user['id']}/weak-spots")
    assert r.status_code == 200

    passed_history = mock_weak.call_args.kwargs["answer_history"]
    assert all("question_type" in entry for entry in passed_history)
    assert passed_history[0]["question_type"] == "detail_recall"


@patch("api.analyze_weak_spots", return_value=MOCK_WEAK_SPOTS)
def test_weak_spots_is_computed_once_per_history(mock_weak, client):
    """The analysis is the only live model call in the user flow and a pure
    function of the history. Revisiting the page must not spend another
    request; a new answer must."""
    user = client.post("/users", json={"email": "cache@example.com"}).json()
    q1 = _seed_question(client)
    client.post("/attempts", json={"user_id": user["id"], "question_id": q1["id"], "selected_index": 2})

    first = client.get(f"/users/{user['id']}/weak-spots").json()
    second = client.get(f"/users/{user['id']}/weak-spots").json()
    assert first == second
    assert mock_weak.call_count == 1, "same history was analysed twice"

    with Session(api.engine) as session:
        q2 = DBQuestion(certification="AWS ANS-C01", domain="Hybrid Connectivity", question_text="another",
                        options=["a", "b", "c", "d"], correct_index=0, explanation="e", concept_tags=["x"],
                        question_type=QuestionType.conceptual, difficulty=Difficulty.medium,
                        review_status=ReviewStatus.approved)
        session.add(q2); session.commit(); session.refresh(q2)
    client.post("/attempts", json={"user_id": user["id"], "question_id": q2.id, "selected_index": 1})

    client.get(f"/users/{user['id']}/weak-spots")
    assert mock_weak.call_count == 2, "new history was served from the stale snapshot"


def test_weak_spots_without_history_returns_400(client):
    user = client.post("/users", json={"email": "d@example.com"}).json()
    r = client.get(f"/users/{user['id']}/weak-spots")
    assert r.status_code == 400


@patch("api.generate_study_plan", return_value=MOCK_STUDY_PLAN)
@patch("api.analyze_weak_spots", return_value=MOCK_WEAK_SPOTS)
def test_study_plan_end_to_end(mock_weak, mock_plan, client):
    user = client.post(
        "/users",
        json={"email": "e@example.com", "target_certification": "AWS ANS-C01", "exam_date": "2026-11-15"},
    ).json()
    question = _seed_question(client)
    client.post("/attempts", json={"user_id": user["id"], "question_id": question["id"], "selected_index": 2})

    r = client.post(f"/users/{user['id']}/study-plan", json={"daily_minutes": 75})
    assert r.status_code == 200
    assert r.json()["feasible"] is True

# ---------------------------------------------------------------------
# Reporting a question
# ---------------------------------------------------------------------

def test_report_question_records_the_report(client):
    user = client.post("/users", json={"email": "reporter@example.com"}).json()
    question = _seed_question(client)

    r = client.post(
        f"/questions/{question['id']}/report",
        json={"reason": "wrong_answer", "detail": "7224:7300 is inbound, not outbound.",
              "user_id": user["id"]},
    )
    assert r.status_code == 201
    assert r.json()["already_reported"] is False

    with Session(api.engine) as session:
        reports = session.exec(select(QuestionReport)).all()
    assert len(reports) == 1
    assert reports[0].reason == ReportReason.wrong_answer
    assert reports[0].resolved is False


def test_report_does_not_unpublish_the_question(client):
    """A report is a signal for the reviewer, not a takedown. Anything else
    would let one user pull a question from everyone else's bank."""
    user = client.post("/users", json={"email": "r2@example.com"}).json()
    question = _seed_question(client)

    client.post(f"/questions/{question['id']}/report",
                json={"reason": "outdated", "user_id": user["id"]})

    r = client.get("/questions/next", params={"user_id": user["id"], "certification": "AWS ANS-C01"})
    assert r.status_code == 200
    assert r.json()["id"] == question["id"]


def test_second_report_from_same_user_is_idempotent(client):
    """A double click or a reload must not inflate the count the review
    queue sorts on."""
    user = client.post("/users", json={"email": "r3@example.com"}).json()
    question = _seed_question(client)
    payload = {"reason": "ambiguous", "user_id": user["id"]}

    first = client.post(f"/questions/{question['id']}/report", json=payload)
    second = client.post(f"/questions/{question['id']}/report", json=payload)

    assert first.json()["already_reported"] is False
    assert second.json()["already_reported"] is True
    assert second.json()["id"] == first.json()["id"]

    with Session(api.engine) as session:
        assert len(session.exec(select(QuestionReport)).all()) == 1


def test_report_survives_an_unknown_user(client):
    """Guest ids live in localStorage and go stale. Losing the report would
    cost more than losing the attribution."""
    question = _seed_question(client)

    r = client.post(f"/questions/{question['id']}/report",
                    json={"reason": "typo", "user_id": 9999})
    assert r.status_code == 201

    with Session(api.engine) as session:
        report = session.exec(select(QuestionReport)).one()
    assert report.user_id is None


def test_report_on_missing_question_is_404(client):
    r = client.post("/questions/9999/report", json={"reason": "other"})
    assert r.status_code == 404
