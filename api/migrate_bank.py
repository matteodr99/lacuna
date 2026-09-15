"""
Copy the question bank from one database to another.

The bank — questions, their sources, their per-option explanations — is the
product's content and lives in the local SQLite file. Production runs on a
managed Postgres, so the content has to get there once (and again whenever
new questions are approved locally). Users, attempts, reports and analysis
snapshots are deliberately not copied: those belong to whichever database
the users are actually in.

Ids are preserved, so a question keeps its id across environments and the
sources and option explanations that point at it still line up. After an
insert with explicit ids, Postgres's id sequences are moved past them so
the next locally-approved question doesn't collide.

Usage:
    python migrate_bank.py --to "$DATABASE_URL"            # copy approved questions
    python migrate_bank.py --to "$DATABASE_URL" --dry-run  # say what would be copied
"""

import argparse
import sys

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from db_schema import OptionExplanation, Question, QuestionSource, ReviewStatus, engine as source_engine

BANK_TABLES = (Question, QuestionSource, OptionExplanation)


def _target_engine(url: str):
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return create_engine(url, pool_pre_ping=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help="Destination database URL")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-pending", action="store_true",
                        help="Also copy pending/rejected questions (default: approved only)")
    args = parser.parse_args()

    target_engine = _target_engine(args.to)
    if target_engine.url == source_engine.url:
        sys.exit("Source and destination are the same database.")

    with Session(source_engine) as src:
        questions = src.exec(select(Question)).all()
        if not args.include_pending:
            questions = [q for q in questions if q.review_status == ReviewStatus.approved]
        ids = {q.id for q in questions}
        sources = [s for s in src.exec(select(QuestionSource)).all() if s.question_id in ids]
        options = [o for o in src.exec(select(OptionExplanation)).all() if o.question_id in ids]

        print(f"{len(questions)} question(s), {len(sources)} source(s), {len(options)} option explanation(s)")
        if args.dry_run:
            return

        SQLModel.metadata.create_all(target_engine)
        with Session(target_engine) as dst:
            existing = {q.id for q in dst.exec(select(Question)).all()}
            copied = 0
            for row in questions + sources + options:
                if isinstance(row, Question) and row.id in existing:
                    continue
                if not isinstance(row, Question) and row.question_id in existing:
                    continue
                dst.add(type(row).model_validate(row.model_dump()))
                copied += 1
            dst.commit()

            if target_engine.dialect.name == "postgresql":
                # Explicit ids leave the sequences behind; move them past the
                # highest id so the next insert doesn't collide.
                for model in BANK_TABLES:
                    table = model.__tablename__
                    dst.exec(text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
                    ))
                dst.commit()

        print(f"copied {copied} row(s); {len(existing)} question(s) were already there")


if __name__ == "__main__":
    main()
