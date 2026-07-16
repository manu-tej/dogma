import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Network, MessageSquare } from "lucide-react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "../components/ui/command";
import { useHistory } from "../hooks/useHistory";
import { useConversations } from "../hooks/useConversations";
import { ALL_DESTINATIONS } from "./routes";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Quick actions that aren't a 1:1 destination jump. */
const QUICK_ACTIONS = [
  { label: "New canvas", to: "/canvas", icon: Plus },
  { label: "New chat", to: "/chat", icon: Plus },
];

/**
 * ⌘K palette: search and jump to any destination, recent canvas, or conversation,
 * or run a quick action. Recent items are loaded lazily when the palette opens.
 */
export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { graphs, refresh } = useHistory();
  const { conversations } = useConversations();

  useEffect(() => {
    if (open) void refresh();
  }, [open, refresh]);

  const go = (to: string) => {
    onOpenChange(false);
    navigate(to);
  };

  const recentGraphs = [...graphs].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 6);
  const recentChats = [...conversations].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime()).slice(0, 6);

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Search destinations, canvases, and chats…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Go to">
          {ALL_DESTINATIONS.map(({ path, label, description, icon: Icon }) => (
            <CommandItem key={path} value={`${label} ${description}`} onSelect={() => go(path)}>
              <Icon />
              <span>{label}</span>
              <span className="ml-auto truncate text-xs text-muted-foreground">{description}</span>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandGroup heading="Actions">
          {QUICK_ACTIONS.map(({ label, to, icon: Icon }) => (
            <CommandItem key={label} value={label} onSelect={() => go(to)}>
              <Icon />
              <span>{label}</span>
            </CommandItem>
          ))}
        </CommandGroup>
        {recentGraphs.length > 0 && (
          <CommandGroup heading="Recent canvases">
            {recentGraphs.map((g) => (
              <CommandItem key={g.id} value={`canvas ${g.query} ${g.id}`} onSelect={() => go(`/canvas/${g.id}`)}>
                <Network />
                <span className="truncate">{g.query || "Untitled canvas"}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        {recentChats.length > 0 && (
          <CommandGroup heading="Recent chats">
            {recentChats.map((c) => (
              <CommandItem key={c.id} value={`chat ${c.title} ${c.id}`} onSelect={() => go(`/chat/${c.id}`)}>
                <MessageSquare />
                <span className="truncate">{c.title}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
