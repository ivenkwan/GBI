"use client";

import Link from "next/link";
import { BarChart3, BookOpen, Database, LayoutDashboard, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";

const FEATURES = [
  {
    icon: Sparkles,
    title: "Ask in plain English",
    text: "Natural-language analytics with schema grounding and few-shot retrieval.",
  },
  {
    icon: Database,
    title: "Governed NL → SQL",
    text: "Every query is validated, read-only, and row-level secured per tenant.",
  },
  {
    icon: LayoutDashboard,
    title: "Reports & dashboards",
    text: "Multi-chart reports from one prompt; pin sections to a board.",
  },
  {
    icon: BookOpen,
    title: "Living knowledge base",
    text: "A tenant wiki that feeds the AI pipeline real business context.",
  },
  {
    icon: ShieldCheck,
    title: "Audit everything",
    text: "Token spend, latency, and feedback traced on every LLM call.",
  },
];

export default function HomePage() {
  const { isAuthenticated, loading } = useAuth();

  return (
    <main className="flex min-h-screen flex-col bg-slate-900">
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            "radial-gradient(700px circle at 15% 10%, rgba(76,110,245,0.5), transparent 60%), radial-gradient(600px circle at 85% 90%, rgba(67,211,151,0.2), transparent 60%)",
        }}
        aria-hidden
      />

      <div className="relative mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-8">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600">
              <BarChart3 className="h-5 w-5 text-white" />
            </div>
            <span className="text-lg font-semibold text-white">GenBI</span>
          </div>
          {!loading && (
            <Link
              href={isAuthenticated ? "/chat" : "/login"}
              className="rounded-lg border border-white/20 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-white/10"
            >
              {isAuthenticated ? "Open GenBI" : "Sign in"}
            </Link>
          )}
        </header>

        <section className="flex flex-1 flex-col items-center justify-center py-16 text-center">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-slate-300">
            <Sparkles className="h-3 w-3 text-brand-300" />
            Generative Business Intelligence
          </p>
          <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight text-white sm:text-5xl">
            Ask questions about your data.
            <span className="text-slate-400"> Get answers, charts, and insights.</span>
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-slate-400">
            Governed NL → SQL with validated queries, auto-visualization, and written
            narratives — multi-tenant, explainable, and audit-logged.
          </p>
          <div className="mt-8">
            {loading ? (
              <span className="text-sm text-slate-500">Loading…</span>
            ) : (
              <Link
                href={isAuthenticated ? "/chat" : "/login"}
                className="rounded-lg bg-brand-600 px-6 py-3 font-medium text-white transition-colors hover:bg-brand-700"
              >
                {isAuthenticated ? "Open GenBI" : "Sign in to the demo"}
              </Link>
            )}
          </div>
        </section>

        <section className="grid gap-3 pb-8 sm:grid-cols-2 lg:grid-cols-5">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div
              key={title}
              className="rounded-xl border border-white/10 bg-white/5 p-4 text-left"
            >
              <span className="mb-3 flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
                <Icon className="h-4 w-4 text-brand-300" />
              </span>
              <p className="text-sm font-semibold text-white">{title}</p>
              <p className="mt-1 text-xs leading-relaxed text-slate-400">{text}</p>
            </div>
          ))}
        </section>
      </div>
    </main>
  );
}
