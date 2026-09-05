"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { listAdminAudit, type AdminAuditEntry } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

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
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Admin audit log</h1>
          <p className="text-sm text-gray-500 mt-1">
            Every control-plane mutation, newest first. History is append-only and
            outlives tenants.
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">
          {error}
        </div>
      )}

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

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce" />
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-400">
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Target</th>
                <th className="px-4 py-3">Detail</th>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">When</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e, i) => (
                <tr key={i} className="border-b border-gray-100 align-top">
                  <td className="px-4 py-3">
                    <Badge variant={actionVariant(e.action)}>{e.action}</Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-600">
                    {e.target_type}
                    {e.target_id && (
                      <div className="font-mono text-[10px] text-gray-400">
                        {e.target_id.slice(0, 13)}…
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[11px] text-gray-500 font-mono max-w-[220px] truncate">
                    {e.detail ? JSON.stringify(e.detail) : "—"}
                  </td>
                  <td className="px-4 py-3 text-[11px] text-gray-400 font-mono">
                    {e.actor_user_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                    No matching audit entries.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
