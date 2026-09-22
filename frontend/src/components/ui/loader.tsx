import { cn } from "@/lib/shadcn";

const DOT = { sm: "w-2 h-2", md: "w-3 h-3", lg: "w-4 h-4" } as const;

export function Loader({
  size = "md",
  fullScreen = false,
  label,
  className,
}: {
  size?: keyof typeof DOT;
  fullScreen?: boolean;
  label?: string;
  className?: string;
}) {
  const dots = (
    <div className="flex items-center justify-center space-x-2" role="status" aria-label={label ?? "Loading"}>
      {[0, 75, 150].map((delay) => (
        <div
          key={delay}
          className={cn(DOT[size], "bg-brand-600 rounded-full animate-bounce")}
          style={delay ? { animationDelay: `${delay}ms` } : undefined}
        />
      ))}
      {label && <span className="ml-2 text-sm text-text-muted">{label}</span>}
    </div>
  );
  if (fullScreen) {
    return <div className={cn("flex items-center justify-center h-screen", className)}>{dots}</div>;
  }
  return <div className={cn("flex items-center justify-center py-16", className)}>{dots}</div>;
}
