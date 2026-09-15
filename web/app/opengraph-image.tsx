import { ImageResponse } from "next/og";

export const alt = "Lacuna — the details you forget, not the concepts you know";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** The share card. Built at request time from the same words as the hero,
 * so it can't drift from the page. System fonts only: a font fetch here
 * would be one more thing to fail on a cold start. */
export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 72,
          background: "#09090b",
          color: "#fafafa",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 28, fontWeight: 600, letterSpacing: -0.5 }}>
          <div style={{ display: "flex", flexWrap: "wrap", width: 34, height: 34, gap: 4 }}>
            <div style={{ width: 15, height: 15, borderRadius: 4, background: "#fafafa" }} />
            <div style={{ width: 15, height: 15, borderRadius: 4, background: "#fafafa" }} />
            <div style={{ width: 15, height: 15, borderRadius: 4, background: "#fafafa" }} />
            <div style={{ width: 15, height: 15, borderRadius: 4, border: "2px dashed #fbbf24" }} />
          </div>
          Lacuna
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 64, fontWeight: 600, lineHeight: 1.1, letterSpacing: -2 }}>
            The details you forget, not the concepts you know
          </div>
          <div style={{ width: 120, height: 8, borderRadius: 4, background: "#fbbf24" }} />
          <div style={{ fontSize: 28, color: "#a1a1aa", lineHeight: 1.4 }}>
            AWS SAA-C03 practice questions for experienced engineers — every claim
            checked against the official documentation.
          </div>
        </div>
      </div>
    ),
    size,
  );
}
