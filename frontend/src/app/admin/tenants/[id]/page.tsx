"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  decommissionTenant,
  getTenantDetail,
  updateTenantAdmin,
  type TenantDetail,
} from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TenantLLMPanel } from "@/components/admin/tenant-llm-panel";
import { UsersAdmin } from "@/components/settings/users-admin";
import { AlertTriangle, ArrowLeft, RefreshCw, Trash2 } from "lucide-react";

export default function TenantDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  // Rename / settings editors
  const [name, setName] = useState("");
  const [settingsText, setSettingsText] = useState("{}");
  const [settingsError, setSettingsError] = useState("");

  // Decommission flow: requires typing the slug, then Delete, then confirm=force
  const [confirmSlug, setConfirmSlug] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const detail = await getTenantDetail(params.id);
      setTenant(detail);
      setName(detail.name);
      setSettingsText(JSON.stringify(detail.settings ?? {}, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tenant");
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (label: string, fn: () => Promise<unknown>) => {
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

  const saveSettings = () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(settingsText || "{}");
    } catch {
      setSettingsError("Invalid JSON");
      return;
    }
    setSettingsError("");
    void act("Settings saved", () => updateTenantAdmin(params.id, { settings: parsed }));
  };

  if (!tenant && !error) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce" />
      </div>
    );
  }

  if (!tenant) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-red-600">{error}</p>
        <Button variant="outline" onClick={() => router.push("/admin/tenants")}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to tenants
        </Button>
      </div>
    );
  }

  const slugMatches = confirmSlug.trim() === (tenant.slug ?? "");

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link
            href="/admin/tenants"
            className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
          >
            <ArrowLeft className="w-3 h-3" /> Tenants
          </Link>
          <h1 className="text-xl font-semibold text-gray-900 mt-1">{tenant.name}</h1>
          <p className="text-sm text-gray-500 font-mono">
            {tenant.slug} · {tenant.id.slice(0, 8)}…
          </p>
        </div>
        <Badge variant={tenant.status === "active" ? "success" : "warning"}>
          {tenant.status}
        </Badge>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">
          {error}
        </div>
      )}
      {notice && (
        <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-4 py-2">
          {notice}
        </div>
      )}

      {/* Lifecycle actions */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-900">Lifecycle</h2>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            disabled={busy || tenant.status === "suspended"}
            onClick={() =>
              act("Tenant suspended", () =>
                updateTenantAdmin(params.id, { status: "suspended" }),
              )
            }
          >
            Suspend
          </Button>
          <Button
            variant="outline"
            disabled={busy || tenant.status === "active"}
            onClick={() =>
              act("Tenant reactivated", () => updateTenantAdmin(params.id, { status: "active" }))
            }
          >
            <RefreshCw className="w-4 h-4 mr-1" />
            Activate
          </Button>
          <Button
            variant="destructive"
            disabled={busy}
            onClick={() => {
              setConfirmOpen(true);
              setConfirmSlug("");
            }}
          >
            <Trash2 className="w-4 h-4 mr-1" />
            Decommission…
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Input
            className="max-w-xs"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Rename tenant"
          />
          <Button
            variant="outline"
            disabled={busy || !name.trim() || name === tenant.name}
            onClick={() => act("Tenant renamed", () => updateTenantAdmin(params.id, { name }))}
          >
            Rename
          </Button>
        </div>
        <p className="text-xs text-gray-400">
          Suspension takes effect within 60 seconds on every authenticated request
          (cached check). Decommission is destructive and audited.
        </p>
      </section>

      {/* Counters + users */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-900">Counters</h2>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            {Object.entries(tenant.counters).map(([key, value]) => (
              <div key={key} className="flex justify-between border-b border-gray-100 pb-1.5">
                <dt className="text-gray-500">{key.replace(/_/g, " ")}</dt>
                <dd className="font-medium text-gray-900">{value < 0 ? "—" : value}</dd>
              </div>
            ))}
          </dl>
          <p className="text-[11px] text-gray-400">
            Business counters read via the tenant GUC — the admin role itself reads no
            business data (ADR 009 §3).
          </p>
        </section>
      </div>

      {/* User management (Phase 23): superusers administer this tenant's
          users through the ?tenant_id= superuser path. */}
      <UsersAdmin tenantId={tenant.id} currentUserId="none" />

      {/* LLM provider panel (Phase 26): masked config, status toggle,
          spend attribution, force-set. */}
      <TenantLLMPanel tenantId={tenant.id} />

      {/* Settings editor */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-gray-900">Tenant settings (JSON)</h2>
        <textarea
          className="w-full h-32 font-mono text-xs border border-gray-300 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-brand-600"
          value={settingsText}
          onChange={(e) => setSettingsText(e.target.value)}
          spellCheck={false}
        />
        {settingsError && <p className="text-xs text-red-600">{settingsError}</p>}
        <Button variant="outline" disabled={busy} onClick={saveSettings}>
          Save settings (merged)
        </Button>
      </section>

      {/* Recent admin actions */}
      <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-gray-900">Recent admin actions</h2>
        <ul className="space-y-1.5 text-sm max-h-64 overflow-y-auto">
          {tenant.recent_admin_actions.map((a, i) => (
            <li key={i} className="flex items-center justify-between text-xs">
              <span className="font-mono text-gray-600">{a.action}</span>
              <span className="text-gray-400">
                {new Date(a.created_at).toLocaleString()}
              </span>
            </li>
          ))}
          {tenant.recent_admin_actions.length === 0 && (
            <li className="text-gray-400 text-sm">No recorded actions.</li>
          )}
        </ul>
      </section>

      {/* Decommission dialog — typed slug + force */}
      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl border border-red-200 shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="w-5 h-5" />
              <h2 className="text-base font-semibold">Decommission “{tenant.name}”?</h2>
            </div>
            <p className="text-sm text-gray-600">
              This permanently deletes the tenant, its users, conversations, reports,
              dashboards, schedules, and analytics rows. Audit history is retained.
              Users must be gone or force-deleted with them.
            </p>
            <Input
              placeholder={`Type the slug “${tenant.slug}” to confirm`}
              value={confirmSlug}
              onChange={(e) => setConfirmSlug(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setConfirmOpen(false)} disabled={busy}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={busy || !slugMatches}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await decommissionTenant(params.id, true);
                    router.push("/admin/tenants");
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Decommission failed");
                    setConfirmOpen(false);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy ? "Deleting…" : "Delete tenant and its data"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
