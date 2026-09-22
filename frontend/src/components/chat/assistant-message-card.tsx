"use client";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { MarkdownText } from "@/components/ui/markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { ChartCard } from "@/components/charts/chart-card";
import type { ChartAssemblyInput } from "@/types/chart";
import type { ChatMessage } from "./chat-types";
import { FeedbackThumbs } from "./feedback-thumbs";
import { LargeQueryConfirm } from "./large-query-confirm";
import { SqlBlock } from "./sql-block";
import { StageBadges } from "./stage-badges";

export function AssistantMessageCard({
  message,
  loading,
  onFeedback,
  onConfirm,
}: {
  message: ChatMessage;
  loading: boolean;
  onFeedback: (msgId: string, score: 1 | -1) => void;
  onConfirm: (msgId: string) => void;
}) {
  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        {/* Stage badges */}
        {message.stages.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            <StageBadges stages={message.stages} />
            {message.streaming && (
              <Badge variant="secondary" className="text-[10px] animate-pulse">
                ...
              </Badge>
            )}
          </div>
        )}

        {/* Streaming skeleton */}
        {message.streaming && message.stages.length === 0 && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        )}

        {/* SQL block */}
        {message.sql && <SqlBlock sql={message.sql} />}

        {/* Chart */}
        {(message.chartSvg || message.chartBase64 || message.chartSpec) && (
          <ChartCard
            spec={message.chartSpec as unknown as ChartAssemblyInput}
            svg={message.chartSvg}
            imageBase64={message.chartBase64}
          />
        )}

        {/* Narrative */}
        {message.narrative && !message.streaming && (
          <MarkdownText>{message.narrative}</MarkdownText>
        )}

        {/* Warnings */}
        {message.warnings.length > 0 && !message.streaming && (
          <Alert variant="warning">
            {message.warnings.map((w, i) => (
              <div key={i}>{w}</div>
            ))}
          </Alert>
        )}

        {/* Feedback (Phase 20): thumbs on completed responses */}
        {!message.streaming && message.narrative && (
          <FeedbackThumbs
            feedback={message.feedback}
            disabled={loading}
            onFeedback={(score) => onFeedback(message.id, score)}
          />
        )}

        {/* Large-query confirmation (Phase 13) */}
        {message.needsConfirm && !message.streaming && (
          <LargeQueryConfirm
            rowEstimate={message.rowEstimate ?? null}
            loading={loading}
            onConfirm={() => onConfirm(message.id)}
          />
        )}
      </CardContent>
    </Card>
  );
}
