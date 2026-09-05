"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getTenantLLM,
  patchTenantLLMStatus,
  putTenantLLM,
  validateLLMConfig,
  type LLMProviderConfig,
  type LLMUsageRow,
} from "@/lib/api-client";
import { LLMConfigSchema } from "@/lib/validators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Bot } from "lucide-react";

/**
 * Tenant-detail LLM panel (superuser): masked BYOK config, status toggle,
 * spend attribution by day × model from the audit trail, and force-set
 * with live validation (ADR 009 guards + ADR 011 §7).
 */
export function TenantLLMPanel({ tenantId }: { tenantId: string }) {
  const [config, setConfig] = useState<LLMProviderConfig | null>(null);
  const [usage, setUsage] = useState<LLMUsageRow[]>([]);
  const [loadError, setLoadError] = useState("");

  const [provider, setProvider] = useState<"anthropic" | "openai">("openai");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [reasoningModel, setReasoningModel] = useState("o4-mini");
  const [fastModel, setFastModel] = useState("gpt-5-mini");
  const [embeddingModel, setEmbeddingModel] = useState("text-embedding-3-small");

  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const detail = await getTenantLLM(tenantId);
      setConfig(detail.config);
      setUsage(detail.usage);
      if (detail.config.configured) {
        setProvider((detail.config.provider as "anthropic" | "openai") ?? "openai");
        setBaseUrl(detail.config.base_url ?? "");
        setReasoningModel(detail.config.reasoning_model ?? "");
        setFastModel(detail.config.fast_model ?? "");
        setEmbeddingModel(detail.config.embedding_model ?? "");
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load LLM config");
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  const formBody = () => {
    const raw = {
      provider,
      api_key: apiKey.trim(),
      base_url: baseUrl.trim() || undefined,
      reasoning_model: reasoningModel.trim(),
      fast_model: fastModel.trim(),
      embedding_model: embeddingModel.trim() || undefined,
    };
    const parsed = LLMConfigSchema.safeParse(raw);
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Invalid config");
      return null;
    }
    return parsed.data;
  };

  const run = async (label: string, fn: () => Promise<unknown>) => {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      setNotice(label);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  };

  const handleForceSet = () => {
    const body = formBody();
    if (!body) return;
    void run("Tenant config force-set (audited)", async () => {
      await putTenantLLM(tenantId, body);
      setApiKey("");
    });
  };

  const configured = config?.configured === true;
  const totalTokens = usage.reduce((sum, row) => sum + row.input_tokens + row.output_tokens, 0);
  const totalCalls = usage.reduce((sum, row) => sum + row.calls, 0);

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
      <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
        <Bot className="w-4 h-4 text-gray-400" /> LLM provider (BYOK)
      </h2>

      {loadError && <p className="text-xs text-red-600">{loadError}</p>}

      {configured ? (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge variant="secondary">{config?.provider}</Badge>
          <Badge variant={config?.status === "active" ? "success" : "warning"}>
            {config?.status}
          </Badge>
          <span className="text-xs text-gray-500">
            key ••••{config?.key_last4} · v{config?.key_version} ·{" "}
            {config?.reasoning_model} / {config?.fast_model}
            {config?.base_url ? ` · ${config.base_url}` : ""}
          </span>
          <Button
            variant="outline"
            className="h-7 text-xs"
            disabled={busy}
            onClick={() =>
              run(
                config?.status === "active" ? "Disabled — tenant on platform key" : "Re-enabled",
                () =>
                  patchTenantLLMStatus(tenantId, config?.status === "active" ? "disabled" : "active"),
              )
            }
          >
            {config?.status === "active" ? "Disable" : "Enable"}
          </Button>
        </div>
      ) : (
        <p className="text-xs text-gray-500">
          No tenant key — this tenant runs on the platform key.
        </p>
      )}

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
        {usage.length === 0 ? (
          <p className="text-xs text-gray-400">No audited LLM calls in the window.</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-400 border-b border-gray-100">
                <th className="py-1 font-normal">Day</th>
                <th className="py-1 font-normal">Model</th>
                <th className="py-1 font-normal">Source</th>
                <th className="py-1 font-normal text-right">Calls</th>
                <th className="py-1 font-normal text-right">In</th>
                <th className="py-1 font-normal text-right">Out</th>
              </tr>
            </thead>
            <tbody>
              {usage.map((row, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-1 text-gray-500 font-mono">{row.day}</td>
                  <td className="py-1 font-mono text-gray-700">{row.model_name}</td>
                  <td className="py-1">
                    <Badge variant={row.key_source === "tenant" ? "default" : "secondary"}>
                      {row.key_source ?? "—"}
                    </Badge>
                  </td>
                  <td className="py-1 text-right text-gray-700">{row.calls}</td>
                  <td className="py-1 text-right text-gray-500">{row.input_tokens}</td>
                  <td className="py-1 text-right text-gray-500">{row.output_tokens}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Force-set */}
      <details className="border border-gray-100 rounded-lg">
        <summary className="px-3 py-2 text-xs text-gray-600 cursor-pointer select-none">
          Force-set this tenant&apos;s provider config (validated + audited)
        </summary>
        <div className="px-3 pb-3 space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <label className="text-xs text-gray-500 space-y-1">
              <span>Provider</span>
              <select
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white"
                value={provider}
                disabled={busy}
                onChange={(e) => setProvider(e.target.value as "anthropic" | "openai")}
              >
                <option value="openai">OpenAI format</option>
                <option value="anthropic">Anthropic native</option>
              </select>
            </label>
            <label className="text-xs text-gray-500 space-y-1">
              <span>API key</span>
              <Input
                type="password"
                placeholder="sk-…"
                value={apiKey}
                disabled={busy}
                onChange={(e) => setApiKey(e.target.value)}
                autoComplete="off"
              />
            </label>
            <label className="text-xs text-gray-500 space-y-1">
              <span>Reasoning model</span>
              <Input
                value={reasoningModel}
                disabled={busy}
                onChange={(e) => setReasoningModel(e.target.value)}
              />
            </label>
            <label className="text-xs text-gray-500 space-y-1">
              <span>Fast model</span>
              <Input
                value={fastModel}
                disabled={busy}
                onChange={(e) => setFastModel(e.target.value)}
              />
            </label>
            <label className="text-xs text-gray-500 space-y-1">
              <span>Embedding model (OpenAI format only)</span>
              <Input
                value={embeddingModel}
                disabled={busy || provider === "anthropic"}
                onChange={(e) => setEmbeddingModel(e.target.value)}
              />
            </label>
            <label className="text-xs text-gray-500 space-y-1">
              <span>Base URL (gateway, optional)</span>
              <Input
                value={baseUrl}
                disabled={busy || provider === "anthropic"}
                onChange={(e) => setBaseUrl(e.target.value)}
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={busy || apiKey.trim().length < 8}
              onClick={() => {
                const body = formBody();
                if (body) void run("Credentials valid", () => validateLLMConfig(body));
              }}
            >
              Validate
            </Button>
            <Button disabled={busy || apiKey.trim().length < 8} onClick={handleForceSet}>
              Force-set
            </Button>
          </div>
        </div>
      </details>

      {error && <p className="text-xs text-red-600">{error}</p>}
      {notice && <p className="text-xs text-green-700">{notice}</p>}
    </section>
  );
}
