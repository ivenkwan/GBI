"use client";

import { Button } from "@/components/ui/button";

export function LargeQueryConfirm({
  rowEstimate,
  loading,
  onConfirm,
}: {
  rowEstimate: number | null;
  loading?: boolean;
  onConfirm: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
      <span className="text-xs text-amber-700">
        Estimated to scan{" "}
        {rowEstimate ? `~${rowEstimate.toLocaleString()} rows` : "many rows"}.
        Run anyway?
      </span>
      <Button size="sm" disabled={loading} onClick={onConfirm}>
        Confirm and run
      </Button>
    </div>
  );
}
