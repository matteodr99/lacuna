"""
Review pending questions before users see them.

This is the human checkpoint. Two hallucinations showed up during
development — one mixing up AWS BGP community families, one inventing
values that contradicted a correct answer the same model gave two calls
earlier. Grounding reduced but didn't eliminate that. So: nothing gets
served until a person reads it.

Verify against official docs (docs.aws.amazon.com, learn.microsoft.com,
cloud.google.com) before approving anything with specific numbers,
thresholds, or codes in it. That's where the errors concentrate.

Usage:
    python review_questions.py            # review pending, one at a time
    python review_questions.py --stats    # counts by status
"""

import argparse

from sqlmodel import Session, select

from db_schema import (
    Question,
    QuestionReport,
    QuestionSource,
    ReviewStatus,
    create_db_and_tables,
    engine,
)


def show_stats():
    with Session(engine) as session:
        questions = session.exec(select(Question)).all()
    if not questions:
        print("No questions in the bank yet. Run `python seed_questions.py` first.")
        return
    counts = {}
    for q in questions:
        counts[q.review_status.value] = counts.get(q.review_status.value, 0) + 1
    print("Question bank:")
    for status in ("approved", "pending", "rejected"):
        print(f"  {status:>9}: {counts.get(status, 0)}")
    print(f"  {'total':>9}: {len(questions)}")

    with Session(engine) as session:
        open_reports = session.exec(
            select(QuestionReport).where(QuestionReport.resolved == False)  # noqa: E712
        ).all()
    if open_reports:
        flagged = len({r.question_id for r in open_reports})
        print(f"\n  {len(open_reports)} open report(s) on {flagged} question(s)"
              f" — review them with `python review_questions.py --reported`")


def _sources(session, question_id: int) -> list[str]:
    return [r.url for r in session.exec(
        select(QuestionSource).where(QuestionSource.question_id == question_id)
    ).all()]


def _open_reports(session, question_id: int) -> list[QuestionReport]:
    return list(session.exec(
        select(QuestionReport).where(
            QuestionReport.question_id == question_id,
            QuestionReport.resolved == False,  # noqa: E712 — SQL comparison
        )
    ).all())


def render(q: Question, reports: list[QuestionReport] | None = None,
           sources: list[str] | None = None) -> None:
    print("=" * 72)
    print(f"[id {q.id}] {q.certification}")
    print(f"{q.domain} — {q.question_type.value} / {q.difficulty.value}")
    print(f"tags: {', '.join(q.concept_tags)}")
    print("-" * 72)
    print(q.question_text)
    print()
    for i, opt in enumerate(q.options):
        marker = "*" if i == q.correct_index else " "
        print(f"  {marker} {chr(65 + i)}. {opt}")
    print()
    print("EXPLANATION:")
    print(q.explanation)
    # The reviewer decides whether a specific threshold or code is real, so
    # what it was checked against belongs on screen next to the claim — not
    # in a batch file they would have to go and find.
    print()
    if sources:
        print("CHECKED AGAINST:")
        for url in sources:
            print(f"  {url}")
    else:
        print("CHECKED AGAINST: nothing recorded — verify every specific value yourself.")
    if reports:
        print("-" * 72)
        print(f"REPORTED BY USERS ({len(reports)}):")
        for r in reports:
            when = r.created_at.strftime("%Y-%m-%d")
            detail = f" — {r.detail}" if r.detail else ""
            print(f"  [{when}] {r.reason.value}{detail}")
    print("=" * 72)


def review():
    with Session(engine) as session:
        pending = session.exec(
            select(Question).where(Question.review_status == ReviewStatus.pending)
        ).all()

        if not pending:
            print("Nothing pending. Run `python seed_questions.py` to generate more.")
            return

        print(f"{len(pending)} question(s) pending review.\n")

        for idx, q in enumerate(pending, 1):
            print(f"\n--- {idx} of {len(pending)} ---")
            render(q, _open_reports(session, q.id), _sources(session, q.id))
            print("[a]pprove  [r]eject  [s]kip  [q]uit")
            choice = input("> ").strip().lower()

            if choice == "q":
                print("Stopped. Remaining questions stay pending.")
                break
            if choice == "a":
                q.review_status = ReviewStatus.approved
                session.add(q)
                session.commit()
                print("APPROVED — this one can now be served to users.")
            elif choice == "r":
                note = input("Reason (optional, helps improve the prompt later): ").strip()
                q.review_status = ReviewStatus.rejected
                q.review_note = note or None
                session.add(q)
                session.commit()
                print("REJECTED.")
            else:
                print("Skipped, still pending.")

    print()
    show_stats()


def review_reported():
    """Re-review questions that users have flagged.

    Distinct from the pending queue: these are already approved and being
    served right now, so they are the more urgent of the two. A report
    never pulls a question on its own — that would let one user empty
    everyone else's bank — so this is where a human decides whether the
    complaint holds."""
    with Session(engine) as session:
        open_reports = session.exec(
            select(QuestionReport).where(QuestionReport.resolved == False)  # noqa: E712
        ).all()
        if not open_reports:
            print("No open reports.")
            return

        by_question: dict[int, list[QuestionReport]] = {}
        for report in open_reports:
            by_question.setdefault(report.question_id, []).append(report)

        # Most-reported first: repeated complaints about the same question
        # are the strongest signal available that something is actually wrong.
        order = sorted(by_question, key=lambda qid: len(by_question[qid]), reverse=True)
        print(f"{len(open_reports)} open report(s) on {len(order)} question(s).\n")

        for idx, question_id in enumerate(order, 1):
            question = session.get(Question, question_id)
            if question is None:
                continue
            reports = by_question[question_id]
            print(f"\n--- {idx} of {len(order)} --- (status: {question.review_status.value})")
            render(question, reports, _sources(session, question_id))
            print("[k]eep as is  [r]eject and pull from the bank  [s]kip  [q]uit")
            choice = input("> ").strip().lower()

            if choice == "q":
                print("Stopped. Remaining reports stay open.")
                break
            if choice == "k":
                for report in reports:
                    report.resolved = True
                    session.add(report)
                session.commit()
                print("KEPT — reports closed, question still served.")
            elif choice == "r":
                note = input("Reason (optional): ").strip()
                question.review_status = ReviewStatus.rejected
                question.review_note = note or None
                session.add(question)
                for report in reports:
                    report.resolved = True
                    session.add(report)
                session.commit()
                print("REJECTED — no longer served.")
            else:
                print("Skipped, reports stay open.")

    print()
    show_stats()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", action="store_true", help="Show counts by review status")
    parser.add_argument("--reported", action="store_true",
                        help="Re-review questions users have flagged (these are already being served)")
    args = parser.parse_args()

    # Safe to call unconditionally — creates tables only if missing, so
    # running this before any seeding gives a clean "empty bank" message
    # instead of a SQL error.
    create_db_and_tables()

    if args.stats:
        show_stats()
    elif args.reported:
        review_reported()
    else:
        review()