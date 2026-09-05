"use client";

import { AuthGuard } from "@/components/auth/auth-provider";
import { DashboardsView } from "@/components/dashboards/dashboards-view";

export default function DashboardsPage() {
  return (
    <AuthGuard>
      <DashboardsView />
    </AuthGuard>
  );
}
