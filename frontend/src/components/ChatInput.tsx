import { useRef, useState } from 'react';
import { Button } from './ui/button';
import { RichTextInput, type RichTextInputHandle } from './RichTextInput';
import { Send, Sparkles, Filter, Network, ArrowRight } from 'lucide-react';
import { Badge } from './ui/badge';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  hasPreferences?: boolean;
  onApplyPreferences?: () => void;
  preferencesActive?: boolean;
  applicableCount?: number;
  /** When provided, typing reveals a CTA to open the causal canvas with the text. */
  onOpenHypothesis?: (text: string) => void;
}

const exampleQueries = [
  'Find breast cancer RNA-Seq datasets',
  'Search for mouse liver tissue studies',
  'Show me heart disease transcriptomics data'
];

export function ChatInput({
  onSendMessage,
  disabled,
  hasPreferences = false,
  onApplyPreferences,
  preferencesActive = false,
  applicableCount = 0,
  onOpenHypothesis,
}: ChatInputProps) {
  const [input, setInput] = useState('');
  const editorRef = useRef<RichTextInputHandle>(null);

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSendMessage(input.trim());
      setInput('');
      editorRef.current?.clear();
    }
  };

  const handleExampleClick = (query: string) => {
    if (!disabled) {
      onSendMessage(query);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        {/* Use My Usual Filters Button */}
        {hasPreferences && onApplyPreferences && (
          <Badge
            variant="outline"
            className="cursor-pointer bg-accent border-signal/30 text-signal hover:bg-accent hover:border-signal/50 transition-colors duration-150 ease-out"
            onClick={() => !disabled && onApplyPreferences()}
          >
            <Filter className="w-3 h-3 mr-1" />
            Use my usual filters
          </Badge>
        )}

        {exampleQueries.map((query) => (
          <Badge
            key={query}
            variant="outline"
            className="cursor-pointer bg-card border-border text-foreground/90 hover:bg-accent hover:border-border-strong hover:text-signal transition-colors duration-150 ease-out"
            onClick={() => handleExampleClick(query)}
          >
            <Sparkles className="w-3 h-3 mr-1" />
            {query}
          </Badge>
        ))}
      </div>

      {/* Open the causal canvas seeded with what you're typing. */}
      {onOpenHypothesis && input.trim() && (
        <button
          type="button"
          onClick={() => onOpenHypothesis(input.trim())}
          className="group flex w-full items-center justify-between rounded-lg border border-signal/40 bg-accent px-3 py-2 text-sm text-signal transition-colors duration-150 ease-out hover:bg-accent hover:border-signal/60"
        >
          <span className="flex items-center gap-2">
            <Network className="h-4 w-4" />
            Investigate as a hypothesis — open the causal canvas
          </span>
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      )}

      <div className="flex gap-2">
        <div className="flex-1 relative">
          <RichTextInput
            ref={editorRef}
            onChange={setInput}
            onSubmit={handleSend}
            disabled={disabled}
            ariaLabel="Search datasets"
            placeholder="Search for RNA-Seq datasets by tissue, disease, organism, or condition..."
          />
          {preferencesActive && applicableCount > 0 && (
            <div className="absolute bottom-2 right-2 flex items-center gap-1 text-xs text-signal bg-accent px-2 py-1 rounded border border-signal/20">
              <Filter className="w-3 h-3" />
              <span>{applicableCount} preference{applicableCount !== 1 ? 's' : ''} active</span>
            </div>
          )}
        </div>
        <Button
          onClick={handleSend}
          disabled={!input.trim() || disabled}
          size="lg"
          className="px-6 glow-signal"
        >
          <Send className="w-5 h-5" />
        </Button>
      </div>
    </div>
  );
}