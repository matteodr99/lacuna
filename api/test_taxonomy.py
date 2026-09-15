"""
Tests for the two fields the adaptive selection depends on.

`domain` and `concept_tags` were free text on both entry paths, and the bank
drifted to 12 distinct domain strings for 4 exam domains, plus tags that
differed only in capitalisation. Nothing failed — `select_next_question()` just
matched fewer of a user's weak concepts than it should have. These tests pin
the fix, because that kind of regression is invisible at runtime.

Run: .venv/bin/python -m pytest test_taxonomy.py -v
"""

import import_questions
from db_schema import EXAM_DOMAINS, canonical_tags, tag_key
from seed_questions import expand_plan


def test_every_planned_job_carries_a_valid_domain():
    """The plan knows the exam domain of each job, so the model is never asked
    to name it. This is the guard that keeps it that way."""
    jobs = list(expand_plan())
    assert jobs
    for job in jobs:
        assert job["domain"] in EXAM_DOMAINS, job


def test_tag_key_ignores_case_and_final_plural():
    assert tag_key("Caching Strategies") == tag_key("caching strategies")
    assert tag_key("S3 bucket policy") == tag_key("S3 bucket policies")


def test_canonical_tags_adopts_the_spelling_already_in_the_bank():
    known = ["caching strategies", "S3 bucket policies"]
    assert canonical_tags(["Caching Strategies", "S3 bucket policy"], known) == known


def test_canonical_tags_keeps_unknown_tags_untouched():
    assert canonical_tags(["Redshift Spectrum"], ["caching strategies"]) == ["Redshift Spectrum"]


def test_canonical_tags_does_not_merge_different_granularity():
    """'visibility timeout' and 'SQS visibility timeout' are different levels
    of detail, not two spellings of one thing. Merging them is a judgement
    about meaning, so the code leaves it to a human."""
    known = ["SQS visibility timeout"]
    assert canonical_tags(["visibility timeout"], known) == ["visibility timeout"]


def test_canonical_tags_drops_duplicates_the_rewrite_creates():
    known = ["caching strategies"]
    result = canonical_tags(["Caching Strategies", "caching strategies"], known)
    assert result == ["caching strategies"]


def _entry(**overrides):
    entry = {
        "certification": "AWS Solutions Architect Associate (SAA-C03)",
        "domain": "Design Secure Architectures",
        "question": "q?",
        "options": ["a", "b", "c", "d"],
        "correct_index": 0,
        "explanation": "because",
        "concept_tags": ["IAM"],
        "question_type": "conceptual",
        "difficulty": "medium",
    }
    entry.update(overrides)
    return entry


def test_import_rejects_a_domain_outside_the_four():
    errors = import_questions.validate(_entry(domain="Storage"), 0)
    assert any("exam domains" in e for e in errors)


def test_import_accepts_each_blueprint_domain():
    for domain in EXAM_DOMAINS:
        assert import_questions.validate(_entry(domain=domain), 0) == []


# ---------------------------------------------------------------------
# Sources: what a reviewer checks a claim against
# ---------------------------------------------------------------------

def test_import_accepts_a_batch_without_sources():
    """Gemini-generated questions have none, and hand-written batches predate
    the field. Their absence is a fact to show the reviewer, not an error."""
    assert import_questions.validate(_entry(), 0) == []


def test_import_rejects_a_malformed_sources_field():
    errors = import_questions.validate(_entry(sources="https://docs.aws.amazon.com"), 0)
    assert any("sources" in e for e in errors)


def test_import_rejects_option_explanations_of_the_wrong_length():
    errors = import_questions.validate(_entry(option_explanations=["only", "three", "given"]), 0)
    assert any("option_explanations" in e for e in errors)


def test_import_accepts_four_option_explanations():
    assert import_questions.validate(_entry(option_explanations=["a", "b", "c", "d"]), 0) == []
