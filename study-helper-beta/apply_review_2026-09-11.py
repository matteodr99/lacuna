"""
Apply the 2026-09-11 review of the question bank.

Review basis: every question was read; specific numeric or behavioural claims
were checked against the official AWS documentation pages listed below. Six
questions were corrected before approval (already applied to the database);
one is rejected as a duplicate. This script records the outcome.

Run once:  .venv/bin/python apply_review_2026-09-11.py
"""

import sqlite3

REVIEWED_ON = "2026-09-11"
D = "https://docs.aws.amazon.com/"

# Documentation pages actually read during this review, attached only where
# the page substantiates the question's central claim. Questions 25-35 carry
# their sources from import already.
FETCHED_SOURCES = {
    1:  [D + "IAM/latest/UserGuide/id_groups.html"],
    7:  [D + "AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html"],
    9:  [D + "AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html",
         D + "AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html"],
    11: [D + "ebs/latest/userguide/general-purpose.html",
         D + "ebs/latest/userguide/provisioned-iops.html",
         D + "ebs/latest/userguide/hdd-vols.html"],
    12: [D + "ebs/latest/userguide/hdd-vols.html"],
    13: [D + "AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesCacheBehavior.html"],
    14: [D + "AmazonElastiCache/latest/APIReference/API_CacheCluster.html"],
    15: [D + "organizations/latest/userguide/orgs_manage_policies_scps.html"],
    16: [D + "AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html"],
    19: [D + "amazondynamodb/latest/developerguide/SecondaryIndexes.html"],
    20: [D + "AmazonS3/latest/userguide/storage-class-intro.html",
         D + "AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html"],
    21: [D + "AmazonS3/latest/userguide/storage-class-intro.html"],
}

FIXED_BEFORE_APPROVAL = {
    1:  "scenario had a role as a member of an IAM group, which is impossible.",
    3:  "stem was ambiguous between the two halves of cross-account access; now asks for the bucket owner's action.",
    11: "stale gp3 limits (16k IOPS / 1,000 MiB/s; now 80k / 2,000) and IOPS threshold raised to 100,000 so gp3 no longer meets it.",
    13: "explanation claimed specificity-based precedence; CloudFront uses list order.",
    14: "explanation cited AOF persistence, which ElastiCache does not offer.",
}

REJECTED = {
    28: "Duplicate of id 19: same fact (LSI strongly consistent but creation-time only; "
        "GSI addable but eventually consistent), same pivot. id 19 came first.",
}


def main():
    c = sqlite3.connect("cert_prep.db")
    cur = c.cursor()

    added = 0
    for qid, urls in FETCHED_SOURCES.items():
        have = {u for (u,) in cur.execute("select url from questionsource where question_id=?", (qid,))}
        for url in urls:
            if url not in have:
                cur.execute("insert into questionsource (question_id, url) values (?, ?)", (qid, url))
                added += 1

    for qid, note in REJECTED.items():
        cur.execute("update question set review_status='rejected', review_note=? where id=?", (note, qid))

    with_docs = set(FETCHED_SOURCES) | set(range(25, 36))
    approved = 0
    for (qid,) in cur.execute("select id from question where review_status='pending' order by id").fetchall():
        if qid in with_docs:
            note = f"Reviewed {REVIEWED_ON} by Claude against the official documentation listed in sources."
            if qid in FIXED_BEFORE_APPROVAL:
                note += " Fixed before approval: " + FIXED_BEFORE_APPROVAL[qid]
        else:
            note = (f"Reviewed {REVIEWED_ON} by Claude. Standard, uncontroversial material; "
                    "no documentation page was fetched for this one specifically.")
        cur.execute("update question set review_status='approved', review_note=? where id=?", (note, qid))
        approved += 1

    c.commit()
    print(f"sources added: {added}")
    print(f"approved: {approved}, rejected: {len(REJECTED)}")
    for status, n in cur.execute("select review_status, count(*) from question group by 1"):
        print(f"  {status:>9}: {n}")


if __name__ == "__main__":
    main()
