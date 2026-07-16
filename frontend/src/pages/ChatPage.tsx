import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ChatInterface } from "../components/ChatInterface";
import { ConnectorToolbar } from "../components/ConnectorToolbar";
import { Sidebar } from "../components/Sidebar";
import { useConversations } from "../hooks/useConversations";

/** Build a fresh conversation record from a seed title. */
function makeConversation(title: string) {
  return {
    id: `conv-${Date.now()}`,
    title: title.slice(0, 50) + (title.length > 50 ? "…" : ""),
    timestamp: new Date(),
  };
}

/**
 * Conversational dataset discovery. The conversation list + dataset connectors
 * live in a page-level Sidebar; the global nav rail sits to its left.
 * `/chat/:conversationId` deep-links a saved conversation.
 */
export function ChatPage() {
  const { conversationId: routeConversationId } = useParams();
  const navigate = useNavigate();
  const {
    conversations,
    currentConversationId,
    conversationMessages,
    selectConversation,
    newConversation,
    updateMessages,
    deleteConversation,
    clearConversations,
  } = useConversations();

  const [selectedDataset, setSelectedDataset] = useState<string | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [selectedConnector, setSelectedConnector] = useState("geo");

  // Resolve the active conversation: prefer the URL param, else ensure one exists
  // (mirrors the old "entering chat starts a conversation" behavior). Runs once.
  const didInit = useRef(false);
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    if (routeConversationId) {
      selectConversation(routeConversationId);
    } else if (!currentConversationId) {
      newConversation(makeConversation("New conversation"));
    }
  }, [routeConversationId, currentConversationId, selectConversation, newConversation]);

  const initialMessages = currentConversationId
    ? conversationMessages[currentConversationId] ?? []
    : [];

  return (
    <div className="flex h-full">
      <Sidebar
        selectedDataset={selectedDataset}
        onSelectDataset={setSelectedDataset}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed((c) => !c)}
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={selectConversation}
        onNewConversation={newConversation}
        onDeleteConversation={deleteConversation}
        onClearConversations={clearConversations}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <ConnectorToolbar
          selectedConnector={selectedConnector}
          onSelectConnector={setSelectedConnector}
        />
        <div className="min-h-0 flex-1">
          <ChatInterface
            selectedDataset={selectedDataset}
            conversationId={currentConversationId}
            initialMessages={initialMessages}
            onUpdateMessages={updateMessages}
            onOpenHypothesis={(text) => navigate(`/canvas?q=${encodeURIComponent(text)}`)}
          />
        </div>
      </div>
    </div>
  );
}
