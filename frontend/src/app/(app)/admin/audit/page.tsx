"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { listAdminAudit, type AdminAuditEntry } from "@/lib/api-client";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { ScrollText } from "lucide-react";

const PAGE_SIZE = 50;

function actionVariant(action: string): "default" | "secondary" | "warning" | "destructive" {
  if (action.includes("decommission") || action.includes("revoke")) return "destructive";
  if (action.includes("suspend") || action.includes("update")) return "warning";
  if (action.includes("grant") || action.includes("provision")) return "default";
  return "secondary";
}

export default function AdminAuditPage() {
  const [entries, setEntries] = useState<AdminAuditEntry[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actorFilter, setActorFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  const load = useCallback(async () => {
    try {
      setEntries(await listAdminAudit(PAGE_SIZE));
    } catch {
      setError("Failed to load the audit feed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    const actor = actorFilter.trim().toLowerCase();
    const type = typeFilter.trim().toLowerCase();
    return entries.filter(
      (e) =>
        (!actor || e.actor_user_id.toLowerCase().includes(actor)) &&
        (!type ||
          e.action.toLowerCase().includes(type) ||
          e.target_type.toLowerCase().includes(type)),
    );
  }, [entries, actorFilter, typeFilter]);

  return (
    <div className="flex h-full flex-col bg-gray-50">
      <PageHeader
        icon={ScrollText}
        title="Admin audit log"
        description="Every control-plane mutation, newest first. History is append-only and outlives tenants."
      />
      <PageContainer>
        <div className="space-y-6">
          {error && <Alert>{error}</Alert>}

          <div className="flex gap-2">
            <Input
              className="max-w-xs"
              placeholder="Filter by actor id…"
              value={actorFilter}
              onChange={(e) => setActorFilter(e.target.value)}
            />
            <Input
              className="max-w-xs"
              placeholder="Filter by action / target…"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            />
          </div>

          <DataTable<AdminAuditEntry>
            keyField={(e) => `${e.created_at}:${e.action}:${e.target_id ?? ""}`}
            rows={filtered}
            loading={loading}
            emptyText="No matching audit entries."
            columns={[
              {
                key: "action",
                header: "Action",
                render: (e) => <Badge variant={actionVariant(e.action)}>{e.action}</Badge>,
              },
              {
                key: "target",
                header: "Target",
                className: "text-xs text-gray-600",
                render: (e) => (
                  <>
                    {e.target_type}
                    {e.target_id && (
                      <div className="font-mono text-[10px] text-gray-400">
                        {e.target_id.slice(0, 13)}…
                      </div>
                    )}
                  </>
                ),
              },
              {
                key: "detail",
                header: "Detail",
                className: "text-[11px] text-gray-500 font-mono max-w-[220px] truncate",
                render: (e) => (e.detail ? JSON.stringify(e.detail) : "—"),
              },
              {
                key: "actor",
                header: "Actor",
                className: "text-[11px] text-gray-400 font-mono",
                render: (e) => `${e.actor_user_id.slice(0, 8)}…`,
              },
              {
                key: "created_at",
                header: "When",
                className: "text-xs text-gray-400 whitespace-nowrap",
                render: (e) => new Date(e.created_at).toLocaleString(),
              },
            ]}
          />
        </div>
      </PageContainer>
    </div>
  );
}
