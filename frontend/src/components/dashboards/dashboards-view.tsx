"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  createDashboard,
  deleteDashboard,
  getDashboard,
  getReport,
  listDashboards,
  listReports,
  pinSection,
  unpinSection,
  type DashboardDetail,
  type DashboardSummary,
  type Report,
  type ReportSummary,
} from "@/lib/api-client";
import { ChartCard } from "@/components/charts/chart-card";
import type { ChartAssemblyInput } from "@/types/chart";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LayoutDashboard, Pin, PinOff, Plus, Trash2 } from "lucide-react";
import { Loader } from "@/components/ui/loader";
import { MarkdownText } from "@/components/ui/markdown";
import { PageHeader } from "@/components/layout/page-header";

export function DashboardsView() {
  const [dashboards, setDashboards] = useState<DashboardSummary[]>([]);
  const [active, setActive] = useState<DashboardDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Create flow: title + source report + which sections to pin
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [sourceReport, setSourceReport] = useState<Report | null>(null);
  const [selectedSections, setSelectedSections] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);

  const loadDashboards = useCallback(async () => {
    try {
      const res = await listDashboards();
      setDashboards(res.dashboards);
    } catch {
      // Sidebar is best-effort
    }
  }, []);

  useEffect(() => {
    loadDashboards();
  }, [loadDashboards]);

  const openCreate = async () => {
    setError("");
    setNewTitle("");
    setSourceReport(null);
    setSelectedSections([]);
    try {
      const res = await listReports();
      setReports(res.reports);
    } catch {
      setReports([]);
    }
    setCreating(true);
  };

  const pickReport = async (id: string) => {
    setSelectedSections([]);
    try {
      setSourceReport(await getReport(id));
    } catch {
      setSourceReport(null);
    }
  };

  const handleCreate = async () => {
    if (!newTitle.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const dashboard = await createDashboard(newTitle.trim());
      for (const position of selectedSections) {
        await pinSection(dashboard.dashboard_id, sourceReport!.report_id, position);
      }
      setCreating(false);
      setActive(await getDashboard(dashboard.dashboard_id));
      loadDashboards();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create dashboard");
    } finally {
      setBusy(false);
    }
  };

  const handleSelect = async (id: string) => {
    if (busy) return;
    setLoading(true);
    setError("");
    try {
      setActive(await getDashboard(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load dashboard");
    } finally {
      setLoading(false);
    }
  };

  const handleUnpin = async (pinId: string) => {
    if (!active || busy) return;
    setBusy(true);
    try {
      await unpinSection(active.dashboard_id, pinId);
      setActive(await getDashboard(active.dashboard_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not unpin section");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!active || busy) return;
    setBusy(true);
    try {
      await deleteDashboard(active.dashboard_id);
      setActive(null);
      loadDashboards();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete dashboard");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full bg-gray-50">
      {/* Dashboards sidebar */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Dashboards
          </span>
          <button
            onClick={openCreate}
            title="New dashboard"
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {dashboards.length === 0 && (
            <p className="px-4 py-2 text-xs text-gray-400">No dashboards yet</p>
          )}
          {dashboards.map((d) => (
            <button
              key={d.id}
              onClick={() => handleSelect(d.id)}
              className={`w-full text-left px-4 py-2 transition-colors ${
                active?.dashboard_id === d.id
                  ? "bg-brand-50 text-brand-700 border-l-2 border-brand-600"
                  : "text-gray-600 hover:bg-gray-50 border-l-2 border-transparent"
              }`}
            >
              <div className="text-sm truncate">{d.title}</div>
              <div className="text-[11px] text-gray-400">
                {d.section_count} pinned section{d.section_count === 1 ? "" : "s"}
              </div>
            </button>
          ))}
        </div>
      </aside>

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0">
        <PageHeader
          title="Dashboards"
          description="Pinned report sections on one board"
          icon={LayoutDashboard}
          actions={
            <>
              {active && (
                <Button variant="outline" size="sm" onClick={handleDelete} disabled={busy}>
                  <Trash2 className="w-4 h-4 mr-1" />
                  Delete
                </Button>
              )}
              <Link
                href="/reports"
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100"
              >
                Reports
              </Link>
            </>
          }
        />

        <main className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
            {error && <Alert>{error}</Alert>}

            {loading && <Loader />}

            {/* Create panel */}
            {creating && (
              <section className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
                <h2 className="text-sm font-semibold text-gray-900">New dashboard</h2>
                <Input
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder='e.g. "Weekly revenue board"'
                />
                <div className="space-y-1">
                  <label className="text-xs text-gray-500">Pin sections from a report:</label>
                  <select
                    onChange={(e) => e.target.value && pickReport(e.target.value)}
                    value={sourceReport?.report_id ?? ""}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-600"
                  >
                    <option value="">Choose a report…</option>
                    {reports.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.title} ({r.section_count} sections)
                      </option>
                    ))}
                  </select>
                </div>
                {sourceReport && (
                  <div className="space-y-1">
                    {sourceReport.sections.map((s) => (
                      <label
                        key={s.position}
                        className="flex items-center gap-2 text-sm text-gray-700"
                      >
                        <input
                          type="checkbox"
                          checked={selectedSections.includes(s.position)}
                          onChange={(e) =>
                            setSelectedSections((prev) =>
                              e.target.checked
                                ? [...prev, s.position]
                                : prev.filter((p) => p !== s.position),
                            )
                          }
                        />
                        {s.section_title}
                        <span className="text-[11px] text-gray-400">{s.metric_name}</span>
                      </label>
                    ))}
                  </div>
                )}
                <div className="flex gap-2">
                  <Button
                    onClick={handleCreate}
                    disabled={!newTitle.trim() || selectedSections.length === 0 || busy}
                  >
                    <Pin className="w-4 h-4 mr-1" />
                    {busy ? "Creating…" : "Create dashboard"}
                  </Button>
                  <Button variant="outline" onClick={() => setCreating(false)} disabled={busy}>
                    Cancel
                  </Button>
                </div>
              </section>
            )}

            {/* Dashboard display */}
            {active && !loading && !creating && (
              <section className="space-y-6">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">{active.title}</h2>
                  {active.description && (
                    <p className="text-sm text-gray-600 mt-1">{active.description}</p>
                  )}
                  <div className="flex gap-2 mt-2">
                    <Badge variant="secondary">{active.sections.length} pinned</Badge>
                    <Badge variant="outline">
                      updated {new Date(active.updated_at).toLocaleString()}
                    </Badge>
                  </div>
                </div>

                {active.warnings.length > 0 && (
                  <div className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
                    {active.warnings.map((w, i) => (
                      <div key={i}>{w}</div>
                    ))}
                  </div>
                )}

                {active.sections.length === 0 && (
                  <p className="text-sm text-gray-400 py-8 text-center">
                    Nothing pinned yet — create a dashboard from a report&apos;s sections.
                  </p>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {active.sections.map((s) => (
                    <div
                      key={s.pin_id}
                      className="bg-white border border-gray-200 rounded-xl p-4 space-y-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="text-sm font-semibold text-gray-900">
                            {s.section_title}
                          </h3>
                          <p className="text-[11px] text-gray-400">from {s.report_title}</p>
                        </div>
                        <button
                          onClick={() => handleUnpin(s.pin_id)}
                          title="Unpin section"
                          className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-red-500 transition-colors"
                        >
                          <PinOff className="w-4 h-4" />
                        </button>
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
                </div>
              </section>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
