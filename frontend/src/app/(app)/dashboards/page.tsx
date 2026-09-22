"use client";

import { DashboardsView } from "@/components/dashboards/dashboards-view";

// Client view reads useSearchParams (deep-linked selection); the route is
// auth-gated with no static value, so skip prerendering.
export const dynamic = "force-dynamic";

export default function DashboardsPage() {
  return <DashboardsView />;
}
