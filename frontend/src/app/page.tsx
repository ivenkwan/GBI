"use client";

import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Database,
  ShieldCheck,
  Sparkles,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";

interface Feature {
  icon: LucideIcon;
  title: string;
  text: string;
  iconColor: string;
  iconBox: string;
  hoverBorder: string;
}

const FEATURES: Feature[] = [
  {
    icon: Sparkles,
    title: "Ask in plain English",
    text: "Natural-language analytics with schema grounding and few-shot retrieval.",
    iconColor: "text-indigo-400",
    iconBox: "bg-indigo-500/10 border-indigo-500/20",
    hoverBorder: "hover:border-indigo-500/30",
  },
  {
    icon: Database,
    title: "Governed NL → SQL",
    text: "Every query is validated, read-only, and row-level secured per tenant.",
    iconColor: "text-cyan-400",
    iconBox: "bg-cyan-500/10 border-cyan-500/20",
    hoverBorder: "hover:border-cyan-500/30",
  },
  {
    icon: BarChart3,
    title: "Reports & dashboards",
    text: "Multi-chart reports from one prompt; pin sections to a board.",
    iconColor: "text-teal-400",
    iconBox: "bg-teal-500/10 border-teal-500/20",
    hoverBorder: "hover:border-teal-500/30",
  },
  {
    icon: BookOpen,
    title: "Living knowledge base",
    text: "A tenant wiki that feeds the AI pipeline real business context.",
    iconColor: "text-purple-400",
    iconBox: "bg-purple-500/10 border-purple-500/20",
    hoverBorder: "hover:border-purple-500/30",
  },
  {
    icon: ShieldCheck,
    title: "Audit everything",
    text: "Token spend, latency, and feedback traced on every LLM call.",
    iconColor: "text-blue-400",
    iconBox: "bg-blue-500/10 border-blue-500/20",
    hoverBorder: "hover:border-blue-500/30",
  },
];

function LogoMark({ box = "h-8 w-8", icon = "h-5 w-5" }: { box?: string; icon?: string }) {
  return (
    <div
      className={`flex items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-cyan-400 shadow-lg shadow-indigo-500/30 ${box}`}
    >
      <Zap className={`text-white ${icon}`} strokeWidth={2.5} />
    </div>
  );
}

export default function HomePage() {
  const { isAuthenticated, loading } = useAuth();
  const authed = isAuthenticated && !loading;

  const navHref = authed ? "/chat" : "/login";
  const navLabel = authed ? "Open GenBI" : "Login";
  const ctaHref = navHref;
  const ctaLabel = authed ? "Open GenBI" : "Sign in to the demo";

  // Inline dark backgrounds below are hard fallbacks — the light text must
  // stay readable even if the Tailwind sheet fails to load (stale tab /
  // cached assets), instead of going white-on-white.
  return (
    <div
      className="relative flex min-h-screen flex-col overflow-x-hidden bg-slate-900 text-slate-50"
      style={{ backgroundColor: "#0f172a" }}
    >
      <nav
        className="fixed top-0 z-50 w-full border-b border-slate-800 bg-slate-900/80 backdrop-blur-md"
        style={{ backgroundColor: "rgba(15,23,42,0.8)" }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <Link href="/" className="flex flex-shrink-0 items-center">
              <div className="flex items-center gap-2">
                <LogoMark />
                <span className="text-xl font-bold tracking-tight text-white">GenBI</span>
              </div>
            </Link>
            <div>
              <Link
                href={navHref}
                className="inline-flex items-center justify-center rounded-full border border-slate-700 bg-slate-800 px-5 py-2 text-sm font-medium text-white transition-all duration-200 hover:bg-slate-700 hover:text-white focus:outline-none focus:ring-2 focus:ring-slate-900 focus:ring-offset-2 focus:ring-offset-slate-900"
              >
                {navLabel}
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <main className="flex-grow">
        <section className="relative overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-24">
          <div className="bg-grid-pattern pointer-events-none absolute inset-0 opacity-30" aria-hidden />
          <div
            className="pointer-events-none absolute top-0 left-1/2 w-full max-w-3xl -translate-x-1/2 opacity-40"
            aria-hidden
          >
            <div className="aspect-[2/1] rounded-full bg-gradient-to-b from-indigo-500/30 to-transparent blur-3xl" />
          </div>

          <div className="relative mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
            <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-sm font-medium text-indigo-300">
              <span className="flex h-2 w-2 rounded-full bg-indigo-500" />
              Now in open beta
            </div>

            <h1 className="mb-6 text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-7xl">
              <span className="block text-slate-100">Generative</span>
              <span className="mt-2 block bg-gradient-to-r from-indigo-400 via-cyan-400 to-teal-300 bg-clip-text text-transparent">
                Business Intelligence
              </span>
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-xl font-medium text-slate-300 sm:text-2xl">
              Ask questions about your data. Get answers, charts, and insights.
            </p>

            <p className="mx-auto mt-4 max-w-3xl text-base leading-relaxed text-slate-400 sm:text-lg">
              Governed NL → SQL with validated queries, auto-visualization, and written
              narratives — multi-tenant, explainable, and audit-logged.
            </p>

            <div className="mt-10 flex flex-col justify-center gap-4 sm:flex-row">
              <Link
                href={ctaHref}
                className="inline-flex items-center justify-center rounded-full border border-transparent bg-gradient-to-r from-indigo-500 to-cyan-500 px-8 py-4 text-base font-semibold text-white transition-all duration-300 hover:shadow-lg hover:shadow-indigo-500/25 hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-slate-900"
              >
                {ctaLabel}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </div>
          </div>
        </section>

        <section
          className="relative border-t border-slate-800 bg-slate-900 py-20"
          style={{ backgroundColor: "#0f172a" }}
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mb-16 text-center">
              <h2 className="text-3xl font-bold text-white sm:text-4xl">Platform Capabilities</h2>
              <p className="mt-4 text-lg text-slate-400">
                Everything you need to deploy safe, reliable AI analytics.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ icon: Icon, title, text, iconColor, iconBox, hoverBorder }) => (
                <div
                  key={title}
                  className={`group rounded-2xl border border-slate-700/50 bg-slate-800/40 p-8 transition-all duration-300 hover:-translate-y-1 hover:bg-slate-800/80 ${hoverBorder}`}
                >
                  <div
                    className={`mb-6 flex h-12 w-12 items-center justify-center rounded-lg border transition-transform duration-300 group-hover:scale-110 ${iconBox}`}
                  >
                    <Icon className={`h-6 w-6 ${iconColor}`} strokeWidth={2} />
                  </div>
                  <h3 className="mb-3 text-xl font-semibold text-white">{title}</h3>
                  <p className="leading-relaxed text-slate-400">{text}</p>
                </div>
              ))}

              <div className="hidden items-center justify-center rounded-2xl border border-dashed border-slate-700/30 bg-transparent p-8 opacity-50 lg:flex">
                <p className="w-full text-center text-sm text-slate-500">
                  More integrations coming soon...
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer
        className="border-t border-slate-800 bg-slate-950 py-8"
        style={{ backgroundColor: "#020617" }}
      >
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <LogoMark box="h-6 w-6 rounded" icon="h-3 w-3" />
            <span className="text-lg font-bold tracking-tight text-slate-300">GenBI</span>
          </div>
          <p className="text-center text-sm text-slate-500 sm:text-left">
            © 2026 GenBI Inc. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
