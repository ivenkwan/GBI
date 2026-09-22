"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";

export function FeedbackThumbs({
  feedback,
  disabled,
  onFeedback,
}: {
  feedback?: 1 | -1 | 0;
  disabled?: boolean;
  onFeedback: (score: 1 | -1) => void;
}) {
  return (
    <div className="flex items-center gap-1 pt-1 border-t border-gray-100">
      <button
        onClick={() => onFeedback(1)}
        disabled={disabled}
        title="Helpful"
        className={`p-1.5 rounded-lg transition-colors ${
          feedback === 1
            ? "text-green-600 bg-green-50"
            : "text-gray-400 hover:bg-gray-100"
        }`}
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </button>
      <button
        onClick={() => onFeedback(-1)}
        disabled={disabled}
        title="Not helpful"
        className={`p-1.5 rounded-lg transition-colors ${
          feedback === -1
            ? "text-red-500 bg-red-50"
            : "text-gray-400 hover:bg-gray-100"
        }`}
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </button>
      {feedback !== undefined && feedback !== 0 && (
        <span className="text-[10px] text-gray-400 ml-1">
          Feedback recorded
        </span>
      )}
    </div>
  );
}
