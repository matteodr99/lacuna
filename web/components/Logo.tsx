/**
 * The Lacuna mark — direction A from the logo exploration of 2026-09-15:
 * the hero illustration reduced to four tiles, three known and one
 * missing, the gap drawn in amber. Inline SVG so it inherits the page's
 * light/dark tokens; `size` is the rendered box in px.
 *
 * The same geometry is repeated in app/icon.svg (favicon, static file so
 * it can carry its own dark-mode media query) and app/opengraph-image.tsx
 * (share card, Satori has no Tailwind). Change all three together.
 */
export function LogoMark({ size = 20, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      fill="none"
      aria-hidden
      focusable="false"
      className={className}
    >
      <rect x="6" y="6" width="23" height="23" rx="5" className="fill-zinc-900 dark:fill-zinc-100" />
      <rect x="35" y="6" width="23" height="23" rx="5" className="fill-zinc-900 dark:fill-zinc-100" />
      <rect x="6" y="35" width="23" height="23" rx="5" className="fill-zinc-900 dark:fill-zinc-100" />
      <rect
        x="36.25"
        y="36.25"
        width="20.5"
        height="20.5"
        rx="4.5"
        strokeWidth="2.5"
        strokeDasharray="4 3.5"
        className="stroke-amber-500 dark:stroke-amber-400"
      />
    </svg>
  );
}

/** Mark plus wordmark, for the header. */
export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <LogoMark size={20} />
      <span className="font-semibold tracking-tight">Lacuna</span>
    </span>
  );
}
