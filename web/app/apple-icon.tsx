import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

/** Home-screen icon: the mark on the dark ground, since iOS gives it no
 * theme to follow. Same geometry as components/Logo.tsx. */
export default function AppleIcon() {
  const tile = { width: 46, height: 46, borderRadius: 10, background: "#fafafa" };
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#09090b",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", width: 104, height: 104, gap: 12 }}>
          <div style={tile} />
          <div style={tile} />
          <div style={tile} />
          <div
            style={{
              width: 46,
              height: 46,
              borderRadius: 10,
              border: "4px dashed #fbbf24",
            }}
          />
        </div>
      </div>
    ),
    size,
  );
}
