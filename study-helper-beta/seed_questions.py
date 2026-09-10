"""
Offline batch generation of the question bank.

This replaces the old per-user live generation. Run it yourself, occasionally,
to top up the bank — users never trigger a Gemini call while taking a test.

Why offline:
  - Cost/quota: one run seeds hundreds of questions; serving them is free.
  - Latency: users get an instant question instead of waiting 5-30s.
  - Accuracy: everything lands as review_status=pending. Nothing reaches a
    user until you approve it. This is the structural answer to the
    hallucinations found during development — prompt rules help, but they
    don't guarantee correctness, and someone studying for a $300 exam
    shouldn't be the one discovering a wrong answer.

Usage:
    python seed_questions.py --plan          # show what it would generate
    python seed_questions.py --limit 5       # generate 5 (respects free-tier quota)
    python seed_questions.py                 # generate the whole plan

Then review with:  python review_questions.py
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from db_schema import (
    Question,
    ReviewStatus,
    canonical_tags,
    create_db_and_tables,
    engine,
)
from gemini_integration_example import generate_question

# AWS SAA-C03 only, on purpose. Twenty-odd questions on one certification
# is a usable study session; six questions spread across three providers is
# a demo of nothing. Add Azure/GCP once this one is genuinely useful.
#
# Distribution follows the official SAA-C03 domain weightings, so the bank
# mirrors the real exam instead of whatever happened to come to mind:
#   Domain 1 Design Secure Architectures      30%  -> 7 questions
#   Domain 2 Design Resilient Architectures   26%  -> 6 questions
#   Domain 3 Design High-Performing           24%  -> 6 questions
#   Domain 4 Design Cost-Optimized            20%  -> 5 questions
#
# question_type mix leans conceptual (~2:1). detail_recall is the product's
# differentiator, but it's also where every hallucination found so far has
# happened, so it needs the most review attention per question. Don't push
# the ratio further toward detail_recall until review is less manual.

CERT = "AWS Solutions Architect Associate (SAA-C03)"

SEED_PLAN = [
    # --- Domain 1: Design Secure Architectures (30%) ---
    {
        "certification": CERT,
        "domain": "Design Secure Architectures",
        "target_concepts": ["IAM policy evaluation logic", "explicit deny vs allow"],
        "mastered_concepts": ["IAM users vs roles"],
        "variants": [("conceptual", "medium"), ("conceptual", "hard")],
    },
    {
        "certification": CERT,
        "domain": "Design Secure Architectures",
        "target_concepts": ["S3 bucket policies", "cross-account access", "resource-based policies"],
        "mastered_concepts": ["S3 basics"],
        "variants": [("conceptual", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design Secure Architectures",
        "target_concepts": ["security groups vs network ACLs", "stateful vs stateless filtering"],
        "mastered_concepts": ["VPC basics"],
        "variants": [("conceptual", "medium"), ("detail_recall", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design Secure Architectures",
        "target_concepts": ["KMS key policies", "encryption at rest", "envelope encryption"],
        "mastered_concepts": [],
        "variants": [("conceptual", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design Secure Architectures",
        "target_concepts": ["Secrets Manager vs Parameter Store", "credential rotation"],
        "mastered_concepts": [],
        "variants": [("conceptual", "medium")],
    },

    # --- Domain 2: Design Resilient Architectures (26%) ---
    {
        "certification": CERT,
        "domain": "Design Resilient Architectures",
        "target_concepts": ["Multi-AZ vs read replicas", "RDS failover behaviour"],
        "mastered_concepts": ["RDS basics"],
        "variants": [("conceptual", "medium"), ("detail_recall", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design Resilient Architectures",
        "target_concepts": ["Auto Scaling group health checks", "ELB health check integration"],
        "mastered_concepts": ["EC2 basics"],
        "variants": [("conceptual", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design Resilient Architectures",
        "target_concepts": ["SQS decoupling", "dead-letter queues", "visibility timeout"],
        "mastered_concepts": [],
        "variants": [("conceptual", "medium"), ("detail_recall", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design Resilient Architectures",
        "target_concepts": ["Route 53 routing policies", "health checks and failover"],
        "mastered_concepts": ["DNS basics"],
        "variants": [("conceptual", "hard")],
    },

    # --- Domain 3: Design High-Performing Architectures (24%) ---
    {
        "certification": CERT,
        "domain": "Design High-Performing Architectures",
        "target_concepts": ["EBS volume types", "IOPS vs throughput workloads"],
        "mastered_concepts": ["EC2 basics"],
        "variants": [("detail_recall", "medium"), ("conceptual", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design High-Performing Architectures",
        "target_concepts": ["CloudFront caching behaviour", "origin selection", "TTL"],
        "mastered_concepts": [],
        "variants": [("conceptual", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design High-Performing Architectures",
        "target_concepts": ["ElastiCache Redis vs Memcached", "caching strategies"],
        "mastered_concepts": [],
        "variants": [("conceptual", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design High-Performing Architectures",
        "target_concepts": ["DynamoDB partition key design", "hot partitions", "GSI vs LSI"],
        "mastered_concepts": ["DynamoDB basics"],
        "variants": [("conceptual", "hard"), ("detail_recall", "hard")],
    },

    # --- Domain 4: Design Cost-Optimized Architectures (20%) ---
    {
        "certification": CERT,
        "domain": "Design Cost-Optimized Architectures",
        "target_concepts": ["S3 storage classes", "lifecycle transition rules"],
        "mastered_concepts": ["S3 basics"],
        "variants": [("detail_recall", "medium"), ("conceptual", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design Cost-Optimized Architectures",
        "target_concepts": ["EC2 pricing models", "Reserved vs Savings Plans vs Spot"],
        "mastered_concepts": ["EC2 basics"],
        "variants": [("conceptual", "medium")],
    },
    {
        "certification": CERT,
        "domain": "Design Cost-Optimized Architectures",
        "target_concepts": ["NAT Gateway vs VPC endpoints", "data transfer cost"],
        "mastered_concepts": ["VPC basics"],
        "variants": [("conceptual", "hard")],
    },
    {
        "certification": CERT,
        "domain": "Design Cost-Optimized Architectures",
        "target_concepts": ["EBS snapshot cost", "data transfer charges between AZs and regions"],
        "mastered_concepts": [],
        "variants": [("detail_recall", "medium")],
    },
]


def expand_plan():
    for entry in SEED_PLAN:
        for question_type, difficulty in entry["variants"]:
            yield {
                "certification": entry["certification"],
                # Carried through from the plan rather than taken from the
                # model's answer: the plan already knows which exam domain the
                # job belongs to, and asking the model to name it is what
                # produced 12 distinct domain strings for 4 domains.
                "domain": entry["domain"],
                "target_concepts": entry["target_concepts"],
                "mastered_concepts": entry["mastered_concepts"],
                "question_type": question_type,
                "difficulty": difficulty,
            }


FAILED_DIR = Path("failed_generations")


def _save_raw_output(exc: Exception, index: int, job: dict) -> Optional[Path]:
    """Write the model text behind a parse failure to a file.

    A failed generation still consumed one of the day's 20 requests, and
    what fails is usually the structure, not the content. Keeping the text
    means a run that ends with failures leaves something reviewable rather
    than only a traceback."""
    raw = getattr(exc, "raw", None)
    if not raw:
        return None
    FAILED_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = FAILED_DIR / f"{stamp}-{index:02d}-{job['question_type']}.json"
    path.write_text(raw)
    return path


def parse_job_selection(spec: str, total: int) -> list[int]:
    """"7,8,11,18-20" -> [7, 8, 11, 18, 19, 20] (1-based, as --plan prints).

    Needed because --limit slices from the start of the plan, so re-running
    after a partial run regenerates questions already in the bank. On a
    20/day budget that's not a small waste: it is the whole day."""
    selected: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(x) for x in part.split("-", 1))
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))
    out_of_range = [n for n in selected if not 1 <= n <= total]
    if out_of_range:
        raise SystemExit(f"Job numbers out of range (plan has {total}): {sorted(out_of_range)}")
    return sorted(selected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Stop after N questions (free-tier quota is small)")
    parser.add_argument("--jobs", help="Job numbers from --plan, e.g. '7,8,11,18-20'. Use this to retry "
                                       "only what failed; --limit always restarts from the top of the plan.")
    parser.add_argument("--plan", action="store_true", help="Show the plan without calling the API")
    parser.add_argument("--delay", type=float, default=8.0,
                        help="Seconds between calls. Free tier allows ~5 requests/minute, so keep this >=12 if you hit 429s.")
    args = parser.parse_args()

    all_jobs = list(expand_plan())
    # Job numbers stay tied to the position in SEED_PLAN, so what --plan
    # prints is what --jobs accepts, run after run.
    jobs = list(enumerate(all_jobs, 1))
    if args.jobs:
        wanted = set(parse_job_selection(args.jobs, len(all_jobs)))
        jobs = [(number, job) for number, job in jobs if number in wanted]
    if args.limit:
        jobs = jobs[:args.limit]

    if args.plan:
        print(f"Would generate {len(jobs)} questions:\n")
        for i, job in jobs:
            print(f"  {i}. [{job['question_type']}/{job['difficulty']}] {job['certification']}")
            print(f"     concepts: {', '.join(job['target_concepts'])}")
        return

    create_db_and_tables()
    created, failed = 0, 0
    # The vocabulary already in the bank, so a generated tag lands on the
    # existing spelling instead of forking it.
    with Session(engine) as session:
        known_tags = sorted({t for q in session.exec(select(Question)).all() for t in q.concept_tags})

    for position, (i, job) in enumerate(jobs, 1):
        label = f"[{position}/{len(jobs)}] job {i}: {job['certification']} ({job['question_type']}/{job['difficulty']})"
        print(f"{label} ... ", end="", flush=True)
        try:
            result = generate_question(**{k: v for k, v in job.items() if k != "domain"})
        except Exception as exc:
            failed += 1
            print(f"FAILED: {type(exc).__name__}: {exc}")
            saved = _save_raw_output(exc, i, job)
            if saved:
                print(f"        raw output kept at {saved}")
            # A quota error will hit every subsequent call too — stop rather
            # than burning through the remaining budget on guaranteed failures.
            if "429" in str(exc) or "quota" in str(exc).lower():
                print("\nQuota exhausted. Stopping here; re-run later to continue.")
                break
            continue

        with Session(engine) as session:
            session.add(Question(
                certification=job["certification"],
                domain=job["domain"],
                question_text=result.question,
                options=result.options,
                correct_index=result.correct_index,
                explanation=result.explanation,
                concept_tags=canonical_tags(result.concept_tags, known_tags),
                question_type=result.question_type,
                difficulty=result.difficulty,
                review_status=ReviewStatus.pending,
            ))
            session.commit()
        created += 1
        print("ok")

        if position < len(jobs):
            time.sleep(args.delay)

    print(f"\nCreated {created}, failed {failed}.")
    if created:
        print("All saved as PENDING — run `python review_questions.py` before they reach users.")


if __name__ == "__main__":
    main()