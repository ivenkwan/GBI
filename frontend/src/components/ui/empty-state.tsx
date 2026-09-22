import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/shadcn";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  variant = "centered",
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  variant?: "card" | "inline" | "centered";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 text-center",
        variant === "card" && "rounded-xl border border-gray-200 bg-white px-6 py-12",
        variant === "inline" && "py-6",
        variant === "centered" && "py-16",
        className,
      )}
    >
      {Icon && (
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 text-brand-600">
          <Icon className="h-6 w-6" />
        </div>
      )}
      <p className="text-sm font-medium text-gray-900">{title}</p>
      {description && <div className="max-w-sm text-sm text-text-muted">{description}</div>}
      {action}
    </div>
  );
}
