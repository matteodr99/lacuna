import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Question text and options come out of the generator as Markdown —
 * bold thresholds, bullet lists of requirements, fenced JSON for IAM
 * policies — so rendering them as plain text makes the exact detail the
 * question hinges on hard to read. Only the inline/block elements the
 * bank actually produces are styled; no raw HTML is allowed through
 * (react-markdown ignores it by default), since this content is
 * model-generated.
 */
export default function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
        strong: ({ children }) => (
          <strong className="font-semibold text-zinc-900 dark:text-zinc-50">{children}</strong>
        ),
        ul: ({ children }) => (
          <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
        ),
        code: ({ children, className }) =>
          // A fenced block gets a language class; inline code doesn't.
          className ? (
            <code className="font-mono text-xs leading-5">{children}</code>
          ) : (
            <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-[0.85em] dark:bg-zinc-800">
              {children}
            </code>
          ),
        pre: ({ children }) => (
          <pre className="mb-3 overflow-x-auto rounded-md bg-zinc-100 p-3 last:mb-0 dark:bg-zinc-800">
            {children}
          </pre>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
