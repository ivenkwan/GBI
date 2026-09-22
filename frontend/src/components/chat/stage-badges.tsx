"use client";

import { Badge } from "@/components/ui/badge";
import type { StreamStage } from "./chat-types";

// Stage badge labels (module scope — was recreated per render in ChatView)
const stageLabels: Record<
  string,
  { label: string; color: "default" | "secondary" | "success" | "warning" }
> = {
  intent: { label: "Intent", color: "secondary" },
  sql: { label: "SQL", color: "secondary" },
  validation: { label: "Validated", color: "success" },
  data: { label: "Results", color: "success" },
  chart: { label: "Chart", color: "secondary" },
  narrative: { label: "Insight", color: "default" },
  done: { label: "Done", color: "success" },
};

export function StageBadges({ stages }: { stages: StreamStage[] }) {
  return (
    <>
      {stages.map((s, i) => {
        const info = stageLabels[s.stage] ?? { label: s.stage, color: "secondary" as const };
        return (
          <Badge key={i} variant={info.color} className="text-[10px]">
            {info.label}
          </Badge>
        );
      })}
    </>
  );
}
