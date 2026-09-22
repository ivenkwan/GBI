"use client";

import { useCallback, useEffect, useState } from "react";
import {
  grantSuperadmin,
  listSuperadmins,
  revokeSuperadmin,
  type SuperadminGrant,
} from "@/lib/api-client";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Shield, ShieldCheck } from "lucide-react";

export default function AdminAdminsPage() {
  const [grants, setGrants] = useState<SuperadminGrant[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setGrants(await listSuperadmins());
    } catch {
      setError("Failed to load superusers");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleGrant = async () => {
    if (!email.trim() || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await grantSuperadmin({ email: email.trim() });
      setNotice(`Granted to ${email.trim()} — revocation binds within 60 seconds.`);
      setEmail("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Grant failed");
    } finally {
      setBusy(false);
    }
  };

  const handleRevoke = async (userId: string) => {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await revokeSuperadmin(userId);
      setNotice("Revoked — existing tokens lose power within ~60 seconds.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Revoke failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-gray-50">
      <PageHeader
        icon={ShieldCheck}
        title="Platform superusers"
        description="Grants live in platform_admins with full history; the JWT claim is re-verified against the table behind a 60-second cache."
      />
      <PageContainer>
        <div className="space-y-6">
          {error && <Alert>{error}</Alert>}
          {notice && <Alert variant="success">{notice}</Alert>}

          <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-900">Grant superuser</h2>
            <div className="flex gap-2">
              <Input
                type="email"
                placeholder="user email (must already exist)"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleGrant()}
              />
              <Button onClick={handleGrant} disabled={busy || !email.includes("@")}>
                <Shield className="w-4 h-4 mr-1" />
                Grant
              </Button>
            </div>
            <p className="text-[11px] text-gray-400">
              Registration is not self-service — grants are the only path in (ADR 009 §5).
            </p>
          </section>

          <DataTable<SuperadminGrant>
            keyField="user_id"
            rows={grants}
            emptyText="No grants yet — bootstrap the first superuser with make admin-create."
            columns={[
              {
                key: "user",
                header: "User",
                render: (g) => (
                  <>
                    <div className="text-gray-900">{g.email ?? "(deleted user)"}</div>
                    <div className="text-[11px] text-gray-400 font-mono">{g.user_id.slice(0, 8)}…</div>
                  </>
                ),
              },
              {
                key: "granted_by",
                header: "Granted by",
                className: "text-xs text-gray-500",
                render: (g) => g.granted_by ?? "—",
              },
              {
                key: "granted_at",
                header: "Granted",
                className: "text-xs text-gray-500",
                render: (g) => new Date(g.granted_at).toLocaleString(),
              },
              {
                key: "revoked",
                header: "Revoked",
                render: (g) =>
                  g.revoked_at ? (
                    <div className="space-y-1">
                      <Badge variant="secondary">revoked</Badge>
                      <div className="text-[11px] text-gray-500">{new Date(g.revoked_at).toLocaleString()}</div>
                    </div>
                  ) : (
                    <Badge variant="success">active</Badge>
                  ),
              },
              {
                key: "actions",
                header: "",
                align: "right",
                render: (g) =>
                  g.active && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => handleRevoke(g.user_id)}
                    >
                      Revoke
                    </Button>
                  ),
              },
            ]}
          />
        </div>
      </PageContainer>
    </div>
  );
}
