"""
Apply the review of questions_batch_5.json (ids 60-83), 2026-09-22.

Same method as batch 4: docs-first. Every source page was fetched and read
before its question was written, so the claims are drafted from the page
rather than checked against it afterwards. Facts this order caught that a
memory-first draft would likely have got wrong:

  - Cross-zone load balancing is *always on* at the load balancer level for
    an ALB (disableable per target group), off by default for NLB/GWLB, and
    console-vs-API dependent for CLB. The usual summary "on for ALB, off for
    NLB" is right by accident and wrong about where the switch lives.
  - Lambda gives one vCPU at 1,769 MB, and memory goes to 10,240 MB.
  - Aurora Serverless now scales to 0 ACUs (auto-pause); 0.5 was the floor.
  - Route 53 multivalue answer returns up to eight records.
  - A transit gateway carries 8500 bytes except over VPN, which is 1500.
  - RestrictPublicBuckets cuts non-public cross-account grants too, once any
    statement makes the policy public, while AWS service principals survive.

Two changes before approval, both tag hygiene rather than content:
  - "cost optimization" was dropped as a tag. It is a general form sitting
    beside the bank's "storage cost optimization" — the granularity drift
    PROJECT_CONTEXT warns about — so each question took a specific tag
    instead ("Step Functions pricing", "Aurora auto-pause") or none.

The self-review caveat stands: writer and reviewer are the same agent, so
what the second pass verifies is wording, option balance and overlap with
the existing bank, not the facts. The facts rest on the fetched pages, which
are recorded per question in QuestionSource.

Run once:  .venv/bin/python apply_review_2026-09-22b.py
"""

import sqlite3

REVIEWED_ON = "2026-09-22"
BATCH_IDS = range(60, 84)

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
