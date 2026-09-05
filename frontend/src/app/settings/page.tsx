"use client";

import { AuthGuard } from "@/components/auth/auth-provider";
import { SettingsView } from "@/components/settings/settings-view";

export default function SettingsPage() {
  return (
    <AuthGuard>
      <SettingsView />
    </AuthGuard>
  );
}
