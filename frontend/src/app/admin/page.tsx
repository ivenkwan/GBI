"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAdminStats, type PlatformStats } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";

function StatCard({
  label,
  value,
  hint,
  href,
}: {
  label: string;
  value: string | number;
  hint?: string;
  href?: string;
}) {
  const inner = (
    <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-1 hover:border-gray-300 transition-colors">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="text-3xl font-light text-gray-900">{value}</p>
      {hint && <p className="text-xs text-gray-400">{hint}</p>}
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

export default function AdminOverviewPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getAdminStats()
      .then(setStats)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load stats"));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Platform overview</h1>
        <p className="text-sm text-gray-500 mt-1">
          Control-plane counters across every tenant (ADR 009).
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      {!stats && !error && (
        <div className="flex items-center justify-center py-16">
          <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce" />
        </div>
      )}

      {stats && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
            <StatCard
              label="Tenants"
              value={stats.tenants_total}
              hint={`${stats.tenants_active} active · ${stats.tenants_suspended} suspended`}
              href="/admin/tenants"
            />
            <StatCard label="Users" value={stats.users_total} hint="across all tenants" />
            <StatCard
              label="LLM calls (24h)"
              value={stats.llm_calls_24h}
              hint="audited invocations"
            />
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900">Platform superusers</h2>
              <Link
                href="/admin/admins"
                className="text-xs text-brand-600 hover:text-brand-700"
              >
                Manage →
              </Link>
            </div>
            <p className="text-sm text-gray-600">
              {stats.platform_admins_active} active grant
              {stats.platform_admins_active === 1 ? "" : "s"} — revocation binds within 60
              seconds via the cached grant check.
            </p>
          </div>

          <div className="flex gap-2">
            <Badge variant="secondary">ADR 009 · control plane</Badge>
            <Badge variant="outline">genbi_admin role</Badge>
            <Badge variant="outline">admin_audit on every mutation</Badge>
          </div>
        </>
      )}
    </div>
  );
}
