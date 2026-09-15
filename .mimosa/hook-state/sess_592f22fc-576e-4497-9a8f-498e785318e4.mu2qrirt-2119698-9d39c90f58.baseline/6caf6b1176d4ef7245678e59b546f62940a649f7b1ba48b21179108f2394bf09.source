"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { changePassword, getMe } from "@/lib/api-client";
import { useAuth } from "@/components/auth/auth-provider";
import { LLMProviderSettings } from "@/components/settings/llm-provider";
import { UsersAdmin } from "@/components/settings/users-admin";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowLeft, KeyRound, Settings2, Shield, User } from "lucide-react";

export function SettingsView() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<Awaited<ReturnType<typeof getMe>> | null>(null);
  const [error, setError] = useState("");

  // Change-password form
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwNotice, setPwNotice] = useState("");
  const [pwError, setPwError] = useState("");
  const [pwBusy, setPwBusy] = useState(false);

  const loadProfile = useCallback(async () => {
    try {
      setProfile(await getMe());
    } catch {
      setError("Failed to load profile");
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleChangePassword = async () => {
    if (newPw.length < 8) {
      setPwError("New password must be at least 8 characters");
      return;
    }
    setPwBusy(true);
    setPwError("");
    setPwNotice("");
    try {
      await changePassword(currentPw, newPw);
      setPwNotice("Password changed");
      setCurrentPw("");
      setNewPw("");
    } catch (e) {
      setPwError(e instanceof Error ? e.message : "Change failed");
    } finally {
      setPwBusy(false);
    }
  };

  const isTenantAdmin = (profile?.roles ?? user?.roles ?? []).includes("admin");

  return (
    <div className="flex h-screen bg-gray-50">
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center">
                <Settings2 className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-gray-900">Settings</h1>
                <p className="text-sm text-gray-500">Profile, security, AI provider, and users</p>
              </div>
            </div>
            <Link
              href="/chat"
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to chat
            </Link>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">
              {error}
            </div>
          )}

          {/* Profile */}
          <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <User className="w-4 h-4 text-gray-400" /> Profile
            </h2>
            {profile ? (
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-xs text-gray-400">Email</dt>
                  <dd className="text-gray-800">{profile.email}</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-400">Tenant</dt>
                  <dd className="text-gray-800 font-mono text-xs">{profile.tenant_id}</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-400">Roles</dt>
                  <dd className="flex gap-1 mt-1">
                    {profile.roles.map((r) => (
                      <Badge key={r} variant="secondary">
                        {r}
                      </Badge>
                    ))}
                  </dd>
                </div>
                {profile.platform_admin && (
                  <div>
                    <dt className="text-xs text-gray-400">Platform</dt>
                    <dd className="mt-1">
                      <Badge variant="default">
                        <Shield className="w-3 h-3 mr-1" /> superuser
                      </Badge>
                    </dd>
                  </div>
                )}
              </dl>
            ) : (
              <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce" />
            )}
          </section>

          {/* Change password */}
          <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-gray-400" /> Change password
            </h2>
            <div className="flex flex-col sm:flex-row gap-2">
              <Input
                type="password"
                placeholder="Current password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
              />
              <Input
                type="password"
                placeholder="New password (min 8)"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
              />
              <Button
                onClick={handleChangePassword}
                disabled={pwBusy || !currentPw || newPw.length < 8}
              >
                {pwBusy ? "Changing…" : "Change"}
              </Button>
            </div>
            {pwError && <p className="text-xs text-red-600">{pwError}</p>}
            {pwNotice && <p className="text-xs text-green-700">{pwNotice}</p>}
            <p className="text-[11px] text-gray-400">
              A wrong current password counts toward the login lockout.
            </p>
          </section>

          {/* AI provider / BYOK (admins only, Phase 26) */}
          {isTenantAdmin && <LLMProviderSettings />}

          {/* Tenant users (admins only) */}
          {isTenantAdmin ? (
            profile && (
              <UsersAdmin currentUserId={profile.id} />
            )
          ) : (
            <p className="text-xs text-gray-400 text-center">
              User management requires the tenant admin role.
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
