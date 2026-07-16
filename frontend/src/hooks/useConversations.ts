import { useEffect, useState } from "react";

/**
 * A chat message. `reasoning` is intentionally loose (`any[]`) because the
 * reasoning-step shape is owned by ChatInterface, which renders it; keeping it
 * loose here lets the persisted record flow into ChatInterface without a type clash.
 */
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  reasoning?: any[];
  analysis?: { type: string; data: any };
}

export interface Conversation {
  id: string;
  title: string;
  timestamp: Date;
}

export type ConversationMessages = { [conversationId: string]: Message[] };

const CONVERSATIONS_KEY = "antonConversations";
const MESSAGES_KEY = "antonMessages";

/**
 * Conversation + message state, persisted to localStorage (keys `antonConversations`
 * / `antonMessages` — kept stable so existing users' saved chats survive). Extracted
 * verbatim from the old App.tsx so the routed ChatPage behaves identically.
 */
export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [conversationMessages, setConversationMessages] = useState<ConversationMessages>({});

  // Load only user-created conversations. Empty state stays empty; Dogma does
  // not seed realistic-looking but unverified scientific search results.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const savedConversations = localStorage.getItem(CONVERSATIONS_KEY);
    const savedMessages = localStorage.getItem(MESSAGES_KEY);

    if (!savedConversations) {
      return;
    }

    try {
      const parsed = JSON.parse(savedConversations);
      const conversationsWithDates: Conversation[] = parsed.map((item: any) => ({
        ...item,
        timestamp: new Date(item.timestamp),
      }));
      setConversations(conversationsWithDates);

      const messagesWithDates: ConversationMessages = {};
      if (savedMessages) {
        const parsedMessages = JSON.parse(savedMessages);
        Object.keys(parsedMessages).forEach((convId) => {
          messagesWithDates[convId] = parsedMessages[convId].map((msg: any) => ({
            ...msg,
            timestamp: new Date(msg.timestamp),
          }));
        });
      }
      setConversationMessages(messagesWithDates);
    } catch (error) {
      console.error("Failed to parse conversations:", error);
    }
  }, []);

  // Persist on change (length-guarded; delete/clear handlers write explicit empties).
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (conversations.length > 0) {
      localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations));
    }
  }, [conversations]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (Object.keys(conversationMessages).length > 0) {
      localStorage.setItem(MESSAGES_KEY, JSON.stringify(conversationMessages));
    }
  }, [conversationMessages]);

  const selectConversation = (conversationId: string) => {
    setCurrentConversationId(conversationId);
  };

  const newConversation = (conversation: Conversation) => {
    setConversations((prev) => [...prev, conversation]);
    setConversationMessages((prev) => ({ ...prev, [conversation.id]: [] }));
    setCurrentConversationId(conversation.id);
  };

  const updateMessages = (conversationId: string, messages: Message[]) => {
    setConversationMessages((prev) => ({ ...prev, [conversationId]: messages }));
  };

  const deleteConversation = (conversationId: string) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== conversationId);
      if (typeof window !== "undefined") localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(next));
      return next;
    });
    setConversationMessages((prev) => {
      const next = { ...prev };
      delete next[conversationId];
      if (typeof window !== "undefined") localStorage.setItem(MESSAGES_KEY, JSON.stringify(next));
      return next;
    });
    if (currentConversationId === conversationId) setCurrentConversationId(null);
  };

  const clearConversations = () => {
    setConversations([]);
    setConversationMessages({});
    setCurrentConversationId(null);
    if (typeof window !== "undefined") {
      localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify([]));
      localStorage.setItem(MESSAGES_KEY, JSON.stringify({}));
    }
  };

  return {
    conversations,
    currentConversationId,
    conversationMessages,
    setCurrentConversationId,
    selectConversation,
    newConversation,
    updateMessages,
    deleteConversation,
    clearConversations,
  };
}
