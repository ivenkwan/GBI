"use client";

import { Plus } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/shadcn";

export interface SidebarListItem {
  id: string;
  label: string;
  secondary?: ReactNode;
}

/**
 * SidebarList — the shared "label + '+' + selectable rows" block used by
 * chat conversations, reports, and dashboards sidebars. Presentational;
 * views wrap it in an <aside> on desktop and in <Sheet> on mobile.
 */
export function SidebarList({
  title,
  items,
  activeKey,
  onSelect,
  onCreate,
  createTitle,
  emptyText,
}: {
  title: string;
  items: SidebarListItem[];
  activeKey?: string | null;
  onSelect?: (id: string) => void;
  onCreate?: () => void;
  createTitle?: string;
  emptyText?: string;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</p>
        {onCreate && (
          <button
            onClick={onCreate}
            title={createTitle ?? `New ${title.toLowerCase()}`}
            className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-900"
          >
            <Plus className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {items.length === 0 ? (
          <p className="px-3 py-8 text-center text-xs text-text-muted">{emptyText ?? "Nothing here yet"}</p>
        ) : (
          <ul className="space-y-0.5">
            {items.map((item) => {
              const active = item.id === activeKey;
              return (
                <li key={item.id}>
                  <button
                    onClick={() => onSelect?.(item.id)}
                    className={cn(
                      "w-full rounded-lg border-l-2 px-3 py-2 text-left transition-colors",
                      active
                        ? "border-brand-600 bg-brand-50 text-gray-900"
                        : "border-transparent text-gray-700 hover:bg-gray-100",
                    )}
                  >
                    <span className="block truncate text-sm">{item.label}</span>
                    {item.secondary && (
                      <span className="mt-0.5 block truncate text-xs text-text-muted">{item.secondary}</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
