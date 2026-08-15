"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  generateReport,
  getReport,
  listReports,
  type Report,
  type ReportSummary,
} from "@/lib/api-client";
import { ChartCard, type ChartAssemblyInput } from "@/components/charts/chart-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowLeft, FileText, Play } from "lucide-react";

export function ReportsView() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [prompt, setPrompt] = useState("");
  const [sectionCount, setSectionCount] = useState(3);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [active, setActive] = useState<Report | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  const loadReports = useCallback(async () => {
    try {
      const res = await listReports();
      setReports(res.reports);
    } catch {
      // Sidebar is best-effort
    }
  }, []);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handleGenerate = async () => {
    if (!prompt.trim() || generating) return;
    setGenerating(true);
    setError("");
    setActive(null);
    try {
      const report = await generateReport(prompt, sectionCount);
      setActive(report);
      loadReports();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Report generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleSelect = async (id: string) => {
    if (generating) return;
    setLoadingReport(true);
    setError("");
    try {
      setActive(await getReport(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load report");
    } finally {
      setLoadingReport(false);
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Reports sidebar */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Reports
          </span>
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {reports.length === 0 && (
            <p className="px-4 py-2 text-xs text-gray-400">No reports yet</p>
          )}
          {reports.map((r) => (
            <button
              key={r.id}
              onClick={() => handleSelect(r.id)}
              className={`w-full text-left px-4 py-2 transition-colors ${
                active?.report_id === r.id
                  ? "bg-brand-50 text-brand-700 border-l-2 border-brand-600"
                  : "text-gray-600 hover:bg-gray-50 border-l-2 border-transparent"
              }`}
            >
              <div className="text-sm truncate">{r.title}</div>
              <div className="text-[11px] text-gray-400">
                {r.section_count} section{r.section_count === 1 ? "" : "s"}
              </div>
            </button>
          ))}
        </div>
      </aside>

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0">
        <header className="shrink-0 flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-gray-900">Reports</h1>
              <p className="text-[11px] text-gray-500">Multi-chart reports from a prompt</p>
            </div>
          </div>
          <Link
            href="/chat"
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to chat
          </Link>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">
                {error}
              </div>
            )}

            {/* Generator */}
            <section className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex gap-3">
                <Input
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleGenerate();
                  }}
                  placeholder='e.g. "Q3 performance: revenue, pipeline, and active users"'
                  disabled={generating}
                  className="flex-1 rounded-xl"
                />
                <select
                  value={sectionCount}
                  onChange={(e) => setSectionCount(Number(e.target.value))}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-600"
                >
                  {[2, 3, 4].map((n) => (
                    <option key={n} value={n}>
                      {n} charts
                    </option>
                  ))}
                </select>
                <Button onClick={handleGenerate} disabled={generating || !prompt.trim()}>
                  <Play className="w-4 h-4 mr-1" />
                  {generating ? "Generating…" : "Generate"}
                </Button>
              </div>
              <p className="text-[10px] text-gray-400 mt-2">
                Picks metrics from the semantic layer, runs tenant-scoped queries, renders charts.
              </p>
            </section>

            {loadingReport && (
              <div className="flex items-center justify-center py-16">
                <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce" />
              </div>
            )}

            {/* Report display */}
            {active && !loadingReport && (
              <section className="space-y-6">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">{active.title}</h2>
                  {active.summary && (
                    <p className="text-sm text-gray-600 mt-2 leading-relaxed">{active.summary}</p>
                  )}
                  <div className="flex gap-2 mt-2">
                    <Badge variant="secondary">{active.sections.length} sections</Badge>
                    <Badge variant="outline">{new Date(active.created_at).toLocaleString()}</Badge>
                  </div>
                </div>

                {active.warnings.length > 0 && (
                  <div className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
                    {active.warnings.map((w, i) => (
                      <div key={i}>{w}</div>
                    ))}
                  </div>
                )}

                {active.sections.map((s) => (
                  <div
                    key={s.position}
                    className="bg-white border border-gray-200 rounded-xl p-4 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-gray-900">{s.section_title}</h3>
                      <span className="text-xs text-gray-400">
                        {s.data_total != null ? `Total: ${s.data_total.toLocaleString()}` : ""}
                        {` · ${s.row_count} rows`}
                      </span>
                    </div>
                    {s.chart_svg && (
                      <ChartCard
                        spec={s.chart_spec as unknown as ChartAssemblyInput}
                        svg={s.chart_svg}
                        title={s.section_title}
                      />
                    )}
                    {s.narrative && (
                      <p className="text-sm text-gray-600 leading-relaxed">{s.narrative}</p>
                    )}
                  </div>
                ))}
              </section>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
