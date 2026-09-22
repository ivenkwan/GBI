"use client";

import { useCallback, useRef, useState } from "react";
import { listConversationMessages, sendFeedback, streamChat } from "@/lib/api-client";
import { ChatRequestSchema } from "@/lib/validators";
import type { SSEEvent } from "@/lib/validators";
import { newMessageId, type ChatMessage } from "@/components/chat/chat-types";

/** Chat message state + SSE streaming lifecycle, extracted from chat-view.tsx.
 *  Parity extraction: semantics match the pre-refactor ChatView except where
 *  the deliberate flips have landed — confirm reuses the pending turn via
 *  confirmLargeQuery (T19); invalid input rejects silently (T21) is still a
 *  parity quirk; feedback now posts the resulting score and rolls back on
 *  failure (T20). */
export function useChatStream({
  conversationId,
  onConversationId,
  onTurnComplete,
}: {
  conversationId: string | null;
  onConversationId: (id: string) => void;
  onTurnComplete: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const streamingMsgRef = useRef<string | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);
  messagesRef.current = messages;

  const finalize = useCallback(() => {
    setLoading(false);
    abortRef.current = null;
    streamingMsgRef.current = null;
  }, []);

  const updateMessageStage = useCallback(
    (msgId: string, stage: string, data: SSEEvent) => {
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== msgId) return m;

          const updated = { ...m, stages: [...m.stages, { stage, data }] };

          // Update state from each stage
          if (data.sql && stage === "sql") updated.sql = data.sql;
          if (data.validated_sql && stage === "validation") updated.sql = data.validated_sql;
          if (data.chart_spec && stage === "chart") updated.chartSpec = data.chart_spec as Record<string, unknown>;
          if (data.svg && stage === "chart") updated.chartSvg = data.svg;
          if (data.image_base64 && stage === "chart") updated.chartBase64 = data.image_base64;
          if (data.narrative && stage === "narrative") updated.narrative = data.narrative;
          if (data.warnings) updated.warnings = data.warnings;
          if (data.session_id && stage === "start") updated.sessionId = data.session_id;

          if (stage === "done") {
            updated.streaming = false;
            updated.content = data.narrative ?? "Here's what I found.";
            if (data.status === "confirmation_required" && data.requires_confirmation) {
              updated.needsConfirm = true;
              updated.rowEstimate = data.row_estimate ?? null;
              updated.content =
                "This query is estimated to scan a large number of rows. " +
                "Please confirm before it runs.";
            }
          }

          return updated;
        }),
      );
    },
    [],
  );

  const startStream = useCallback(
    (query: string, assistantId: string, confirmLarge: boolean) => {
      setLoading(true);
      abortRef.current = streamChat(
        {
          query,
          confirm_large_query: confirmLarge || undefined,
          conversation_id: conversationId ?? undefined,
        },
        (event: SSEEvent) => {
          updateMessageStage(assistantId, event.event, event);

          // Conversation threading (Phase 14): capture the server-assigned
          // id on start; refresh the sidebar ordering when a turn ends.
          if (event.event === "start" && event.conversation_id) {
            onConversationId(event.conversation_id);
          }
          if (event.event === "done") {
            onTurnComplete();
            finalize();
          }
        },
        () => {
          // Parity for Task 16 (Task 21 replaces this with streamError):
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: "Sorry, something went wrong.", streaming: false }
                : m,
            ),
          );
          finalize();
        },
        () => finalize(), // onClose without done: never leave the spinner running (Review Focus 2)
      );
      streamingMsgRef.current = assistantId;
    },
    [conversationId, onConversationId, onTurnComplete, updateMessageStage, finalize],
  );

  const send = useCallback(
    (query: string) => {
      if (!query.trim() || loading) return;

      // Validate input
      const parsed = ChatRequestSchema.safeParse({ query });
      if (!parsed.success) {
        return; // silently reject invalid input
      }

      const msgId = newMessageId();
      const userMessage: ChatMessage = {
        id: newMessageId(),
        role: "user",
        content: query,
        streaming: false,
        stages: [],
        warnings: [],
      };
      const assistantMessage: ChatMessage = {
        id: msgId,
        role: "assistant",
        content: "",
        streaming: true,
        stages: [],
        warnings: [],
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      startStream(query, msgId, false);
    },
    [loading, startStream],
  );

  // Large-query confirm (T19): reuse the pending turn — reset the same
  // assistant bubble and re-stream the last user query into it with
  // confirm_large_query set, instead of appending a duplicate pair. The reset
  // also wipes sql/chart artifacts the confirmation-required turn may already
  // have streamed in — SqlBlock/ChartCard render unconditionally, so stale
  // artifacts would otherwise stay visible during the confirmed re-stream.
  const confirmLargeQuery = useCallback(() => {
    const pending = [...messagesRef.current].reverse().find((m) => m.role === "assistant" && m.needsConfirm);
    const lastUser = [...messagesRef.current].reverse().find((m) => m.role === "user");
    if (!pending || !lastUser || loading) return;
    setMessages((prev) =>
      prev.map((m) =>
        m.id === pending.id
          ? {
              ...m,
              streaming: true,
              needsConfirm: false,
              content: "",
              stages: [],
              warnings: [],
              streamError: undefined,
              sql: undefined,
              chartSpec: undefined,
              chartSvg: undefined,
              chartBase64: undefined,
              rowEstimate: null,
            }
          : m,
      ),
    );
    startStream(lastUser.content, pending.id, true);
  }, [loading, startStream]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setLoading(false);
    // End the in-flight assistant bubble — otherwise its streaming spinner
    // outlives the cancelled request.
    const msgId = streamingMsgRef.current;
    if (msgId) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId && m.streaming
            ? { ...m, streaming: false, content: m.content || "Cancelled." }
            : m,
        ),
      );
    }
  }, []);

  const loadHistory = useCallback(
    async (id: string) => {
      if (loading) return;
      setMessages([]);
      try {
        const res = await listConversationMessages(id);
        setMessages(
          res.messages.map((m, i) => ({
            id: `${id}-${i}`,
            role: m.role,
            content: m.content,
            streaming: false,
            stages: [],
            warnings: [],
            sql: m.generated_sql ?? undefined,
            narrative: m.role === "assistant" ? m.content : undefined,
          })),
        );
      } catch {
        setMessages([]);
      }
    },
    [loading],
  );

  const reset = useCallback(() => {
    setMessages([]);
  }, []);

  // Feedback (Phase 20): thumbs up/down on a completed response. The score
  // lands on the session's audit rows; failures roll the thumb back.
  const setFeedback = useCallback((msgId: string, score: 1 | -1) => {
    const msg = messagesRef.current.find((m) => m.id === msgId);
    if (!msg?.sessionId) return;
    const next: 1 | -1 | 0 = msg.feedback === score ? 0 : score;
    setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, feedback: next } : m)));
    sendFeedback(msg.sessionId, next).catch(() => {
      setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, feedback: msg.feedback ?? 0 } : m)));
    });
  }, []);

  return { messages, loading, send, confirmLargeQuery, cancel, loadHistory, reset, setFeedback };
}
