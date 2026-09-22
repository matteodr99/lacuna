"""
Apply the 2026-09-22 review of questions_batch_4.json (ids 36-59).

Review basis: the batch was written and reviewed in the same session, with
every specific claim looked up on the documentation page recorded as the
question's source *before* the question was written — the pages were
fetched first, the questions drafted from what they said. Three facts had
changed since the usual training material and were caught by the fetch:
the S3 object ceiling is now 50 TB (was 5 TB), NAT gateways have a regional
availability mode, and Compute Savings Plans are "up to 66%" (was 66/72
split differently). The self-review caveat from the first pass applies:
the writer and the reviewer are the same agent. What the second read
checked was ambiguity and overlap with the existing bank, not facts.

One change before approval: the Aurora Global Database question carried
"cross-Region replication", which canonical_tags() folded onto the bank's
S3 tag "Cross-Region Replication" — the granularity trap PROJECT_CONTEXT
warns about. The tag was dropped; "Aurora Global Database" says it.

Run once:  .venv/bin/python apply_review_2026-09-22.py
"""

import sqlite3

REVIEWED_ON = "2026-09-22"
BATCH_IDS = range(36, 60)

NOTE = (
    f"Reviewed {REVIEWED_ON} by Claude against the official documentation listed in "
    "sources; each page was fetched and read before the question was written. "
    "Second read checked wording and overlap with the existing bank."
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
        n_sources = cur.execute("select count(*) from questionsource where question_id=?", (qid,)).fetchone()[0]
        if n_sources == 0:
            raise SystemExit(f"question {qid} has no recorded source — refusing to approve")
        cur.execute("update question set review_status='approved', review_note=? where id=?", (NOTE, qid))
        approved += 1
    c.commit()
    print(f"approved: {approved}")
    for status, n in cur.execute("select review_status, count(*) from question group by 1"):
        print(f"  {status:>9}: {n}")


if __name__ == "__main__":
    main()
