"use client";

import { ReportsView } from "@/components/reports/reports-view";

// Client view reads useSearchParams (deep-linked selection); the route is
// auth-gated with no static value, so skip prerendering.
export const dynamic = "force-dynamic";

export default function ReportsPage() {
  return <ReportsView />;
}
