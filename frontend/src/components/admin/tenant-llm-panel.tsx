"use client";

import { useCallback, useEffect, useState } from "react";
import { getTenantLLM, type LLMUsageRow } from "@/lib/api-client";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import { LLMProviderForm } from "@/components/llm/llm-provider-form";
import { Bot } from "lucide-react";

/**
 * Tenant-detail LLM panel (superuser): the shared LLMProviderForm in
 * "tenant" mode (force-set, validated + audited — ADR 009 guards + ADR 011
 * §7) above the spend-attribution table (audit trail, day × model grain).
 * The panel keeps its own fetch for the usage rows; the form manages the
 * masked config itself.
 */
export function TenantLLMPanel({ tenantId }: { tenantId: string }) {
  const [usage, setUsage] = useState<LLMUsageRow[]>([]);
  const [loadError, setLoadError] = useState("");

  const loadUsage = useCallback(async () => {
    try {
      const detail = await getTenantLLM(tenantId);
      setUsage(detail.usage);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load LLM config");
    }
  }, [tenantId]);

  useEffect(() => {
    loadUsage();
  }, [loadUsage]);

  const totalTokens = usage.reduce((sum, row) => sum + row.input_tokens + row.output_tokens, 0);
  const totalCalls = usage.reduce((sum, row) => sum + row.calls, 0);

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
      <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
        <Bot className="w-4 h-4 text-gray-400" /> LLM provider (BYOK)
      </h2>

      <LLMProviderForm mode="tenant" tenantId={tenantId} />

      {/* Spend attribution (audit_log, day × model grain) */}
      <div className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
            Spend by model (7 days)
          </h3>
          <span className="text-xs text-gray-400">
            {totalCalls} calls · {totalTokens.toLocaleString()} tokens
          </span>
        </div>
        {loadError && <Alert className="text-xs">{loadError}</Alert>}
        <DataTable<LLMUsageRow>
          keyField={(row) => `${row.day}:${row.model_name}:${row.key_source ?? ""}`}
          rows={usage}
          emptyText="No audited LLM calls in the window."
          columns={[
            {
              key: "day",
              header: "Day",
              className: "text-gray-500 font-mono",
            },
            {
              key: "model_name",
              header: "Model",
              className: "font-mono text-gray-700",
            },
            {
              key: "key_source",
              header: "Source",
              render: (row) => (
                <Badge variant={row.key_source === "tenant" ? "default" : "secondary"}>
                  {row.key_source ?? "—"}
                </Badge>
              ),
            },
            { key: "calls", header: "Calls", align: "right", className: "text-gray-700" },
            { key: "input_tokens", header: "In", align: "right", className: "text-gray-500" },
            { key: "output_tokens", header: "Out", align: "right", className: "text-gray-500" },
          ]}
        />
      </div>
    </section>
  );
}
