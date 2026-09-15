/**
 * The four steps between a model (or a person) writing a question and a
 * candidate reading it, drawn as a stepper: a row on wide screens, a
 * column on narrow ones. Short lines only — the FAQ and the README carry
 * the detail.
 */

function Icon({ children }: { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={22}
      height={22}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {children}
    </svg>
  );
}

const STEPS = [
  {
    title: "Written offline",
    body: "Generated with search grounding, or written by hand. Never during a test.",
    icon: (
      <Icon>
        <rect x="5" y="3" width="14" height="18" rx="2" />
        <path d="M9 8h6M9 12h6M9 16h4" />
      </Icon>
    ),
  },
  {
    title: "Checked against the docs",
    body: "Every threshold and behaviour looked up in the official documentation. Pages recorded.",
    icon: (
      <Icon>
        <circle cx="11" cy="11" r="6.5" />
        <path d="m20 20-4-4" />
        <path d="m8.5 11 1.75 1.75L14 9" />
      </Icon>
    ),
  },
  {
    title: "Two reasons per answer",
    body: "Why your pick is wrong, why the right one is right. Reviewed text, not generated.",
    icon: (
      <Icon>
        <path d="M9 7h11M9 12h11M9 17h11" />
        <path d="m3.5 7 1 1 1.5-2M3.5 12l1 1 1.5-2M3.5 17l1 1 1.5-2" />
      </Icon>
    ),
  },
  {
    title: "Adapts to your misses",
    body: "Weak spots steer the next question. The model stays out of the loop.",
    icon: (
      <Icon>
        <circle cx="12" cy="12" r="8" />
        <circle cx="12" cy="12" r="3" />
        <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
      </Icon>
    ),
  },
];

export default function Pipeline() {
  return (
    <ol className="relative grid gap-8 md:grid-cols-4 md:gap-6">
      {/* The connecting rail: horizontal between the icons on wide screens,
          vertical down the left on narrow ones. */}
      <div
        aria-hidden
        className="absolute top-5 bottom-5 left-5 w-px bg-zinc-200 md:top-5 md:right-[12.5%] md:bottom-auto md:left-[12.5%] md:h-px md:w-auto dark:bg-zinc-800"
      />
      {STEPS.map((step, index) => (
        <li key={step.title} className="relative flex gap-4 md:flex-col md:items-center md:text-center">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-300">
            {step.icon}
          </span>
          <div className="flex flex-col gap-1 pt-2 md:pt-0">
            <h3 className="font-medium">
              <span className="mr-2 font-mono text-xs text-zinc-400 md:hidden">
                {index + 1}
              </span>
              {step.title}
            </h3>
            <p className="text-sm leading-6 text-zinc-600 dark:text-zinc-400">{step.body}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
