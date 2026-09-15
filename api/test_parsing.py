"""
Tests for the local repair of model output shape drift.

Every payload here is a reconstruction of a shape the model actually
returned during a seeding run. They matter because the fallback for a
shape the code can't handle is a second API call out of a 20/day budget —
and in the run that produced these, that second call came back in the
same wrong shape, so the question was lost and the quota spent twice.

Run: .venv/bin/python -m pytest test_parsing.py -v
"""

import pytest
from pydantic import ValidationError

from gemini_integration_example import Question, _normalise


def _validate(payload) -> Question:
    return Question.model_validate(_normalise(payload))


def test_labelled_options_become_strings():
    """`options: [{"label": "A", "text": "..."}]` — the label is redundant
    with the position, so only the text is kept."""
    question = _validate({
        "question": "Which service stores rotating database credentials?",
        "options": [
            {"label": "A", "text": "AWS Secrets Manager"},
            {"label": "B", "text": "AWS Systems Manager Parameter Store"},
            {"label": "C", "text": "AWS Key Management Service (KMS)"},
            {"label": "D", "text": "S3 server-side encryption"},
        ],
        "correct_index": 0,
        "explanation": "Secrets Manager rotates credentials natively.",
        "domain": "Design Secure Architectures",
        "concept_tags": ["Secrets Manager"],
        "question_type": "conceptual",
        "difficulty": "medium",
    })
    assert question.options[0] == "AWS Secrets Manager"
    assert question.options[3] == "S3 server-side encryption"


def test_answer_letter_becomes_index():
    """`finalAnswer: "B"` where the schema wants `correct_index: 1`."""
    question = _validate({
        "problemStatement": "Which storage class suits 90-day audit access?",
        "options": [
            {"id": "A", "text": "S3 Standard"},
            {"id": "B", "text": "S3 Standard-IA"},
            {"id": "C", "text": "S3 Glacier Deep Archive"},
            {"id": "D", "text": "S3 One Zone-IA"},
        ],
        "finalAnswer": "B",
        "explanation": "Standard-IA keeps millisecond retrieval.",
        "domain": "Design Cost-Optimized Architectures",
        "concept_tags": ["S3 storage classes"],
        "question_type": "detail_recall",
        "difficulty": "medium",
    })
    assert question.correct_index == 1
    assert question.question.startswith("Which storage class")


def test_metadata_wrapper_is_lifted():
    """The classification fields arrived nested under a wrapper object
    instead of at the top level."""
    question = _validate({
        "question": "A company uses SQS and messages are processed twice.",
        "options": ["Set maxReceiveCount", "Raise visibility timeout",
                    "Publish to CloudWatch", "Cap messages in flight"],
        "correct_index": 1,
        "explanation": "Visibility timeout must exceed processing time.",
        "metadata": {
            "domain": "Design Resilient Architectures",
            "concept_tags": ["SQS", "visibility timeout"],
            "question_type": "conceptual",
            "difficulty": "medium",
        },
    })
    assert question.domain == "Design Resilient Architectures"
    assert question.difficulty == "medium"
    assert question.concept_tags == ["SQS", "visibility timeout"]


def test_nested_explanation_is_flattened_without_losing_text():
    """`explanation` came back as an object of per-option rationales. The
    words are the model's; only the nesting is dropped."""
    question = _validate({
        "question": "Why does an explicit deny win?",
        "options": ["Denied", "Allowed", "Depends on order", "Depends on SCP"],
        "correct_index": 0,
        "explanation": {
            "correct_option_explanation": "An explicit deny always wins.",
            "distractor_explanations": ["Order does not matter."],
        },
        "domain": "Design Secure Architectures",
        "concept_tags": ["IAM policy evaluation"],
        "question_type": "conceptual",
        "difficulty": "medium",
    })
    assert "An explicit deny always wins." in question.explanation
    assert "Order does not matter." in question.explanation


def test_per_option_correct_flag_becomes_index():
    question = _validate({
        "question": "Which check does an ASG use with an ELB attached?",
        "options": [
            {"text": "EC2 status checks only", "is_correct": False},
            {"text": "ELB health checks once enabled", "is_correct": True},
            {"text": "CloudWatch alarms", "is_correct": False},
            {"text": "Route 53 health checks", "is_correct": False},
        ],
        "explanation": "ELB health checks apply once the ASG is told to use them.",
        "domain": "Design Resilient Architectures",
        "concept_tags": ["Auto Scaling"],
        "question_type": "conceptual",
        "difficulty": "medium",
    })
    assert question.correct_index == 1


def test_title_cased_enums_still_normalise():
    """Regression: the original two fixes must survive the new ones."""
    question = _validate({
        "question": {"text": "Which EBS volume type suits high IOPS?"},
        "options": ["gp2", "io2", "st1", "sc1"],
        "correct_index": 1,
        "explanation": "io2 is provisioned IOPS.",
        "domain": "Design High-Performing Architectures",
        "concept_tags": ["EBS"],
        "question_type": "Conceptual",
        "difficulty": "Medium",
    })
    assert question.question_type == "conceptual"
    assert question.difficulty == "medium"
    assert question.question.startswith("Which EBS")


def test_missing_content_is_not_invented():
    """The point of the review gate: a payload with no domain or concept
    tags must fail, not acquire plausible-looking ones."""
    with pytest.raises(ValidationError) as caught:
        _validate({
            "problemStatement": "Which service rotates credentials?",
            "options": [{"label": "A", "text": "Secrets Manager"},
                        {"label": "B", "text": "Parameter Store"}],
            "finalAnswer": "A",
        })
    missing = {error["loc"][0] for error in caught.value.errors()}
    assert {"domain", "concept_tags", "explanation"} <= missing


# ---------------------------------------------------------------------
# The quota assertion: a malformed shape must cost one request, not two.
# ---------------------------------------------------------------------

MALFORMED_RESPONSE = """```json
{
  "problemStatement": "An application needs database credentials rotated automatically.",
  "options": [
    {"label": "A", "text": "AWS Secrets Manager"},
    {"label": "B", "text": "AWS Systems Manager Parameter Store"},
    {"label": "C", "text": "AWS Key Management Service (KMS)"},
    {"label": "D", "text": "S3 server-side encryption"}
  ],
  "finalAnswer": "A",
  "explanation": {
    "correct_option_explanation": "Secrets Manager rotates credentials natively.",
    "distractor_explanations": ["Parameter Store stores values but does not rotate them."]
  },
  "metadata": {
    "domain": "Design Secure Architectures",
    "concept_tags": ["Secrets Manager", "credential rotation"],
    "question_type": "Conceptual",
    "difficulty": "Medium"
  }
}
```"""


class _FakeInteraction:
    status = "completed"
    errors = None

    def __init__(self, output_text):
        self.output_text = output_text


class _FakeClient:
    """Counts requests, because the count is the thing under test."""

    def __init__(self, output_text):
        self.calls = 0
        self._output_text = output_text
        self.interactions = self

    def create(self, **kwargs):
        self.calls += 1
        return _FakeInteraction(self._output_text)


def test_malformed_shape_costs_one_request(monkeypatch):
    """The whole point of normalising locally.

    A shape the code can't handle triggers a reformatting request — a
    second call out of 20/day, which in the run that motivated this came
    back in the same wrong shape, losing the question and the quota. Every
    deviation absorbed here has to stay absorbed."""
    import gemini_integration_example as gie

    client = _FakeClient(MALFORMED_RESPONSE)
    monkeypatch.setattr(gie, "get_client", lambda *a, **k: client)

    question = gie.generate_question(
        certification="AWS Solutions Architect Associate (SAA-C03)",
        target_concepts=["Secrets Manager vs Parameter Store"],
        mastered_concepts=[],
        question_type="conceptual",
        difficulty="medium",
    )

    assert client.calls == 1, "a repair call was made for a shape we can normalise"
    assert question.correct_index == 0
    assert question.options[0] == "AWS Secrets Manager"
    assert question.domain == "Design Secure Architectures"
    assert question.question_type == "conceptual"
    assert "rotates credentials natively" in question.explanation


def test_unrecoverable_shape_keeps_the_raw_text(monkeypatch):
    """When repair can't help either, the text still has to survive — it
    cost a request, and it's reviewable by hand."""
    import gemini_integration_example as gie

    client = _FakeClient('{"question": "Missing everything else"}')
    monkeypatch.setattr(gie, "get_client", lambda *a, **k: client)

    with pytest.raises(gie.StructuredOutputError) as caught:
        gie.generate_question(
            certification="AWS Solutions Architect Associate (SAA-C03)",
            target_concepts=["anything"],
            mastered_concepts=[],
            question_type="conceptual",
            difficulty="medium",
        )
    assert "Missing everything else" in caught.value.raw


# ---------------------------------------------------------------------
# Model fallback: a 5xx from one model is retried once on another.
# ---------------------------------------------------------------------

class _FakeStatusError(Exception):
    """Stands in for the SDK's APIStatusError, which is what _interact
    checks the status code on."""
    def __init__(self, status_code):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class _FlakyClient:
    """Fails on the primary model with the given status, succeeds on any other."""
    def __init__(self, status):
        self.status = status
        self.models_tried = []
        self.interactions = self

    def create(self, model, **kwargs):
        self.models_tried.append(model)
        if model == "primary":
            raise _FakeStatusError(self.status)
        return _FakeInteraction('{"ok": true}')


def _patch_fallback(monkeypatch, gie, status):
    client = _FlakyClient(status)
    monkeypatch.setattr(gie, "get_client", lambda *a, **k: client)
    monkeypatch.setattr(gie, "MODEL", "primary")
    monkeypatch.setattr(gie, "FALLBACK_MODEL", "fallback")
    import google.genai._gaos.lib.compat_errors as ce
    monkeypatch.setattr(ce, "APIStatusError", _FakeStatusError)
    return client


def test_server_error_falls_back_to_the_other_model(monkeypatch):
    """Seen live: "currently experiencing high demand" on the only live call
    in the user flow. That's the model's problem, not the request's."""
    import gemini_integration_example as gie
    client = _patch_fallback(monkeypatch, gie, 500)
    result = gie._interact(input="x")
    assert result.output_text == '{"ok": true}'
    assert client.models_tried == ["primary", "fallback"]


def test_rate_limit_is_not_retried_on_another_model(monkeypatch):
    """Grounding quota is shared across models, so a blind retry on 429 would
    usually spend a request to fail the same way. Let it surface."""
    import gemini_integration_example as gie
    client = _patch_fallback(monkeypatch, gie, 429)
    with pytest.raises(_FakeStatusError):
        gie._interact(input="x")
    assert client.models_tried == ["primary"]


def test_timeout_falls_back_to_the_other_model(monkeypatch):
    """A model under load may hang rather than fail. The client timeout turns
    that into a timeout error, which must reach the fallback too."""
    import gemini_integration_example as gie
    import google.genai._gaos.lib.compat_errors as ce

    class _FakeTimeout(Exception):
        pass

    class _HangingClient:
        def __init__(self):
            self.models_tried = []
            self.interactions = self
        def create(self, model, **kwargs):
            self.models_tried.append(model)
            if model == "primary":
                raise _FakeTimeout("timed out")
            return _FakeInteraction('{"ok": true}')

    client = _HangingClient()
    monkeypatch.setattr(gie, "get_client", lambda *a, **k: client)
    monkeypatch.setattr(gie, "MODEL", "primary")
    monkeypatch.setattr(gie, "FALLBACK_MODEL", "fallback")
    monkeypatch.setattr(ce, "APITimeoutError", _FakeTimeout)
    assert gie._interact(input="x").output_text == '{"ok": true}'
    assert client.models_tried == ["primary", "fallback"]
