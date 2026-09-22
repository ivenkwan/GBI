"use client";

import { useCallback, useState } from "react";
import { useConversations } from "@/hooks/use-conversations";
import { useChatStream } from "@/hooks/use-chat-stream";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { MessageList } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";

export function ChatView() {
  const {
    conversations,
    conversationId,
    listError,
    refresh,
    selectConversation,
    startNewChat,
    handleServerAssignedId,
  } = useConversations();
  const { messages, loading, send, cancel, loadHistory, reset, setFeedback } =
    useChatStream({
      conversationId,
      onConversationId: handleServerAssignedId,
      onTurnComplete: refresh,
    });
  const [input, setInput] = useState("");

  const handleSelect = useCallback(
    (id: string) => {
      if (loading) return;
      selectConversation(id);
      loadHistory(id);
    },
    [loading, selectConversation, loadHistory],
  );

  const handleNewChat = useCallback(() => {
    if (loading) return;
    startNewChat();
    reset();
    setInput("");
  }, [loading, startNewChat, reset]);

  const handleSend = useCallback(() => {
    send(input);
    setInput("");
  }, [input, send]);

  // Large-query confirm (Phase 13): resend the original query with
  // confirm_large_query set. Task 19 replaces this with stream.confirmLargeQuery().
  const handleConfirm = useCallback(
    (msgId: string) => {
      const idx = messages.findIndex((m) => m.id === msgId);
      if (idx < 0) return;
      const query =
        messages[idx].confirmQuery ??
        (idx > 0 ? messages[idx - 1].content : "");
      if (query) send(query, true);
    },
    [messages, send],
  );

  return (
    <div className="flex h-full bg-gray-50">
      {/* Conversations sidebar (Phase 14) */}
      <ConversationSidebar
        conversations={conversations}
        activeId={conversationId}
        listError={listError}
        onSelect={handleSelect}
        onNewChat={handleNewChat}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <MessageList
          messages={messages}
          loading={loading}
          onSuggestion={(text) => send(text)}
          onFeedback={setFeedback}
          onConfirm={handleConfirm}
        />
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onCancel={cancel}
          loading={loading}
        />
      </div>
    </div>
  );
}
