"use client";

import Markdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

/** Allow normal URLs plus inline data: images — persisted chat messages
 *  embed their rendered chart as a data-URI markdown image. */
function urlTransform(url: string): string {
  if (url.startsWith("data:image/")) return url;
  return defaultUrlTransform(url);
}

/**
 * MarkdownText — shared renderer for LLM-generated narratives and wiki
 * content (both are markdown). Without it the raw `**bold**` / `###` / `-`
 * markers render as literal text. Component-level styling keeps typography
 * consistent and compact without the typography plugin.
 */
export function MarkdownText({ children }: { children: string }) {
  return (
    <div className="markdown-text text-sm leading-relaxed text-gray-700">
      <Markdown
        remarkPlugins={[remarkGfm]}
        urlTransform={urlTransform}
        components={{
          img: ({ src, alt }) => (
            /* eslint-disable-next-line @next/next/no-img-element -- inline data-URI charts, no asset pipeline */
            <img
              src={typeof src === "string" ? src : undefined}
              alt={alt ?? "chart"}
              className="my-2 max-w-full rounded-lg border border-gray-100 bg-white"
            />
          ),
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          h1: ({ children }) => (
            <h1 className="mb-2 mt-4 text-lg font-semibold text-gray-900 first:mt-0">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-4 text-base font-semibold text-gray-900 first:mt-0">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-1.5 mt-3 text-sm font-semibold text-gray-900 first:mt-0">{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 className="mb-1.5 mt-3 text-sm font-semibold text-gray-800 first:mt-0">{children}</h4>
          ),
          ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
          ol: ({ children }) => (
            <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
          ),
          li: ({ children }) => <li className="pl-0.5">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ href, children }) => (
            <a href={href} className="text-brand-600 underline hover:text-brand-700" target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mb-2 border-l-2 border-gray-300 pl-3 text-gray-600 last:mb-0">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-3 border-gray-200" />,
          code: ({ className, children }) => {
            const isBlock = /language-/.test(className ?? "");
            if (isBlock) {
              return (
                <code className={`${className ?? ""} block rounded-lg bg-slate-900 px-3 py-2 font-mono text-xs leading-relaxed text-slate-100`}>
                  {children}
                </code>
              );
            }
            return (
              <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-xs text-gray-800">
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="mb-2 overflow-x-auto last:mb-0">{children}</pre>
          ),
          table: ({ children }) => (
            <div className="mb-2 overflow-x-auto last:mb-0">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
          th: ({ children }) => (
            <th className="border border-gray-200 px-2 py-1 text-left font-semibold text-gray-700">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-gray-200 px-2 py-1 text-gray-600">{children}</td>
          ),
        }}
      >
        {children}
      </Markdown>
    </div>
  );
}
