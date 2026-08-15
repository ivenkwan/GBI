"use client";

import { AuthGuard } from "@/components/auth/auth-provider";
import { ReportsView } from "@/components/reports/reports-view";

export default function ReportsPage() {
  return (
    <AuthGuard>
      <ReportsView />
    </AuthGuard>
  );
}
