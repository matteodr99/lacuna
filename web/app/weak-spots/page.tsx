import WeakSpotsClient from "./WeakSpotsClient";
import Container from "@/components/Container";

export const metadata = {
  title: "Weak spots",
};

export default function WeakSpotsPage() {
  return (
    <Container className="py-10">
      <WeakSpotsClient />
    </Container>
  );
}
