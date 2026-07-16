import { Database, FileSearch, BarChart3, Microscope, ChevronLeft, ChevronRight, Plus, Link2, MessageSquare, Clock, Save, AlertCircle, Trash2 } from 'lucide-react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { ConversationSkeleton } from './LoadingSpinner';

interface SidebarProps {
  selectedDataset: string | null;
  onSelectDataset: (dataset: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  conversations: Array<{
    id: string;
    title: string;
    timestamp: Date;
    messageCount?: number;
    hasUnsavedChanges?: boolean;
  }>;
  currentConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onNewConversation: (conversation: { id: string; title: string; timestamp: Date }) => void;
  isLoading?: boolean;
  /** Delete a single conversation. */
  onDeleteConversation?: (conversationId: string) => void;
  /** Delete every conversation (clean slate). */
  onClearConversations?: () => void;
}

const datasets = [
  {
    id: 'geo',
    name: 'GEO',
    description: 'Gene Expression Omnibus',
    icon: Database,
    recordCount: '5M+ samples'
  },
  {
    id: 'sra',
    name: 'SRA',
    description: 'Sequence Read Archive',
    icon: FileSearch,
    recordCount: '15M+ runs'
  },
  {
    id: 'arrayexpress',
    name: 'ArrayExpress',
    description: 'EMBL-EBI RNA-Seq data',
    icon: BarChart3,
    recordCount: '130K+ studies'
  },
  {
    id: 'tcga',
    name: 'TCGA',
    description: 'Cancer Genome Atlas',
    icon: Microscope,
    recordCount: '11K+ patients'
  }
];

const capabilities = [
  'Dataset Search',
  'Differential Expression',
  'Quality Control Metrics',
  'Sample Comparison',
  'Pathway Analysis',
  'Gene Set Enrichment'
];

export function Sidebar({ selectedDataset, onSelectDataset, isCollapsed, onToggleCollapse, conversations, currentConversationId, onSelectConversation, onNewConversation, isLoading = false, onDeleteConversation, onClearConversations }: SidebarProps) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [dataSourceName, setDataSourceName] = useState('');
  const [connectionString, setConnectionString] = useState('');
  const [apiKey, setApiKey] = useState('');

  const handleConnectData = () => {
    // Handle custom data connection logic here
    console.log('Connecting custom data source:', { dataSourceName, connectionString, apiKey });
    setIsDialogOpen(false);
    // Reset form
    setDataSourceName('');
    setConnectionString('');
    setApiKey('');
  };

  const getTimeAgo = (timestamp: Date): string => {
    const now = new Date();
    const diff = now.getTime() - timestamp.getTime();
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
      return `${days} day${days > 1 ? 's' : ''} ago`;
    } else if (hours > 0) {
      return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    } else if (minutes > 0) {
      return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    } else {
      return `${seconds} second${seconds > 1 ? 's' : ''} ago`;
    }
  };

  return (
    <aside className={`h-screen bg-sidebar border-r border-border flex flex-col transition-all duration-500 ease-out ${
      isCollapsed ? 'w-16' : 'w-80'
    }`}>
      {/* Header with Toggle Button */}
      <div className="p-4 border-b border-border flex items-center justify-between bg-sidebar">
        {!isCollapsed && (
          <div>
            <h2 className="text-foreground mb-1">Conversation History</h2>
            <p className="text-muted-foreground text-sm">Your recent conversations</p>
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleCollapse}
          className={`${isCollapsed ? 'w-full' : ''} flex-shrink-0 hover:bg-accent text-muted-foreground`}
        >
          {isCollapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
        </Button>
      </div>

      {!isCollapsed && (
        <>
          <div className="flex-1 overflow-auto p-4 space-y-3 bg-sidebar">
            {/* New Chat Button — bordered with green label (emit, not fill) so the
                one filled-green CTA per screen stays the focal point */}
            <Button
              variant="outline"
              className="w-full text-signal hover:text-signal"
              onClick={() => {
                // Create new conversation
                const newConversationId = `conv-${Date.now()}`;
                const newConversation = {
                  id: newConversationId,
                  title: 'New conversation',
                  timestamp: new Date()
                };
                onSelectConversation(newConversationId);
                onNewConversation(newConversation);
              }}
            >
              <Plus className="w-4 h-4 mr-2" />
              New Chat
            </Button>

            {conversations.length > 0 && onClearConversations && (
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-muted-foreground hover:bg-accent hover:text-destructive"
                onClick={() => {
                  if (window.confirm(`Delete all ${conversations.length} conversation(s)? This cannot be undone.`)) {
                    onClearConversations();
                  }
                }}
              >
                <Trash2 className="w-3.5 h-3.5 mr-2" />
                Clear all
              </Button>
            )}

            {/* Conversation List */}
            {isLoading ? (
              <ConversationSkeleton />
            ) : conversations.length === 0 ? (
              <Card className="p-4 border border-border bg-card elev">
                <p className="text-muted-foreground text-sm text-center">No conversations yet</p>
              </Card>
            ) : (
              conversations.map((conversation) => {
                const timeAgo = getTimeAgo(conversation.timestamp);
                const isActive = currentConversationId === conversation.id;

                return (
                  <Card
                    key={conversation.id}
                    className={`group p-4 pl-5 cursor-pointer border elev transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 ${
                      isActive
                        ? 'trace-band border-border-strong bg-accent'
                        : 'border-border hover:border-border-strong bg-card'
                    }`}
                    onClick={() => onSelectConversation(conversation.id)}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg transition-colors duration-150 ${
                        isActive
                          ? 'bg-signal'
                          : 'bg-surface-2'
                      }`}>
                        <MessageSquare className={`w-5 h-5 transition-colors ${
                          isActive ? 'text-primary-foreground' : 'text-muted-foreground'
                        }`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="text-foreground truncate flex-1">{conversation.title}</h3>
                          {conversation.hasUnsavedChanges && (
                            <Save className="w-3 h-3 text-positive flex-shrink-0" title="Unsaved changes" />
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-muted-foreground text-xs font-mono">
                          <Clock className="w-3 h-3" />
                          <span>{timeAgo}</span>
                          {conversation.messageCount !== undefined && conversation.messageCount > 0 && (
                            <>
                              <span>•</span>
                              <span>{conversation.messageCount} {conversation.messageCount === 1 ? 'message' : 'messages'}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); onDeleteConversation?.(conversation.id); }}
                        aria-label={`Delete conversation: ${conversation.title}`}
                        title="Delete conversation"
                        className="flex-shrink-0 rounded p-1 text-muted-foreground/70 opacity-0 transition hover:text-destructive group-hover:opacity-100"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </Card>
                );
              })
            )}
          </div>
        </>
      )}

      {isCollapsed && (
        <div className="flex-1 overflow-auto p-2 space-y-2 bg-sidebar">
          {conversations.map((conversation) => {
            return (
              <Button
                key={conversation.id}
                variant={currentConversationId === conversation.id ? "default" : "ghost"}
                size="sm"
                onClick={() => onSelectConversation(conversation.id)}
                className={`w-full p-2 transition-colors duration-150 ${
                  currentConversationId === conversation.id ? 'glow-signal' : 'text-muted-foreground hover:bg-accent'
                }`}
                title={conversation.title}
              >
                <MessageSquare className="w-5 h-5" />
              </Button>
            );
          })}
        </div>
      )}
    </aside>
  );
}