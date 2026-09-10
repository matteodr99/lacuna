"""
Import questions from a JSON file into the bank.

Alternative path to seed_questions.py, for questions written and
fact-checked outside the Gemini pipeline. Same destination, same rules:
everything lands as review_status=pending and still goes through
review_questions.py before any user sees it. Being hand-checked doesn't
buy a pass on review — the review step is also where you catch a question
that's factually right but badly worded or ambiguous.

Usage:
    python import_questions.py questions.json
    python import_questions.py questions.json --dry-run
"""

import argparse
import json
import sys

from sqlmodel import Session, select

from db_schema import (
    EXAM_DOMAINS,
    Difficulty,
    Question,
    QuestionType,
    ReviewStatus,
    canonical_tags,
    create_db_and_tables,
    engine,
)

REQUIRED = {"certification", "domain", "question", "options", "correct_index",
            "explanation", "concept_tags", "question_type", "difficulty"}


def validate(entry: dict, index: int) -> list[str]:
    errors = []
    missing = REQUIRED - entry.keys()
    if missing:
        errors.append(f"missing fields: {', '.join(sorted(missing))}")
        return errors

    if not isinstance(entry["options"], list) or len(entry["options"]) != 4:
        errors.append(f"options must be a list of exactly 4, got {len(entry.get('options', []))}")
    if not isinstance(entry["correct_index"], int) or not 0 <= entry["correct_index"] <= 3:
        errors.append(f"correct_index must be 0-3, got {entry['correct_index']!r}")
    if entry["domain"] not in EXAM_DOMAINS:
        errors.append(f"domain must be one of the four exam domains, got {entry['domain']!r}")
    if entry["question_type"] not in {t.value for t in QuestionType}:
        errors.append(f"bad question_type: {entry['question_type']!r}")
    if entry["difficulty"] not in {d.value for d in Difficulty}:
        errors.append(f"bad difficulty: {entry['difficulty']!r}")
    if not entry["concept_tags"]:
        errors.append("concept_tags is empty")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="JSON file containing a list of questions")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    args = parser.parse_args()

    with open(args.path) as f:
        entries = json.load(f)
    if not isinstance(entries, list):
        sys.exit("Expected a JSON list of question objects.")

    all_errors = []
    for i, entry in enumerate(entries):
        for err in validate(entry, i):
            all_errors.append(f"  [{i}] {err}")
    if all_errors:
        print(f"Validation failed for {args.path}:")
        print("\n".join(all_errors))
        sys.exit(1)

    print(f"{len(entries)} question(s) valid.")
    if args.dry_run:
        for e in entries:
            print(f"  [{e['question_type']}/{e['difficulty']}] {e['domain']}: {e['question'][:60]}...")
        return

    create_db_and_tables()
    imported, skipped = 0, 0
    with Session(engine) as session:
        bank = session.exec(select(Question)).all()
        existing = {q.question_text for q in bank}
        # Match incoming tags to the spelling the bank already uses, so an
        # import can't fork the vocabulary the adaptive selection keys on.
        known_tags = sorted({t for q in bank for t in q.concept_tags})
        renamed = []
        for entry in entries:
            if entry["question"] in existing:
                skipped += 1
                continue
            tags = canonical_tags(entry["concept_tags"], known_tags)
            renamed += [(a, b) for a, b in zip(entry["concept_tags"], tags) if a != b]
            session.add(Question(
                certification=entry["certification"],
                domain=entry["domain"],
                question_text=entry["question"],
                options=entry["options"],
                correct_index=entry["correct_index"],
                explanation=entry["explanation"],
                concept_tags=tags,
                question_type=QuestionType(entry["question_type"]),
                difficulty=Difficulty(entry["difficulty"]),
                review_status=ReviewStatus.pending,
            ))
            imported += 1
        session.commit()

    print(f"Imported {imported}, skipped {skipped} duplicate(s).")
    for before, after in dict.fromkeys(renamed):
        print(f"  tag {before!r} -> {after!r} (spelling already in the bank)")
    if imported:
        print("Saved as PENDING — run `python review_questions.py` before they reach users.")


if __name__ == "__main__":
    main()
