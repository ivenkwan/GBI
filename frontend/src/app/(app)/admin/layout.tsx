"use client";

import type { ReactNode } from "react";
import { PlatformAdminGuard } from "@/components/auth/auth-provider";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <PlatformAdminGuard>{children}</PlatformAdminGuard>;
}
