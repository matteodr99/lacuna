/** The `certification` string is a free-text column on the backend, so the
 * value here has to match what seed_questions.py wrote into the bank
 * character for character or /questions/next returns an empty result. */
export type Certification = {
  id: string;
  provider: "AWS" | "Azure" | "GCP";
  name: string;
  blurb: string;
  available: boolean;
};

export const CERTIFICATIONS: Certification[] = [
  {
    id: "AWS Solutions Architect Associate (SAA-C03)",
    provider: "AWS",
    name: "Solutions Architect Associate",
    blurb: "SAA-C03 — networking, storage classes, resilience patterns.",
    available: true,
  },
  {
    id: "Azure Administrator Associate (AZ-104)",
    provider: "Azure",
    name: "Administrator Associate",
    blurb: "AZ-104 — question bank not seeded yet.",
    available: false,
  },
  {
    id: "Google Professional Cloud Architect",
    provider: "GCP",
    name: "Professional Cloud Architect",
    blurb: "Question bank not seeded yet.",
    available: false,
  },
];

export function findCertification(id: string): Certification | undefined {
  return CERTIFICATIONS.find((c) => c.id === id);
}
