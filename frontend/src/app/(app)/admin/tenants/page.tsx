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
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DataTable } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Copy, Plus, Building2 } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";

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
    <div className="flex h-full flex-col bg-gray-50">
      <PageHeader
        icon={Building2}
        title="Tenants"
        description="Provision, suspend, and decommission tenant workspaces."
        actions={
          <Button
            onClick={() => {
              setCreated(null);
              setOpen(true);
            }}
          >
            <Plus className="w-4 h-4 mr-1" />
            Provision tenant
          </Button>
        }
      />
      <PageContainer>
        <div className="space-y-6">
          {error && <Alert>{error}</Alert>}

          {created && (
            <Alert variant="success">
              <p className="font-medium">{created.name} provisioned — initial admin {created.admin_email}</p>
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
            </Alert>
          )}

          <DataTable<TenantSummary>
            keyField="id"
            rows={tenants}
            loading={loading}
            emptyText="No tenants yet — provision the first one."
            columns={[
              {
                key: "name",
                header: "Tenant",
                render: (t) => (
                  <Link
                    href={`/admin/tenants/${t.id}`}
                    className="text-gray-900 hover:text-brand-600 font-medium"
                  >
                    {t.name}
                  </Link>
                ),
              },
              {
                key: "slug",
                header: "Slug",
                className: "text-gray-500 font-mono text-xs",
                render: (t) => t.slug ?? "—",
              },
              {
                key: "status",
                header: "Status",
                render: (t) => (
                  <Badge variant={t.status === "active" ? "success" : "warning"}>
                    {t.status}
                  </Badge>
                ),
              },
              { key: "user_count", header: "Users", className: "text-gray-600" },
              {
                key: "created_at",
                header: "Created",
                className: "text-gray-400 text-xs",
                render: (t) => new Date(t.created_at).toLocaleDateString(),
              },
            ]}
          />

          <ConfirmDialog
            open={open}
            onOpenChange={setOpen}
            title="Provision a new tenant"
            description="Creates the tenant and its initial admin user in one transaction. A one-time password is generated and shown once."
            confirmLabel="Provision"
            confirmVariant="default"
            onConfirm={handleProvision}
            busy={busy}
          >
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
          </ConfirmDialog>
        </div>
      </PageContainer>
    </div>
  );
}
