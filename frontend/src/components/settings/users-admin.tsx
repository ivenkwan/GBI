"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createUser,
  deleteUser,
  listUsers,
  resetUserPassword,
  updateUser,
  type TenantUserRow,
} from "@/lib/api-client";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { KeyRound, Plus, Trash2 } from "lucide-react";

/**
 * Tenant user management table (Phase 23). Used by the /settings page
 * (own tenant) and the admin portal's tenant detail (?tenant_id= for
 * superusers). Caller gates rendering on the tenant-admin role.
 */
export function UsersAdmin({
  tenantId,
  currentUserId,
}: {
  tenantId?: string;
  currentUserId: string;
}) {
  const [users, setUsers] = useState<TenantUserRow[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", admin: false });
  const [formError, setFormError] = useState("");
  const [resetTarget, setResetTarget] = useState<TenantUserRow | null>(null);
  const [resetPw, setResetPw] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<TenantUserRow | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await listUsers(tenantId);
      setUsers(res.users);
    } catch {
      setError("Failed to load users");
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

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

  const handleCreate = async () => {
    if (!form.email.includes("@") || form.password.length < 8) {
      setFormError("Valid email and a password of at least 8 characters required");
      return;
    }
    setFormError("");
    await run("User created", async () => {
      await createUser({
        email: form.email,
        password: form.password,
        roles: form.admin ? ["admin", "user"] : ["user"],
      });
      setCreateOpen(false);
      setForm({ email: "", password: "", admin: false });
    });
  };

  const generatePassword = () =>
    Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) =>
      b.toString(36).padStart(2, "0"),
    )
      .join("")
      .slice(0, 16);

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900">Users ({users.length})</h2>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="w-4 h-4 mr-1" />
          Add user
        </Button>
      </div>

      {error && <Alert className="text-xs">{error}</Alert>}
      {notice && <p className="text-xs text-green-700">{notice}</p>}

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-400">
            <th className="py-2">Email</th>
            <th className="py-2">Roles</th>
            <th className="py-2">Status</th>
            <th className="py-2">Last login</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b border-gray-100">
              <td className="py-2.5 text-gray-800">{u.email}</td>
              <td className="py-2.5">
                <select
                  className="text-xs border border-gray-200 rounded px-1.5 py-1 bg-white"
                  value={u.roles.includes("admin") ? "admin" : "user"}
                  disabled={busy || u.id === currentUserId}
                  onChange={(e) =>
                    run("Roles updated", () =>
                      updateUser(
                        u.id,
                        {
                          roles:
                            e.target.value === "admin" ? ["admin", "user"] : ["user"],
                        },
                        tenantId,
                      ),
                    )
                  }
                >
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </td>
              <td className="py-2.5">
                <Badge variant={u.status === "active" ? "success" : "secondary"}>
                  {u.status}
                </Badge>
              </td>
              <td className="py-2.5 text-xs text-gray-400">
                {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}
              </td>
              <td className="py-2.5 text-right space-x-1 whitespace-nowrap">
                <button
                  title={u.status === "active" ? "Disable" : "Enable"}
                  disabled={busy || u.id === currentUserId}
                  className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 disabled:opacity-40"
                  onClick={() =>
                    run(
                      u.status === "active" ? "User disabled" : "User enabled",
                      () =>
                        updateUser(
                          u.id,
                          { status: u.status === "active" ? "disabled" : "active" },
                          tenantId,
                        ),
                    )
                  }
                >
                  {u.status === "active" ? "Disable" : "Enable"}
                </button>
                <button
                  title="Reset password"
                  disabled={busy}
                  className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400"
                  onClick={() => {
                    setResetTarget(u);
                    setResetPw(generatePassword());
                  }}
                >
                  <KeyRound className="w-3.5 h-3.5 inline" />
                </button>
                <button
                  title="Delete user"
                  disabled={busy || u.id === currentUserId}
                  className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 disabled:opacity-40"
                  onClick={() => setDeleteTarget(u)}
                >
                  <Trash2 className="w-3.5 h-3.5 inline" />
                </button>
              </td>
            </tr>
          ))}
          {users.length === 0 && (
            <tr>
              <td colSpan={5} className="py-6 text-center text-gray-400">
                No users.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Create dialog */}
      <ConfirmDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="Add a user"
        confirmLabel="Create"
        confirmVariant="default"
        onConfirm={handleCreate}
        busy={busy}
      >
        <Input
          type="email"
          placeholder="email@tenant.example"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <div className="flex gap-2">
          <Input
            type="text"
            placeholder="initial password (min 8)"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <Button variant="outline" size="sm" onClick={() => setForm({ ...form, password: generatePassword() })}>
            Generate
          </Button>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={form.admin}
            onChange={(e) => setForm({ ...form, admin: e.target.checked })}
          />
          Tenant admin role
        </label>
        {formError && <Alert className="text-xs">{formError}</Alert>}
      </ConfirmDialog>

      {/* Reset-password dialog */}
      <ConfirmDialog
        open={resetTarget !== null}
        onOpenChange={(o) => {
          if (!o) setResetTarget(null);
        }}
        title={`Reset password for ${resetTarget?.email ?? ""}`}
        confirmLabel="Reset"
        confirmVariant="default"
        onConfirm={async () => {
          if (!resetTarget || resetPw.length < 8) return;
          await run("Password reset", () =>
            resetUserPassword(resetTarget.id, resetPw, tenantId),
          );
          setResetTarget(null);
        }}
        busy={busy}
      >
        <div className="flex gap-2">
          <Input value={resetPw} onChange={(e) => setResetPw(e.target.value)} />
          <Button variant="outline" size="sm" onClick={() => setResetPw(generatePassword())}>
            Regenerate
          </Button>
        </div>
        <p className="text-xs text-gray-400">
          Share the new password securely — it is not shown again.
        </p>
      </ConfirmDialog>

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => {
          if (!o) setDeleteTarget(null);
        }}
        title={`Delete ${deleteTarget?.email ?? ""}?`}
        description="Hard delete. Their conversations, reports, and dashboards remain (tenant assets); audit history is retained. The last active admin cannot be deleted."
        confirmLabel="Delete"
        onConfirm={async () => {
          if (!deleteTarget) return;
          await run("User deleted", () => deleteUser(deleteTarget.id, tenantId));
          setDeleteTarget(null);
        }}
        busy={busy}
      />
    </section>
  );
}
