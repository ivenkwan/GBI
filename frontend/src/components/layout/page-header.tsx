"use client";

import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

/**
 * PageHeader — the shared in-page header for workspace views.
 * Icon + title + description on the left, arbitrary actions on the right.
 * Views render it as the first child of their content column.
 */
export function PageHeader({
  title,
  description,
  icon: Icon,
  actions,
}: {
  title: string;
  description?: string;
  icon?: LucideIcon;
  actions?: ReactNode;
}) {
  return (
    <header className="flex shrink-0 items-center justify-between gap-4 border-b border-gray-200 bg-white px-6 py-4">
      <div className="flex min-w-0 items-center gap-3">
        {Icon && (
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <Icon className="h-4.5 w-4.5" />
          </div>
        )}
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold text-gray-900">{title}</h1>
          {description && <p className="truncate text-xs text-gray-500">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}
