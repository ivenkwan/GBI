"use client";

import { useCallback, useState } from "react";
import { MessageSquare } from "lucide-react";
import { useConversations } from "@/hooks/use-conversations";
import { useChatStream } from "@/hooks/use-chat-stream";
import { ConversationSidebar } from "@/components/chat/conversation-sidebar";
import { MessageList } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";
import { Sheet } from "@/components/ui/sheet";

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
  const {
    messages,
    loading,
    inputError,
    send,
    confirmLargeQuery,
    retry,
    cancel,
    loadHistory,
    reset,
    setFeedback,
  } = useChatStream({
    conversationId,
    onConversationId: handleServerAssignedId,
    onTurnComplete: refresh,
  });
  const [input, setInput] = useState("");
  const [listOpen, setListOpen] = useState(false);

  const handleSelect = useCallback(
    (id: string) => {
      if (loading) return;
      selectConversation(id);
      loadHistory(id);
      setListOpen(false);
    },
    [loading, selectConversation, loadHistory],
  );

  const handleNewChat = useCallback(() => {
    if (loading) return;
    startNewChat();
    reset();
    setInput("");
    setListOpen(false);
  }, [loading, startNewChat, reset]);

  const handleSend = useCallback(() => {
    // Keep the typed text when send rejects it (T21) — the validation hint
    // is useless if the query it refers to has been wiped.
    if (send(input)) setInput("");
  }, [input, send]);

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
        <button
          type="button"
          onClick={() => setListOpen(true)}
          className="flex md:hidden items-center gap-2 border-b border-gray-200 bg-white px-4 py-2 text-sm text-gray-700"
        >
          <MessageSquare className="h-4 w-4" />
          Conversations
        </button>

        <Sheet open={listOpen} onOpenChange={setListOpen} title="Conversations">
          <ConversationSidebar
            conversations={conversations}
            activeId={conversationId}
            listError={listError}
            onSelect={handleSelect}
            onNewChat={handleNewChat}
          />
        </Sheet>

        <MessageList
          messages={messages}
          loading={loading}
          onSuggestion={(text) => setInput(text)}
          onFeedback={setFeedback}
          onConfirm={confirmLargeQuery}
          onRetry={retry}
        />
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onCancel={cancel}
          loading={loading}
          error={inputError}
        />
      </div>
    </div>
  );
}
