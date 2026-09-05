"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  listTenantsAdmin,
  provisionTenant,
  type ProvisionResult,
  type TenantSummary,
} from "@/lib/api-client";
import { TenantProvisionSchema } from "@/lib/validators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Copy, Plus } from "lucide-react";

export default function AdminTenantsPage() {
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Provision dialog state
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", admin_email: "", seed: true });
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<ProvisionResult | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await listTenantsAdmin();
      setTenants(res.tenants);
    } catch {
      setError("Failed to load tenants");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleProvision = async () => {
    const parsed = TenantProvisionSchema.safeParse({
      name: form.name,
      slug: form.slug,
      admin_email: form.admin_email,
      seed_sample_data: form.seed,
    });
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? "Invalid input");
      return;
    }
    setBusy(true);
    setFormError("");
    try {
      const result = await provisionTenant(parsed.data);
      setCreated(result);
      setOpen(false);
      setForm({ name: "", slug: "", admin_email: "", seed: true });
      load();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Provisioning failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Tenants</h1>
          <p className="text-sm text-gray-500 mt-1">
            Provision, suspend, and decommission tenant workspaces.
          </p>
        </div>
        <Button
          onClick={() => {
            setCreated(null);
            setOpen(true);
          }}
        >
          <Plus className="w-4 h-4 mr-1" />
          Provision tenant
        </Button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      {created && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 space-y-2">
          <p className="text-sm font-medium text-green-800">
            {created.name} provisioned — initial admin {created.admin_email}
          </p>
          {created.temp_password ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-gray-600">One-time password (shown never again):</span>
              <code className="bg-white border border-green-200 rounded px-2 py-0.5 font-mono">
                {created.temp_password}
              </code>
              <button
                className="p-1 rounded hover:bg-green-100 text-gray-500"
                title="Copy password"
                onClick={() => {
                  navigator.clipboard.writeText(created.temp_password ?? "");
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }}
              >
                <Copy className="w-3.5 h-3.5" />
              </button>
              {copied && <span className="text-xs text-green-700">copied</span>}
            </div>
          ) : (
            <p className="text-xs text-green-700">
              Password was set by you — nothing generated to display.
            </p>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce" />
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-400">
                <th className="px-4 py-3">Tenant</th>
                <th className="px-4 py-3">Slug</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Users</th>
                <th className="px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => (
                <tr key={t.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link href={`/admin/tenants/${t.id}`} className="text-gray-900 hover:text-brand-600 font-medium">
                      {t.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-500 font-mono text-xs">{t.slug ?? "—"}</td>
                  <td className="px-4 py-3">
                    <Badge variant={t.status === "active" ? "success" : "warning"}>
                      {t.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{t.user_count}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {new Date(t.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {tenants.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                    No tenants yet — provision the first one.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-xl w-full max-w-md p-6 space-y-4">
            <h2 className="text-base font-semibold text-gray-900">Provision a new tenant</h2>
            <p className="text-xs text-gray-500">
              Creates the tenant and its initial admin user in one transaction. A one-time
              password is generated and shown once.
            </p>
            <div className="space-y-3">
              <Input
                placeholder="Tenant name (e.g. Acme Corp)"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <Input
                placeholder="Slug (e.g. acme-corp)"
                value={form.slug}
                onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase() })}
              />
              <Input
                placeholder="Initial admin email"
                type="email"
                value={form.admin_email}
                onChange={(e) => setForm({ ...form, admin_email: e.target.value })}
              />
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input
                  type="checkbox"
                  checked={form.seed}
                  onChange={(e) => setForm({ ...form, seed: e.target.checked })}
                />
                Seed sample sales data
              </label>
            </div>
            {formError && <p className="text-xs text-red-600">{formError}</p>}
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setOpen(false)} disabled={busy}>
                Cancel
              </Button>
              <Button onClick={handleProvision} disabled={busy}>
                {busy ? "Provisioning…" : "Provision"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
