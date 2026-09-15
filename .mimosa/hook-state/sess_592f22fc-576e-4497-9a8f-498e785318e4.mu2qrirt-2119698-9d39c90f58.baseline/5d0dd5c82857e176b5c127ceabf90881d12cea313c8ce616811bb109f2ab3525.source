"use client";

import { useCallback, useEffect, useState } from "react";
import {
  grantSuperadmin,
  listSuperadmins,
  revokeSuperadmin,
  type SuperadminGrant,
} from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Shield } from "lucide-react";

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
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Platform superusers</h1>
        <p className="text-sm text-gray-500 mt-1">
          Grants live in <code className="text-xs">platform_admins</code> with full
          history; the JWT claim is re-verified against the table behind a 60-second
          cache.
        </p>
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

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-400">
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Granted</th>
              <th className="px-4 py-3">Revoked</th>
              <th className="px-4 py-3">State</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {grants.map((g) => (
              <tr key={g.user_id} className="border-b border-gray-100">
                <td className="px-4 py-3">
                  <div className="text-gray-900">{g.email ?? "(deleted user)"}</div>
                  <div className="text-[11px] text-gray-400 font-mono">{g.user_id.slice(0, 8)}…</div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {new Date(g.granted_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {g.revoked_at ? new Date(g.revoked_at).toLocaleString() : "—"}
                </td>
                <td className="px-4 py-3">
                  <Badge variant={g.active ? "success" : "secondary"}>
                    {g.active ? "active" : "revoked"}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-right">
                  {g.active && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => handleRevoke(g.user_id)}
                    >
                      Revoke
                    </Button>
                  )}
                </td>
              </tr>
            ))}
            {grants.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  No grants yet — bootstrap the first superuser with
                  <code className="mx-1 text-xs">make admin-create</code>.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
