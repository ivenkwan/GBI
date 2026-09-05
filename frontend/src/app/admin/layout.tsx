"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { AuthGuard, PlatformAdminGuard } from "@/components/auth/auth-provider";
import { ArrowLeft, ClipboardList, LayoutDashboard, Shield, Users } from "lucide-react";

const NAV = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard },
  { href: "/admin/tenants", label: "Tenants", icon: Users },
  { href: "/admin/admins", label: "Superusers", icon: Shield },
  { href: "/admin/audit", label: "Audit log", icon: ClipboardList },
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <AuthGuard>
      <PlatformAdminGuard>
        <div className="flex h-screen bg-gray-50">
          <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-gray-200 bg-white">
            <div className="flex items-center gap-2.5 px-4 py-4 border-b border-gray-200">
              <div className="w-8 h-8 rounded-lg bg-gray-900 flex items-center justify-center">
                <Shield className="w-4.5 h-4.5 text-white" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900">Admin portal</p>
                <p className="text-[10px] text-gray-400 uppercase tracking-wide">
                  Platform control plane
                </p>
              </div>
            </div>
            <nav className="flex-1 py-2 space-y-0.5">
              {NAV.map(({ href, label, icon: Icon }) => {
                const active = href === "/admin" ? pathname === href : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`flex items-center gap-2.5 px-4 py-2 text-sm transition-colors ${
                      active
                        ? "bg-gray-100 text-gray-900 font-medium border-l-2 border-gray-900"
                        : "text-gray-600 hover:bg-gray-50 border-l-2 border-transparent"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {label}
                  </Link>
                );
              })}
            </nav>
            <div className="px-4 py-3 border-t border-gray-200">
              <Link
                href="/chat"
                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to GenBI
              </Link>
            </div>
          </aside>
          <main className="flex-1 overflow-y-auto">
            <div className="max-w-5xl mx-auto px-6 py-8">{children}</div>
          </main>
        </div>
      </PlatformAdminGuard>
    </AuthGuard>
  );
}
