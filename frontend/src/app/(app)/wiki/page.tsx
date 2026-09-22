"use client";

import { WikiView } from "@/components/wiki/wiki-view";

// Client view reads useSearchParams (deep-linked selection); the route is
// auth-gated with no static value, so skip prerendering.
export const dynamic = "force-dynamic";

export default function WikiPage() {
  return <WikiView />;
}
