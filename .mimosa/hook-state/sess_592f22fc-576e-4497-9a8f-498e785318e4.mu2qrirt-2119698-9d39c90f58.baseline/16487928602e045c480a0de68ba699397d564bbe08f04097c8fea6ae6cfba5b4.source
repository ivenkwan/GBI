"use client";

import { useCallback, useEffect, useState } from "react";
import {
  deleteLLMConfig,
  getLLMConfig,
  saveLLMConfig,
  setLLMStatus,
  validateLLMConfig,
  type LLMProviderConfig,
} from "@/lib/api-client";
import { LLMConfigSchema } from "@/lib/validators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Bot, ShieldCheck } from "lucide-react";

/**
 * "AI Provider" (BYOK) section of /settings — tenant admins configure the
 * tenant's own LLM key. The key is write-only: saved state shows last4 +
 * version only. Validate pings the provider live; Save validates then
 * persists; Disable is the revert-without-deleting switch; Revert deletes
 * the config entirely (back to the platform key).
 */
export function LLMProviderSettings() {
  const [config, setConfig] = useState<LLMProviderConfig | null>(null);
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
      const cfg = await getLLMConfig();
      setConfig(cfg);
      if (cfg.configured) {
        setProvider((cfg.provider as "anthropic" | "openai") ?? "openai");
        setBaseUrl(cfg.base_url ?? "");
        setReasoningModel(cfg.reasoning_model ?? "");
        setFastModel(cfg.fast_model ?? "");
        setEmbeddingModel(cfg.embedding_model ?? "");
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load AI provider config");
    }
  }, []);

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

  const handleValidate = () => {
    const body = formBody();
    if (!body) return;
    void run("Credentials valid — nothing saved yet", () => validateLLMConfig(body));
  };

  const handleSave = () => {
    const body = formBody();
    if (!body) return;
    void run("Saved — the tenant now runs on your key", async () => {
      await saveLLMConfig(body);
      setApiKey("");
    });
  };

  const configured = config?.configured === true;

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
      <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
        <Bot className="w-4 h-4 text-gray-400" /> AI Provider (bring your own key)
      </h2>

      {loadError && <p className="text-xs text-red-600">{loadError}</p>}

      {/* Current state */}
      {configured ? (
        <div className="border border-gray-100 rounded-lg p-3 space-y-2 text-sm bg-gray-50/60">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{config?.provider}</Badge>
            <Badge variant={config?.status === "active" ? "success" : "warning"}>
              {config?.status}
            </Badge>
            <span className="text-xs text-gray-500">
              key ••••{config?.key_last4} · v{config?.key_version} · updated{" "}
              {config?.updated_at ? new Date(config.updated_at).toLocaleString() : "—"}
            </span>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div>
              <dt className="text-gray-400 inline">reasoning: </dt>
              <dd className="text-gray-700 inline font-mono">{config?.reasoning_model}</dd>
            </div>
            <div>
              <dt className="text-gray-400 inline">fast: </dt>
              <dd className="text-gray-700 inline font-mono">{config?.fast_model}</dd>
            </div>
            {config?.embedding_model && (
              <div>
                <dt className="text-gray-400 inline">embeddings: </dt>
                <dd className="text-gray-700 inline font-mono">{config.embedding_model}</dd>
              </div>
            )}
            {config?.base_url && (
              <div>
                <dt className="text-gray-400 inline">gateway: </dt>
                <dd className="text-gray-700 inline font-mono truncate">{config.base_url}</dd>
              </div>
            )}
          </dl>
          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() =>
                run(
                  config?.status === "active" ? "Disabled — platform key in use" : "Re-enabled",
                  () => setLLMStatus(config?.status === "active" ? "disabled" : "active"),
                )
              }
            >
              {config?.status === "active" ? "Disable" : "Enable"}
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() =>
                run("Reverted to the platform key", () => deleteLLMConfig())
              }
            >
              Revert to platform key
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-xs text-gray-500">
          No tenant key configured — all LLM calls currently run on the platform key.
        </p>
      )}

      {/* Editor */}
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
          <span>API key (re-entered on every save — replace is all-or-nothing)</span>
          <Input
            type="password"
            placeholder={configured ? `current key ends ••••${config?.key_last4}` : "sk-…"}
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
            placeholder="o4-mini"
          />
        </label>
        <label className="text-xs text-gray-500 space-y-1">
          <span>Fast model</span>
          <Input
            value={fastModel}
            disabled={busy}
            onChange={(e) => setFastModel(e.target.value)}
            placeholder="gpt-5-mini"
          />
        </label>
        <label className="text-xs text-gray-500 space-y-1">
          <span>Embedding model (OpenAI format only)</span>
          <Input
            value={embeddingModel}
            disabled={busy || provider === "anthropic"}
            onChange={(e) => setEmbeddingModel(e.target.value)}
            placeholder="text-embedding-3-small"
          />
        </label>
        <label className="text-xs text-gray-500 space-y-1">
          <span>Base URL (OpenAI-compatible gateway, optional)</span>
          <Input
            value={baseUrl}
            disabled={busy || provider === "anthropic"}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://gateway.example.com/v1"
          />
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={busy || apiKey.trim().length < 8} onClick={handleValidate}>
          Validate
        </Button>
        <Button disabled={busy || apiKey.trim().length < 8} onClick={handleSave}>
          {busy ? "Working…" : "Save"}
        </Button>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}
      {notice && <p className="text-xs text-green-700">{notice}</p>}

      <p className="text-[11px] text-gray-400 flex items-start gap-1.5">
        <ShieldCheck className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        The key is validated with a live 1-token ping, encrypted (pgcrypto) before storage,
        and never displayed again or sent to logs. A configured tenant never silently falls
        back to the platform key — a broken key surfaces as an error you can fix here.
      </p>
    </section>
  );
}
