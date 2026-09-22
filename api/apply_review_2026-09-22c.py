"""
Apply the review of questions_batch_6.json (ids 84-101), 2026-09-22.

The batch that takes the bank to 100 approved questions, and the third
written docs-first: source pages fetched and read before drafting, sources
recorded per question.

Facts the fetch corrected or pinned down, where a memory-first draft would
likely have been wrong or vague:

  - S3 Replication Time Control is documented as "most objects in seconds
    and 99.9 percent within 15 minutes" — commonly misremembered as 99.99%.
    The question quotes the user guide's figure.
  - KMS multi-Region keys share key ID and key material, but key policy,
    grants, aliases, tags and enabled state are *independent* and are never
    synchronised; and a single-Region key can never be converted.
  - CloudWatch retention is tiered and aggregating: 1-minute data for 15
    days, 5-minute for 63 days, 1-hour for 455 days.
  - GuardDuty ingests CloudTrail management events, VPC flow logs and DNS
    logs with nothing else to enable and no agent (agents belong to the
    optional Runtime Monitoring plan).
  - `MSCK REPAIR TABLE` works *only* with Hive-style key=value partitions;
    non-Hive layouts need ALTER TABLE ADD PARTITION or partition projection.
  - Shield Advanced covers standard AWS WAF costs on protected resources
    only, and not Bot Control or CAPTCHA.

Deliberate near-neighbours in this batch, kept because the pivots differ:
two AWS Backup questions (centralised cross-account plans vs lifecycle to
cold storage and incremental backups), two CloudWatch questions (metric
resolution and alarm period vs retention tiers), two Athena questions
(partition registration mechanics vs cost from data scanned).

One change before approval: the tag "monitoring" was dropped from the
CloudWatch retention question — a general form beside this batch's own
"security monitoring", and redundant with "CloudWatch metrics" and
"metrics retention" already on it.

Self-review caveat as before: writer and reviewer are the same agent, so
the second pass verifies wording, option balance and overlap, not the
facts. The facts rest on the pages recorded in QuestionSource.

Run once:  .venv/bin/python apply_review_2026-09-22c.py
"""

import sqlite3

REVIEWED_ON = "2026-09-22"
BATCH_IDS = range(84, 102)

NOTE = (
    f"Reviewed {REVIEWED_ON} by Claude against the official documentation listed in "
    "sources; each page was fetched and read before the question was written. "
    "Second read checked wording, option balance and overlap with the existing bank."
)


def main():
    c = sqlite3.connect("cert_prep.db")
    cur = c.cursor()
    approved = 0
    for qid in BATCH_IDS:
        row = cur.execute("select review_status from question where id=?", (qid,)).fetchone()
        if row is None or row[0] != "pending":
            print(f"skip {qid}: {row}")
            continue
        n_sources = cur.execute(
            "select count(*) from questionsource where question_id=?", (qid,)
        ).fetchone()[0]
        if n_sources == 0:
            raise SystemExit(f"question {qid} has no recorded source — refusing to approve")
        n_options = cur.execute(
            "select count(*) from optionexplanation where question_id=?", (qid,)
        ).fetchone()[0]
        if n_options != 4:
            raise SystemExit(f"question {qid} has {n_options} option explanations, expected 4")
        cur.execute(
            "update question set review_status='approved', review_note=? where id=?", (NOTE, qid)
        )
        approved += 1
    c.commit()
    print(f"approved: {approved}")
    for status, n in cur.execute("select review_status, count(*) from question group by 1"):
        print(f"  {status:>9}: {n}")


if __name__ == "__main__":
    main()
