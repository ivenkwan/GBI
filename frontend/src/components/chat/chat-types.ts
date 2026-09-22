"use client";

import type { SSEEvent } from "@/lib/validators";

export interface StreamStage {
  stage: string;
  data: SSEEvent;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming: boolean;
  stages: StreamStage[];
  sql?: string;
  chartSpec?: Record<string, unknown>;
  chartSvg?: string;
  chartBase64?: string;
  narrative?: string;
  warnings: string[];
  // Feedback (Phase 20): the pipeline session id lands on the completed
  // message; thumbs up/down POST /chat/feedback with it.
  sessionId?: string;
  feedback?: 1 | -1 | 0;
  // Large-query confirmation (Phase 13): set when the pipeline stops with
  // status "confirmation_required"; the panel offers Confirm and run.
  needsConfirm?: boolean;
  rowEstimate?: number | null;
  streamError?: string;
}

/** Message ids only need in-session uniqueness — but crypto.randomUUID
 *  exists only in secure contexts (HTTPS / localhost), so plain-HTTP LAN
 *  access would otherwise throw and silently kill every send. */
export function newMessageId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `m-${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}-${Math.random()
    .toString(16)
    .slice(2, 8)}`;
}
