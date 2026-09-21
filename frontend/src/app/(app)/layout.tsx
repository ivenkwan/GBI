"use client";

import type { ReactNode } from "react";
import { AuthGuard } from "@/components/auth/auth-provider";
import { AppShell } from "@/components/layout/app-shell";

/**
 * Workspace route group (`(app)` — no URL prefix): every authenticated
 * workspace page renders inside the shared AppShell (sidebar nav + user
 * card) behind a single AuthGuard. The pages themselves no longer wrap
 * their own guards or top navbars.
 */
export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}
