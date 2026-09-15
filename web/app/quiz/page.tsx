import Link from "next/link";
import QuizClient from "./QuizClient";
import Container from "@/components/Container";
import { findCertification } from "@/lib/certifications";

export default async function QuizPage({ searchParams }: PageProps<"/quiz">) {
  const { certification } = await searchParams;
  const id = typeof certification === "string" ? certification : undefined;
  const cert = id ? findCertification(id) : undefined;

  if (!cert || !cert.available) {
    return (
      <Container className="py-10">
        <div className="flex flex-col items-start gap-4">
          <h1 className="text-2xl font-semibold tracking-tight">
            No question bank for that certification
          </h1>
          <p className="text-zinc-600 dark:text-zinc-400">
            Pick one that has been seeded and reviewed.
          </p>
          <Link
            href="/"
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
          >
            Choose a certification
          </Link>
        </div>
      </Container>
    );
  }

  return (
    <Container className="py-10">
      <QuizClient certification={cert.id} label={`${cert.provider} ${cert.name}`} />
    </Container>
  );
}
