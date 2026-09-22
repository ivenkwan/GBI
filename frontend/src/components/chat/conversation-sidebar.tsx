"use client";

import { Alert } from "@/components/ui/alert";
import { SidebarList } from "@/components/ui/sidebar-list";
import type { ConversationSummary } from "@/lib/api-client";

export function ConversationSidebar({
  conversations,
  activeId,
  listError,
  onSelect,
  onNewChat,
}: {
  conversations: ConversationSummary[];
  activeId: string | null;
  listError?: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
}) {
  return (
    <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
      {listError && (
        <Alert variant="error" className="m-2 text-xs">
          {listError}
        </Alert>
      )}
      <div className="min-h-0 flex-1">
        <SidebarList
          title="Conversations"
          items={conversations.map((c) => ({ id: c.id, label: c.title }))}
          activeKey={activeId}
          onSelect={onSelect}
          onCreate={onNewChat}
          createTitle="New chat"
          emptyText="No conversations yet"
        />
      </div>
    </aside>
  );
}
