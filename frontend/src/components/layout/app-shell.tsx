"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import {
  BarChart3,
  BookOpen,
  Database,
  FileText,
  LayoutDashboard,
  Menu,
  MessageSquare,
  MoreVertical,
  Settings,
  Shield,
  X,
} from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * AppShell — the persistent workspace layout (Phase 27b).
 *
 * A dark navigation sidebar with the brand, sectioned nav, and a user card,
 * replacing the per-view top navbars (each page used to carry its own
 * copy-pasted header with a subset of links). Route-grouped under
 * `app/(app)/` so every workspace page shares it; the admin portal keeps
 * its own layout (different audience, different guard).
 */

const WORKSPACE_NAV = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/explore", label: "Explore", icon: Database },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/dashboards", label: "Dashboards", icon: LayoutDashboard },
  { href: "/wiki", label: "Wiki", icon: BookOpen },
];

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();

  const item = ({ href, label, icon: Icon }: (typeof WORKSPACE_NAV)[number]) => {
    const active = isActive(pathname, href);
    return (
      <Link
        key={href}
        href={href}
        onClick={onNavigate}
        className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
          active
            ? "bg-brand-600 text-white shadow-sm"
            : "text-slate-300 hover:bg-white/10 hover:text-white"
        }`}
      >
        <Icon className="h-4 w-4 shrink-0" />
        {label}
      </Link>
    );
  };

  return (
    <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
      <div className="space-y-1">
        <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
          Workspace
        </p>
        {WORKSPACE_NAV.map(item)}
      </div>
      <div className="space-y-1">
        <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
          Account
        </p>
        {item({ href: "/settings", label: "Settings", icon: Settings })}
        {user?.platform_admin &&
          item({ href: "/admin", label: "Admin portal", icon: Shield })}
      </div>
    </nav>
  );
}

function UserCard({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const name = user?.name ?? "User";
  const email = user?.email ?? "";
  const initials = name
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return (
    <div className="border-t border-white/10 p-3">
      <div className="flex items-center gap-3 rounded-lg px-2 py-2">
        <Avatar className="h-9 w-9">
          <AvatarFallback className="bg-brand-600 text-sm font-semibold text-white">
            {initials || "U"}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white">{name}</p>
          <p className="truncate text-xs text-slate-400">{email}</p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              aria-label="User menu"
              className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            >
              <MoreVertical className="h-4 w-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="bg-slate-800 border-white/10 text-slate-200"
          >
            <DropdownMenuItem asChild className="focus:bg-white/10 focus:text-white">
              <Link href="/settings" onClick={onNavigate}>
                Settings
              </Link>
            </DropdownMenuItem>
            <Separator className="my-1 bg-white/10" />
            <DropdownMenuItem
              className="focus:bg-white/10 focus:text-white"
              onClick={() => {
                onNavigate?.();
                logout();
              }}
            >
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  // Close the drawer on navigation.
  const closeDrawer = () => setMobileOpen(false);

  return (
    <TooltipProvider>
      <div className="flex h-screen bg-gray-50">
        {/* Desktop sidebar */}
        <aside className="hidden w-64 shrink-0 flex-col bg-slate-900 lg:flex">
          <div className="flex h-16 items-center gap-2.5 border-b border-white/10 px-5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
              <BarChart3 className="h-4.5 w-4.5 text-white" />
            </div>
            <div className="leading-tight">
              <p className="text-sm font-semibold text-white">GenBI</p>
              <p className="text-[10px] uppercase tracking-widest text-slate-500">
                Generative BI
              </p>
            </div>
          </div>
          <SidebarNav />
          <UserCard />
        </aside>

        {/* Mobile drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-slate-900/60"
              onClick={closeDrawer}
              aria-hidden
            />
            <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-slate-900 shadow-xl">
              <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600">
                    <BarChart3 className="h-4.5 w-4.5 text-white" />
                  </div>
                  <p className="text-sm font-semibold text-white">GenBI</p>
                </div>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={closeDrawer}
                      aria-label="Close navigation"
                      className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>Close navigation</TooltipContent>
                </Tooltip>
              </div>
              <SidebarNav onNavigate={closeDrawer} />
              <UserCard onNavigate={closeDrawer} />
            </aside>
          </div>
        )}

        {/* Content column */}
        <div className="flex h-full min-w-0 flex-1 flex-col">
          {/* Mobile top bar */}
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-4 lg:hidden">
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setMobileOpen(true)}
                  aria-label="Open navigation"
                  className="rounded-lg p-2 text-gray-500 hover:bg-gray-100"
                >
                  <Menu className="h-5 w-5" />
                </button>
              </TooltipTrigger>
              <TooltipContent>Open navigation</TooltipContent>
            </Tooltip>
            <span className="text-sm font-semibold text-gray-900">GenBI</span>
            <span className="w-9" aria-hidden />
          </header>

          <main key={pathname} className="min-h-0 flex-1">
            {children}
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
