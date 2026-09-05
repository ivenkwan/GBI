"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  listMetrics,
  queryMetrics,
  renderChart,
  type MetricQueryResponse,
  type MetricSummary,
} from "@/lib/api-client";
import { ChartCard, type ChartAssemblyInput } from "@/components/charts/chart-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft, BarChart3, Play } from "lucide-react";

const selectClass =
  "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white " +
  "focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent";

type Granularity = "none" | "day" | "month";

export function ExploreView() {
  const [metrics, setMetrics] = useState<MetricSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [measure, setMeasure] = useState("");
  const [dimension, setDimension] = useState("");
  const [granularity, setGranularity] = useState<Granularity>("none");
  const [limit, setLimit] = useState(50);

  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<MetricQueryResponse | null>(null);
  const [chartSpec, setChartSpec] = useState<ChartAssemblyInput | null>(null);
  const [chartSvg, setChartSvg] = useState<string | undefined>();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await listMetrics();
        if (cancelled) return;
        setMetrics(res.metrics);
        if (res.metrics.length > 0) setMeasure(res.metrics[0].name);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load catalog");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(
    () => metrics.find((m) => m.name === measure) ?? null,
    [metrics, measure],
  );

  // Reset dependent picks when the measure changes.
  useEffect(() => {
    setDimension("");
    setGranularity("none");
  }, [measure]);

  const runQuery = useCallback(async () => {
    if (!selected) return;
    setRunning(true);
    setError("");
    setResult(null);
    setChartSpec(null);
    setChartSvg(undefined);
    try {
      const res = await queryMetrics({
        measures: [selected.name],
        ...(dimension ? { dimensions: [dimension] } : {}),
        ...(granularity !== "none" && selected.time_dimensions.length > 0
          ? {
              time_dimensions: [
                {
                  dimension: selected.time_dimensions[0],
                  granularity,
                },
              ],
            }
          : {}),
        limit,
      });
      setResult(res);

      // Render a bar chart when there is a dimension to slice by.
      const xField = dimension ? dimension.split(".").pop() : granularity !== "none" ? granularity : null;
      const yField = selected.measure_name;
      if (xField && res.data.length > 0 && res.data.length <= 50) {
        const spec: ChartAssemblyInput = {
          chartType: "Bar Chart",
          encodings: { x: { field: xField }, y: { field: yField } },
          baseSize: { width: 600, height: 400 },
          data: { values: res.data },
        };
        setChartSpec(spec);
        try {
          const rendered = await renderChart({ spec, backend: "vegalite", format: "svg" });
          setChartSvg(rendered.svg ?? undefined);
        } catch {
          setChartSvg(undefined); // table still renders; chart is best-effort
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Query failed");
    } finally {
      setRunning(false);
    }
  }, [selected, dimension, granularity, limit]);

  const columns = useMemo(() => {
    if (!result || result.data.length === 0) return [];
    return Object.keys(result.data[0]);
  }, [result]);

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="shrink-0 flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900">Explore</h1>
            <p className="text-[11px] text-gray-500">Semantic layer metrics</p>
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
        <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce" />
            </div>
          ) : (
            <>
              {/* Catalog */}
              <section>
                <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
                  Catalog ({metrics.length} metrics)
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {metrics.map((m) => (
                    <button
                      key={m.name}
                      onClick={() => setMeasure(m.name)}
                      className={`text-left p-3 bg-white border rounded-xl transition-colors ${
                        m.name === measure
                          ? "border-brand-500 ring-1 ring-brand-500"
                          : "border-gray-200 hover:border-brand-300"
                      }`}
                    >
                      <div className="text-sm font-medium text-gray-900 truncate">{m.title}</div>
                      <div className="text-[11px] text-gray-400 truncate">{m.cube_name}</div>
                      <Badge variant="secondary" className="mt-1.5">{m.metric_type}</Badge>
                    </button>
                  ))}
                </div>
              </section>

              {/* Query builder */}
              <section className="bg-white border border-gray-200 rounded-xl p-4">
                <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
                  Query
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Measure</label>
                    <select value={measure} onChange={(e) => setMeasure(e.target.value)} className={selectClass}>
                      {metrics.map((m) => (
                        <option key={m.name} value={m.name}>
                          {m.title} ({m.cube_name})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Group by</label>
                    <select
                      value={dimension}
                      onChange={(e) => setDimension(e.target.value)}
                      className={selectClass}
                      disabled={!selected}
                    >
                      <option value="">— none —</option>
                      {selected?.dimensions.map((d) => (
                        <option key={d} value={d}>
                          {d.split(".").pop()}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Time</label>
                    <select
                      value={granularity}
                      onChange={(e) => setGranularity(e.target.value as Granularity)}
                      className={selectClass}
                      disabled={!selected || selected.time_dimensions.length === 0}
                    >
                      <option value="none">— none —</option>
                      <option value="day">by day</option>
                      <option value="month">by month</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Row limit</label>
                    <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className={selectClass}>
                      {[10, 25, 50, 100].map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-3">
                  <Button onClick={runQuery} disabled={running || !selected}>
                    <Play className="w-4 h-4 mr-1" />
                    {running ? "Running…" : "Run query"}
                  </Button>
                  {result && (
                    <span className="text-xs text-gray-400">
                      {result.data.length} rows · {result.latency_ms} ms
                      {result.cached ? " · cached" : ""}
                    </span>
                  )}
                </div>
              </section>

              {/* Results */}
              {result && result.data.length > 0 && (
                <section className="space-y-4">
                  {chartSpec && (
                    <ChartCard spec={chartSpec} svg={chartSvg} title={selected?.title} />
                  )}
                  <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200">
                          {columns.map((c) => (
                            <th key={c} className="text-left px-4 py-2 text-xs font-medium text-gray-600">
                              {c}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.data.map((row, i) => (
                          <tr key={i} className="border-b border-gray-100 last:border-0">
                            {columns.map((c) => (
                              <td key={c} className="px-4 py-2 text-gray-700">
                                {formatCell(row[c])}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {result && result.data.length === 0 && (
                <div className="bg-white border border-gray-200 rounded-xl px-4 py-8 text-center text-sm text-gray-500">
                  No rows. Under tenant RLS this usually means the tenant has no data
                  for this metric — try seeding (`make seed`).
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(value);
}
