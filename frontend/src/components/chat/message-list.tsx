"use client";

import { useEffect, useRef } from "react";
import { BarChart3 } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import type { ChatMessage } from "./chat-types";
import { AssistantMessageCard } from "./assistant-message-card";

export function MessageList({
  messages,
  loading,
  onSuggestion,
  onFeedback,
  onConfirm,
}: {
  messages: ChatMessage[];
  loading: boolean;
  onSuggestion: (text: string) => void;
  onFeedback: (msgId: string, score: 1 | -1) => void;
  onConfirm: (msgId: string) => void;
}) {
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <EmptyState
            icon={BarChart3}
            variant="centered"
            className="mt-32"
            title="Ask anything about your data"
            description="Natural language to SQL, charts, and insights — instantly"
            action={
              <div className="flex gap-2 justify-center mt-6 flex-wrap">
                {[
                  "Show revenue by region",
                  "Monthly active users trend",
                  "Top 10 customers by value",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => {
                      onSuggestion(suggestion);
                    }}
                    className="px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-full text-gray-600 hover:border-brand-300 hover:text-brand-600 transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            }
          />
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div className={`max-w-[85%] ${msg.role === "user" ? "" : "w-full"}`}>
              {/* User bubble */}
              {msg.role === "user" && (
                <div className="bg-brand-600 text-white rounded-2xl rounded-br-md px-5 py-3 shadow-sm">
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                </div>
              )}

              {/* Assistant card */}
              {msg.role === "assistant" && (
                <AssistantMessageCard
                  message={msg}
                  loading={loading}
                  onFeedback={onFeedback}
                  onConfirm={onConfirm}
                />
              )}
            </div>
          </div>
        ))}

        <div ref={chatEndRef} />
      </div>
    </div>
  );
}
