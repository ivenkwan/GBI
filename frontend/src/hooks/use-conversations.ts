"use client";

import { useCallback, useEffect, useState } from "react";
import { listConversations, type ConversationSummary } from "@/lib/api-client";

/** Conversation list + active id (Phase 14). Message state lives in use-chat-stream. */
export function useConversations() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await listConversations();
      setConversations(res.conversations);
      setListError(null);
    } catch {
      setListError("Conversations couldn't be loaded.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const selectConversation = useCallback((id: string) => setConversationId(id), []);
  const startNewChat = useCallback(() => setConversationId(null), []);
  const handleServerAssignedId = useCallback((id: string) => setConversationId(id), []);

  return {
    conversations,
    conversationId,
    listError,
    refresh,
    selectConversation,
    startNewChat,
    handleServerAssignedId,
  };
}
