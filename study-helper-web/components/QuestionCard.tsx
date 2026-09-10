import Markdown from "@/components/Markdown";
import type { Question } from "@/lib/api";

const TYPE_LABEL: Record<Question["question_type"], string> = {
  conceptual: "Conceptual",
  detail_recall: "Detail recall",
};

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-zinc-200 px-2 py-0.5 text-xs text-zinc-600 dark:border-zinc-800 dark:text-zinc-400">
      {children}
    </span>
  );
}

type Props = {
  question: Question;
  selectedIndex: number | null;
  correctIndex: number | null;
  disabled: boolean;
  onSelect: (index: number) => void;
};

export default function QuestionCard({
  question,
  selectedIndex,
  correctIndex,
  disabled,
  onSelect,
}: Props) {
  const revealed = correctIndex !== null;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{question.domain}</Badge>
        <Badge>{TYPE_LABEL[question.question_type]}</Badge>
        <Badge>{question.difficulty}</Badge>
      </div>

      <div className="text-lg leading-7 font-medium">
        <Markdown>{question.question}</Markdown>
      </div>

      <ul className="flex flex-col gap-2" role="radiogroup" aria-label="Answer options">
        {question.options.map((option, index) => {
          const isSelected = selectedIndex === index;
          const isCorrect = revealed && correctIndex === index;
          const isWrongPick = revealed && isSelected && correctIndex !== index;

          let tone =
            "border-zinc-200 bg-white hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-600";
          if (isCorrect) {
            tone =
              "border-emerald-500 bg-emerald-50 dark:border-emerald-600 dark:bg-emerald-950/40";
          } else if (isWrongPick) {
            tone = "border-red-500 bg-red-50 dark:border-red-600 dark:bg-red-950/40";
          } else if (isSelected) {
            tone = "border-zinc-900 bg-white dark:border-zinc-100 dark:bg-zinc-900";
          }

          return (
            <li key={index}>
              <button
                type="button"
                role="radio"
                aria-checked={isSelected}
                disabled={disabled}
                onClick={() => onSelect(index)}
                className={`flex w-full items-start gap-3 rounded-lg border p-4 text-left transition-colors disabled:cursor-default ${tone}`}
              >
                <span className="mt-0.5 font-mono text-sm text-zinc-500 dark:text-zinc-400">
                  {String.fromCharCode(65 + index)}
                </span>
                <span className="flex-1 leading-6">
                  <Markdown>{option}</Markdown>
                </span>
                {isCorrect && (
                  <span className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
                    Correct
                  </span>
                )}
                {isWrongPick && (
                  <span className="text-sm font-medium text-red-700 dark:text-red-400">
                    Your answer
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
