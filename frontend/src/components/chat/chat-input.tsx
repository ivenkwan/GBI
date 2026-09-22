"use client";

import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ChatInput({
  value,
  onChange,
  onSend,
  onCancel,
  loading,
  error,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onCancel: () => void;
  loading: boolean;
  error?: string | null;
}) {
  return (
    <div className="border-t border-gray-200 bg-white shrink-0">
      <div className="max-w-4xl mx-auto px-4 py-4">
        <div className="flex gap-3">
          <Input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            placeholder="Ask a question about your data..."
            className="flex-1 rounded-xl"
            disabled={loading}
          />
          {loading ? (
            <Button
              onClick={onCancel}
              variant="destructive"
              size="lg"
              className="rounded-xl"
            >
              Cancel
            </Button>
          ) : (
            <Button
              onClick={onSend}
              size="lg"
              className="rounded-xl"
            >
              <Send className="w-4 h-4 mr-1.5" />
              Send
            </Button>
          )}
        </div>
        {error && (
          <p className="mt-2 text-xs text-red-600">{error}</p>
        )}
        <p className="text-[10px] text-gray-400 mt-2 text-center">
          GenBI may produce inaccurate results. Always verify data with source systems.
        </p>
      </div>
    </div>
  );
}
