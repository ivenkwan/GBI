"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
import { LayoutDashboard, List, Pin, PinOff, Plus, Trash2 } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { Loader } from "@/components/ui/loader";
import { MarkdownText } from "@/components/ui/markdown";
import { PageHeader } from "@/components/layout/page-header";
import { Sheet } from "@/components/ui/sheet";
import { SidebarList } from "@/components/ui/sidebar-list";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useSelectionParam } from "@/hooks/use-selection-param";

function DashboardsSidebarContent({
  dashboards,
  activeId,
  listError,
  onSelect,
  onCreate,
}: {
  dashboards: DashboardSummary[];
  activeId: string | null;
  listError?: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
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
          title="Dashboards"
          items={dashboards.map((d) => ({
            id: d.id,
            label: d.title,
            secondary: `${d.section_count} sections`,
          }))}
          activeKey={activeId}
          onSelect={onSelect}
          onCreate={onCreate}
          createTitle="New dashboard"
          emptyText="No dashboards yet"
        />
      </div>
    </>
  );
}

export function DashboardsView() {
  const [dashboards, setDashboards] = useState<DashboardSummary[]>([]);
  const [active, setActive] = useState<DashboardDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Create flow: title + source report + which sections to pin
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [sourceReport, setSourceReport] = useState<Report | null>(null);
  const [selectedSections, setSelectedSections] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [listOpen, setListOpen] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [unpinTarget, setUnpinTarget] = useState<string | null>(null);
  const [selected, setSelected] = useSelectionParam("dash");
  const activeId = active?.dashboard_id ?? null;

  const loadDashboards = useCallback(async () => {
    try {
      const res = await listDashboards();
      setDashboards(res.dashboards);
      setListError(null);
    } catch {
      setListError("Dashboards couldn't be loaded.");
    }
  }, []);

  useEffect(() => {
    loadDashboards();
  }, [loadDashboards]);

  const openCreate = async () => {
    setListOpen(false);
    setError("");
    setCreateError("");
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
    setCreateError("");
    try {
      const dashboard = await createDashboard(newTitle.trim());
      for (const position of selectedSections) {
        await pinSection(dashboard.dashboard_id, sourceReport!.report_id, position);
      }
      setCreating(false);
      setActive(await getDashboard(dashboard.dashboard_id));
      loadDashboards();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Could not create dashboard");
    } finally {
      setBusy(false);
    }
  };

  const handleSelect = useCallback(
    async (id: string, opts?: { silent?: boolean }) => {
      if (busy) return;
      setListOpen(false);
      setLoading(true);
      if (!opts?.silent) setError("");
      try {
        setActive(await getDashboard(id));
      } catch (e) {
        // A stale deep link falls back to the default view with no error
        // banner; a sidebar click still surfaces the failure.
        if (opts?.silent) setSelected(null);
        else setError(e instanceof Error ? e.message : "Could not load dashboard");
      } finally {
        setLoading(false);
      }
    },
    [busy, setSelected],
  );

  // Param → state: adopt a deep-linked dashboard; invalid ids fall back to
  // the default view silently (no error banner for a stale shared link).
  // Only a param change can trigger this effect — comparing against the
  // latest id ref (not the state value in deps) keeps a click-driven state
  // change from re-firing it, which would ping-pong with the state → param
  // effect.
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  useEffect(() => {
    if (!selected || selected === activeIdRef.current) return;
    handleSelect(selected, { silent: true });
  }, [selected, handleSelect]);

  // State → param: selection changes (click, create, delete) sync the URL.
  useEffect(() => {
    if (selected === activeId) return;
    setSelected(activeId);
  }, [activeId, selected, setSelected]);

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
      setUnpinTarget(null);
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
      setConfirmDelete(false);
    }
  };

  return (
    <div className="flex h-full bg-gray-50">
      {/* Dashboards sidebar */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
        <DashboardsSidebarContent
          dashboards={dashboards}
          activeId={active?.dashboard_id ?? null}
          listError={listError}
          onSelect={handleSelect}
          onCreate={openCreate}
        />
      </aside>

      <Sheet open={listOpen} onOpenChange={setListOpen} title="Dashboards">
        <div className="flex h-full flex-col">
          <DashboardsSidebarContent
            dashboards={dashboards}
            activeId={active?.dashboard_id ?? null}
            listError={listError}
            onSelect={handleSelect}
            onCreate={openCreate}
          />
        </div>
      </Sheet>

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0">
        <PageHeader
          title="Dashboards"
          description="Pinned report sections on one board"
          icon={LayoutDashboard}
          actions={
            <>
              <button
                type="button"
                onClick={() => setListOpen(true)}
                title="Dashboards list"
                className="md:hidden p-2 rounded-lg text-gray-600 transition-colors hover:bg-gray-100"
              >
                <List className="h-4 w-4" />
              </button>
              <Button size="sm" onClick={openCreate}>
                <Plus className="w-4 h-4 mr-1" />
                New dashboard
              </Button>
              {active && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConfirmDelete(true)}
                  disabled={busy}
                >
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

            {/* Dashboard display */}
            {active && !loading && (
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
                  <EmptyState
                    variant="centered"
                    title="Nothing pinned yet"
                    description="Create a dashboard from a report's sections."
                  />
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
                          onClick={() => setUnpinTarget(s.pin_id)}
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

      {/* Create dialog (sidebar "+" and header action share this one) */}
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New dashboard</DialogTitle>
          </DialogHeader>
          <Input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder='e.g. "Weekly revenue board"'
            autoFocus
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
            <div className="space-y-1 max-h-56 overflow-y-auto">
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
          {createError && <Alert>{createError}</Alert>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreating(false)} disabled={busy}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!newTitle.trim() || selectedSections.length === 0 || busy}
            >
              <Pin className="w-4 h-4 mr-1" />
              {busy ? "Creating…" : "Create dashboard"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete dashboard confirm */}
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete "${active?.title ?? ""}"?`}
        description="The dashboard and its pinned sections are removed. The underlying reports are not affected."
        confirmLabel="Delete"
        onConfirm={handleDelete}
        busy={busy}
      />

      {/* Unpin section confirm */}
      <ConfirmDialog
        open={unpinTarget !== null}
        onOpenChange={(o) => {
          if (!o) setUnpinTarget(null);
        }}
        title="Unpin this section?"
        description="It is removed from this dashboard; the source report is unchanged."
        confirmLabel="Unpin"
        onConfirm={() => {
          if (unpinTarget) handleUnpin(unpinTarget);
        }}
        busy={busy}
      />
    </div>
  );
}
