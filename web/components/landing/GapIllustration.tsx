/**
 * The hero graphic: a field of things the candidate knows, with a few
 * tiles missing — the gaps — each labelled with the kind of detail the
 * bank targets. Inline SVG styled with the same zinc utilities as the
 * page, so it follows light/dark without a second asset.
 *
 * Decorative: the heading next to it says the same thing in words.
 */

const COLS = 6;
const ROWS = 5;
const TILE_W = 36;
const TILE_H = 28;
const GAP = 8;
const PAD = 12;

const GAPS: { row: number; col: number; label: string; dx: number; dy: number }[] = [
  { row: 1, col: 4, label: "30-day minimum", dx: -84, dy: -34 },
  { row: 2, col: 1, label: "maxReceiveCount", dx: 22, dy: 32 },
  { row: 3, col: 3, label: "7224:9xxx", dx: 24, dy: 30 },
];

const W = PAD * 2 + COLS * (TILE_W + GAP) - GAP;
const H = PAD * 2 + ROWS * (TILE_H + GAP) - GAP + 24;

export default function GapIllustration({ className = "" }: { className?: string }) {
  const tiles: { row: number; col: number }[] = [];
  for (let row = 0; row < ROWS; row++) {
    for (let col = 0; col < COLS; col++) tiles.push({ row, col });
  }
  const isGap = (row: number, col: number) => GAPS.some((g) => g.row === row && g.col === col);
  const x = (col: number) => PAD + col * (TILE_W + GAP);
  const y = (row: number) => PAD + row * (TILE_H + GAP);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={className}
      aria-hidden
      focusable="false"
    >
      {tiles.map(({ row, col }) =>
        isGap(row, col) ? (
          <rect
            key={`${row}-${col}`}
            x={x(col) + 0.5}
            y={y(row) + 0.5}
            width={TILE_W - 1}
            height={TILE_H - 1}
            rx={5}
            fill="none"
            strokeDasharray="3 3"
            className="stroke-zinc-900 dark:stroke-zinc-100"
          />
        ) : (
          <rect
            key={`${row}-${col}`}
            x={x(col)}
            y={y(row)}
            width={TILE_W}
            height={TILE_H}
            rx={5}
            className="fill-zinc-200 dark:fill-zinc-800"
          />
        ),
      )}

      {GAPS.map((gap) => {
        const cx = x(gap.col) + TILE_W / 2;
        const cy = y(gap.row) + TILE_H / 2;
        const chipX = cx + gap.dx;
        const chipY = cy + gap.dy;
        const chipW = gap.label.length * 6.6 + 16;
        const chipH = 20;
        return (
          <g key={gap.label}>
            <line
              x1={cx}
              y1={cy}
              x2={gap.dx < 0 ? chipX + chipW : chipX}
              y2={chipY + chipH / 2}
              className="stroke-zinc-400 dark:stroke-zinc-500"
            />
            <rect
              x={chipX}
              y={chipY}
              width={chipW}
              height={chipH}
              rx={4}
              className="fill-white stroke-zinc-300 dark:fill-zinc-950 dark:stroke-zinc-700"
            />
            <text
              x={chipX + 8}
              y={chipY + 14}
              fontSize={11}
              fontFamily="var(--font-geist-mono), ui-monospace, monospace"
              className="fill-zinc-800 dark:fill-zinc-200"
            >
              {gap.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
