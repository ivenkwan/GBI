import { cva, type VariantProps } from "class-variance-authority";
import { AlertCircle, AlertTriangle, CheckCircle2, X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/shadcn";

const alertVariants = cva("flex items-start gap-2 rounded-lg border px-4 py-2 text-sm", {
  variants: {
    variant: {
      error: "bg-red-50 border-red-200 text-red-700",
      success: "bg-green-50 border-green-200 text-green-700",
      warning: "bg-amber-50 border-amber-200 text-amber-800",
    },
  },
  defaultVariants: { variant: "error" },
});

const ICONS = { error: AlertCircle, success: CheckCircle2, warning: AlertTriangle } as const;

export interface AlertProps extends VariantProps<typeof alertVariants> {
  title?: string;
  children: ReactNode;
  onDismiss?: () => void;
  action?: ReactNode;
  className?: string;
}

export function Alert({ variant = "error", title, children, onDismiss, action, className }: AlertProps) {
  const Icon = ICONS[variant ?? "error"];
  return (
    <div className={cn(alertVariants({ variant }), className)} role="alert">
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        <div className="break-words">{children}</div>
      </div>
      {action}
      {onDismiss && (
        <button onClick={onDismiss} className="shrink-0 rounded p-0.5 hover:bg-black/5" title="Dismiss">
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
