"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/shadcn";
import { Loader } from "@/components/ui/loader";

export interface Column<T> {
  key: string;
  header: ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
  render?: (row: T) => ReactNode;
}

export function DataTable<T extends object>({
  columns,
  rows,
  keyField,
  emptyText = "No rows.",
  loading = false,
}: {
  columns: Column<T>[];
  rows: T[];
  keyField: keyof T | ((row: T) => string);
  emptyText?: string;
  loading?: boolean;
}) {
  const keyOf = (row: T, i: number) =>
    typeof keyField === "function"
      ? keyField(row)
      : String((row as Record<string, unknown>)[keyField as string] ?? i);
  if (loading) return <Loader />;
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50 text-left">
            {columns.map((c) => (
              <th
                key={c.key}
                className={cn(
                  "px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-gray-500",
                  c.align === "right" && "text-right",
                  c.align === "center" && "text-center",
                )}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-text-muted">
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={keyOf(row, i)} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={cn(
                      "px-4 py-2.5 align-top",
                      c.align === "right" && "text-right",
                      c.align === "center" && "text-center",
                      c.className,
                    )}
                  >
                    {c.render ? c.render(row) : ((row as Record<string, unknown>)[c.key] as ReactNode)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
