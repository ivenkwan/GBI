"use client";

import { useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { BarChart3, LifeBuoy, Lock, Mail, Sparkles, ShieldCheck, Zap } from "lucide-react";

/** Email/password sign-in form. Calls onSuccess after a successful login. */
export function LoginForm({ onSuccess }: { onSuccess?: () => void }) {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      onSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Brand panel */}
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-slate-900 p-12 lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              "radial-gradient(600px circle at 20% 20%, rgba(76,110,245,0.45), transparent 60%), radial-gradient(500px circle at 80% 80%, rgba(67,211,151,0.25), transparent 60%)",
          }}
          aria-hidden
        />
        <div className="relative flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600">
            <BarChart3 className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-semibold text-white">GenBI</span>
        </div>

        <div className="relative max-w-md space-y-8">
          <div className="space-y-4">
            <h2 className="text-3xl font-semibold leading-tight text-white">
              Ask questions about your data in plain English.
            </h2>
            <p className="text-base leading-relaxed text-slate-400">
              Governed NL → SQL with validated queries, charts, and written
              insights — multi-tenant, explainable, and audit-logged.
            </p>
          </div>
          <ul className="space-y-3.5">
            {[
              { icon: Sparkles, text: "Natural-language analytics with schema grounding" },
              { icon: ShieldCheck, text: "Row-level security on every tenant query" },
              { icon: Zap, text: "Reports, dashboards, and a living knowledge base" },
            ].map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3 text-sm text-slate-300">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white/10">
                  <Icon className="h-3.5 w-3.5 text-brand-200" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-slate-500">
          GenBI — Generative Business Intelligence
        </p>
      </div>

      {/* Form panel */}
      <div className="flex w-full items-center justify-center px-6 lg:w-1/2">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="mb-4 flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600">
                <BarChart3 className="h-5 w-5 text-white" />
              </div>
              <span className="text-lg font-semibold text-gray-900">GenBI</span>
            </div>
          </div>

          <h1 className="text-2xl font-bold text-gray-900">Welcome back</h1>
          <p className="mt-1 text-sm text-gray-500">Sign in to your workspace</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="login-email" className="mb-1 block text-sm font-medium text-gray-700">
                Email
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full rounded-lg border border-gray-300 py-2.5 pl-10 pr-3 text-sm transition-colors focus:border-transparent focus:outline-none focus:ring-2 focus:ring-brand-600"
                  required
                  autoFocus
                />
              </div>
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between">
                <label htmlFor="login-password" className="block text-sm font-medium text-gray-700">
                  Password
                </label>
                <Dialog>
                  <DialogTrigger asChild>
                    <button
                      type="button"
                      className="text-xs font-medium text-brand-600 transition-colors hover:text-brand-700 hover:underline"
                    >
                      Forgot password?
                    </button>
                  </DialogTrigger>
                  <DialogContent className="max-w-md">
                    <DialogHeader>
                      <DialogTitle className="flex items-center gap-2">
                        <LifeBuoy className="h-4 w-4 text-gray-400" />
                        Reset your password
                      </DialogTitle>
                      <DialogDescription className="pt-1 text-left">
                        GenBI accounts are managed by your workspace administrators —
                        there is no email-based self-reset.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-3 text-sm text-gray-600">
                      <div className="rounded-lg border border-gray-100 bg-gray-50 px-4 py-3">
                        <p className="font-medium text-gray-800">Still know your password?</p>
                        <p className="mt-1 text-xs leading-relaxed text-gray-500">
                          Sign in and change it any time under{" "}
                          <span className="font-medium">Settings → Change password</span>.
                        </p>
                      </div>
                      <div className="rounded-lg border border-gray-100 bg-gray-50 px-4 py-3">
                        <p className="font-medium text-gray-800">Locked out?</p>
                        <p className="mt-1 text-xs leading-relaxed text-gray-500">
                          Ask your tenant admin to reset it for you{" "}
                          (<span className="font-medium">Settings → Users → Reset password</span>
                          ), or contact the platform administrator if your tenant admin
                          is unavailable.
                        </p>
                      </div>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-gray-300 py-2.5 pl-10 pr-3 text-sm transition-colors focus:border-transparent focus:outline-none focus:ring-2 focus:ring-brand-600"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <div className="mt-6 rounded-lg border border-dashed border-gray-300 bg-white px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">
              Demo environment
            </p>
            <p className="mt-1 text-xs leading-relaxed text-gray-500">
              <code className="rounded bg-gray-100 px-1 py-0.5">admin@demo-acme.test</code>{" "}
              / <code className="rounded bg-gray-100 px-1 py-0.5">Demo123!</code>
              <br />
              (see <code className="rounded bg-gray-100 px-1 py-0.5">make demo-status</code> for all
              demo logins)
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
