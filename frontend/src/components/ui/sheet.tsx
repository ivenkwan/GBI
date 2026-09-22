"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/shadcn";

/**
 * Sheet — a side-anchored panel built on the installed Radix Dialog
 * (focus trap, Escape to close, aria wiring) so no new dependency is
 * introduced. Hosts in-view sidebar lists below their breakpoint.
 */
export function Sheet({
  open,
  onOpenChange,
  side = "left",
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  side?: "left" | "right";
  title?: string;
  children: ReactNode;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-slate-900/60" />
        <DialogPrimitive.Content
          className={cn(
            "fixed inset-y-0 z-50 flex w-72 flex-col bg-white shadow-xl outline-none",
            side === "left" ? "left-0 border-r border-gray-200" : "right-0 border-l border-gray-200",
          )}
        >
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 px-4">
            <DialogPrimitive.Title className="text-sm font-semibold text-gray-900">
              {title ?? "Panel"}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close className="rounded-lg p-2 text-gray-500 hover:bg-gray-100">
              <X className="h-4 w-4" />
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
