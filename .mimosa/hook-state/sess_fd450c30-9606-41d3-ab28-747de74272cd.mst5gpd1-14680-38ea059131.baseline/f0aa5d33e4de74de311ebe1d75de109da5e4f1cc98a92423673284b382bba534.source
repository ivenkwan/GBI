import * as React from "react";
import { cn } from "@/lib/shadcn";
import { cva, type VariantProps } from "class-variance-authority";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "bg-brand-600 text-white",
        secondary: "bg-gray-100 text-gray-800",
        destructive: "bg-red-100 text-red-700",
        outline: "text-gray-600 border border-gray-300",
        success: "bg-green-100 text-green-700",
        warning: "bg-amber-100 text-amber-700",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
