"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  exportReportPdf,
  generateReport,
  getReport,
  getReportSchedule,
  listReports,
  regenerateReport,
  scheduleReport,
  unscheduleReport,
  type Report,
  type ReportSchedule,
  type ReportSummary,
} from "@/lib/api-client";
import { ChartCard } from "@/components/charts/chart-card";
import type { ChartAssemblyInput } from "@/types/chart";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CalendarClock, Download, FileText, LayoutDashboard, List, Play, RefreshCw } from "lucide-react";
import { Loader } from "@/components/ui/loader";
import { MarkdownText } from "@/components/ui/markdown";
import { PageHeader } from "@/components/layout/page-header";
import { Sheet } from "@/components/ui/sheet";
import { SidebarList } from "@/components/ui/sidebar-list";
import { useSelectionParam } from "@/hooks/use-selection-param";


function ReportsSidebarContent({
  reports,
  activeId,
  listError,
  onSelect,
}: {
  reports: ReportSummary[];
  activeId: string | null;
  listError?: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <>
      {listError && (
        <Alert variant="error" className="m-2 text-xs">
          {listError}
        </Alert>
      )}
      <div className="min-h-0 flex-1">
        <SidebarList
          title="Reports"
          items={reports.map((r) => ({
            id: r.id,
            label: r.title,
            secondary: `${r.section_count} sections`,
          }))}
          activeKey={activeId}
          onSelect={onSelect}
          emptyText="No reports yet"
        />
      </div>
    </>
  );
}

export function ReportsView() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [prompt, setPrompt] = useState("");
  const [sectionCount, setSectionCount] = useState(3);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [active, setActive] = useState<Report | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [schedule, setSchedule] = useState<ReportSchedule | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [listOpen, setListOpen] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [selected, setSelected] = useSelectionParam("report");
  const activeId = active?.report_id ?? null;

  const loadReports = useCallback(async () => {
    try {
      const res = await listReports();
      setReports(res.reports);
      setListError(null);
    } catch {
      setListError("Reports couldn't be loaded.");
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

  const handleSelect = useCallback(
    async (id: string, opts?: { silent?: boolean }) => {
      if (generating) return;
      setListOpen(false);
      setLoadingReport(true);
      if (!opts?.silent) setError("");
      try {
        setActive(await getReport(id));
        setSchedule(null);
        getReportSchedule(id).then(setSchedule).catch(() => setSchedule(null));
      } catch (e) {
        // A stale deep link falls back to the default view with no error
        // banner; a sidebar click still surfaces the failure.
        if (opts?.silent) setSelected(null);
        else setError(e instanceof Error ? e.message : "Could not load report");
      } finally {
        setLoadingReport(false);
      }
    },
    [generating, setSelected],
  );

  // Param → state: adopt a deep-linked report; invalid ids fall back to the
  // default view silently (no error banner for a stale shared link). Only a
  // param change can trigger this effect — comparing against the latest id
  // ref (not the state value in deps) keeps a click-driven state change
  // from re-firing it, which would ping-pong with the state → param effect.
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  useEffect(() => {
    if (!selected || selected === activeIdRef.current) return;
    handleSelect(selected, { silent: true });
  }, [selected, handleSelect]);

  // State → param: selection changes (click, generate, delete) sync the URL.
  useEffect(() => {
    if (selected === activeId) return;
    setSelected(activeId);
  }, [activeId, selected, setSelected]);

  const handleRegenerate = async () => {
    if (!active || regenerating) return;
    setRegenerating(true);
    setError("");
    try {
      setActive(await regenerateReport(active.report_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Regeneration failed");
    } finally {
      setRegenerating(false);
    }
  };

  const handleExportPdf = async () => {
    if (!active) return;
    setError("");
    try {
      const blob = await exportReportPdf(active.report_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `genbi-report-${active.report_id}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "PDF export failed");
    }
  };

  const handleSchedule = async (frequency: ReportSchedule["frequency"] | "off") => {
    if (!active || scheduling) return;
    setScheduling(true);
    setError("");
    try {
      if (frequency === "off") {
        await unscheduleReport(active.report_id);
        setSchedule(null);
      } else {
        setSchedule(await scheduleReport(active.report_id, frequency));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Schedule update failed");
    } finally {
      setScheduling(false);
    }
  };

  return (
    <div className="flex h-full bg-gray-50">
      {/* Reports sidebar */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
        <ReportsSidebarContent
          reports={reports}
          activeId={active?.report_id ?? null}
          listError={listError}
          onSelect={handleSelect}
        />
      </aside>

      <Sheet open={listOpen} onOpenChange={setListOpen} title="Reports">
        <div className="flex h-full flex-col">
          <ReportsSidebarContent
            reports={reports}
            activeId={active?.report_id ?? null}
            listError={listError}
            onSelect={handleSelect}
          />
        </div>
      </Sheet>

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0">
        <PageHeader
          title="Reports"
          description="Multi-chart reports from a prompt"
          icon={FileText}
          actions={
            <>
              <button
                type="button"
                onClick={() => setListOpen(true)}
                title="Reports list"
                className="md:hidden p-2 rounded-lg text-gray-600 transition-colors hover:bg-gray-100"
              >
                <List className="h-4 w-4" />
              </button>
              <Link
                href="/dashboards"
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100"
              >
                <LayoutDashboard className="h-4 w-4" />
                Dashboards
              </Link>
            </>
          }
        />

        <main className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
            {error && <Alert>{error}</Alert>}

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

            {loadingReport && <Loader />}

            {/* Report display */}
            {active && !loadingReport && (
              <section className="space-y-6">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">{active.title}</h2>
                  {active.summary && (
                    <p className="text-sm text-gray-600 mt-2 leading-relaxed">{active.summary}</p>
                  )}
                  <div className="flex flex-wrap gap-2 mt-2">
                    <Badge variant="secondary">{active.sections.length} sections</Badge>
                    <Badge variant="outline">{new Date(active.created_at).toLocaleString()}</Badge>
                  </div>

                  {/* Report actions (Phase 19) */}
                  <div className="flex flex-wrap items-center gap-2 mt-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRegenerate}
                      disabled={regenerating}
                    >
                      <RefreshCw className={`w-4 h-4 mr-1 ${regenerating ? "animate-spin" : ""}`} />
                      {regenerating ? "Regenerating…" : "Regenerate"}
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleExportPdf}>
                      <Download className="w-4 h-4 mr-1" />
                      Export PDF
                    </Button>
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <CalendarClock className="w-4 h-4" />
                      <select
                        value={schedule?.frequency ?? "off"}
                        disabled={scheduling}
                        onChange={(e) =>
                          handleSchedule(e.target.value as ReportSchedule["frequency"] | "off")
                        }
                        className="px-2 py-1 border border-gray-300 rounded-lg text-xs bg-white focus:outline-none focus:ring-2 focus:ring-brand-600"
                      >
                        <option value="off">No schedule</option>
                        <option value="hourly">Hourly</option>
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                      </select>
                      {schedule && (
                        <span className="text-[10px] text-gray-400">
                          next run {new Date(schedule.next_run_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {active.warnings.length > 0 && (
                  <Alert variant="warning" title="Some sections were skipped">
                    {active.warnings.map((w, i) => (
                      <div key={i}>{w}</div>
                    ))}
                  </Alert>
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
                    {s.narrative && <MarkdownText>{s.narrative}</MarkdownText>}
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
