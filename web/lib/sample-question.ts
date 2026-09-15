import type { Question } from "@/lib/api";

/**
 * One approved question, copied verbatim from the bank (id 30, reviewed
 * 2026-09-11) so the landing page can show the product without a request
 * to the API — which sleeps on the free tier and would leave the page's
 * first impression waiting on a cold start.
 *
 * It is static on purpose, and this one was chosen on purpose: it is the
 * product's thesis in a single question. Everyone knows S3 has storage
 * classes; the detail that decides the bill is that AWS removed one 30-day
 * rule in 2026 and kept the other. The sources are the pages the reviewer
 * actually checked, so the landing shows the same evidence the review
 * queue shows.
 *
 * Keep in sync with the bank if the question is ever corrected there:
 * the bank is the source of truth, this is a copy.
 */
export const SAMPLE_QUESTION: Question = {
  id: 30,
  question:
    "A team writes log objects to S3 Standard and configures a lifecycle rule that transitions them to S3 Standard-IA 0 days after creation, because the logs are cold within hours. A separate rule expires the objects 10 days after creation. What is the effect on the S3 bill?",
  options: [
    "The transition is accepted, but each object still incurs the 30-day minimum storage duration charge for S3 Standard-IA, so expiring at day 10 is billed for the remaining 20 days as well.",
    "The lifecycle configuration is rejected, because objects must remain in S3 Standard for at least 30 days before transitioning to S3 Standard-IA.",
    "The transition is accepted and billing simply stops at expiry, because the minimum storage duration applies only to the S3 Glacier storage classes.",
    "The transition is accepted, and the minimum storage duration charge is waived because the object is expired by a lifecycle rule rather than deleted directly.",
  ],
  domain: "Design Cost-Optimized Architectures",
  concept_tags: ["S3 storage classes", "lifecycle transition rules", "minimum storage duration"],
  question_type: "detail_recall",
  difficulty: "medium",
};

export const SAMPLE_CORRECT_INDEX = 0;

/** One reason per option, aligned with `SAMPLE_QUESTION.options`. */
export const SAMPLE_OPTION_EXPLANATIONS: string[] = [
  "Two separate 30-day rules, only one of which was removed: the minimum wait before a lifecycle rule may transition to Standard-IA no longer exists, so a 0-day transition is valid, but Standard-IA still bills a 30-day minimum storage duration. Expiring at day 10 incurs a pro-rated charge for the remaining 20 days.",
  "The 30-day minimum before transitioning to S3 Standard-IA or One Zone-IA was removed in July 2026. A 0-day transition is accepted.",
  "The minimum storage duration is not limited to the Glacier classes: S3 Standard-IA and One Zone-IA both bill for 30 days. Billing does not simply stop at expiry.",
  "The minimum duration charge applies whether an object is deleted, overwritten or transitioned away early. Expiring it through a lifecycle rule does not waive it.",
];

/** The official pages the review checked this question against. */
export const SAMPLE_SOURCES: { title: string; url: string }[] = [
  {
    title: "S3 removes the 30-day minimum for transitions to Standard-IA and One Zone-IA (What's New, July 2026)",
    url: "https://aws.amazon.com/about-aws/whats-new/2026/07/s3-removes-30-day-transitions-standard-ia-one-zone-ia/",
  },
  {
    title: "Amazon S3 storage classes",
    url: "https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html",
  },
  {
    title: "Lifecycle transition general considerations",
    url: "https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html",
  },
];
