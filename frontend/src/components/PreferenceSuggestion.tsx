/**
 * PreferenceSuggestion Component
 *
 * Displays inline suggestion that appears after pattern detection (5+ similar queries).
 * Shows accept/reject buttons with animated slide-in appearance and confidence score.
 */

import { useState } from 'react';
import { Sparkles, X, Check, Info } from 'lucide-react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import type { PreferenceSuggestion as PreferenceSuggestionType } from '@/types/preferences';

interface PreferenceSuggestionProps {
  suggestion: PreferenceSuggestionType;
  onAccept: (suggestion: PreferenceSuggestionType) => void;
  onReject: (suggestion: PreferenceSuggestionType) => void;
  onModify?: (suggestion: PreferenceSuggestionType) => void;
}

export function PreferenceSuggestion({
  suggestion,
  onAccept,
  onReject,
  onModify,
}: PreferenceSuggestionProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isAccepting, setIsAccepting] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);

  const handleAccept = async () => {
    setIsAccepting(true);
    try {
      await onAccept(suggestion);
    } finally {
      setIsAccepting(false);
    }
  };

  const handleReject = async () => {
    setIsRejecting(true);
    try {
      await onReject(suggestion);
    } finally {
      setIsRejecting(false);
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return 'bg-surface-2 text-positive border-border';
    if (score >= 0.6) return 'bg-surface-2 text-signal border-signal/30';
    return 'bg-surface-2 text-muted-foreground border-border';
  };

  const formatPreferenceValue = (value: Record<string, any>) => {
    if (value.preferred && Array.isArray(value.preferred)) {
      return value.preferred.join(', ');
    }
    return JSON.stringify(value);
  };

  const formatPreferenceType = (type: string) => {
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <Card className="elev trace-band border-border-strong animate-in slide-in-from-bottom-4 duration-300">
      <div className="p-4">
        {/* Header */}
        <div className="flex items-start gap-3 mb-3">
          <div className="mt-1">
            <Sparkles className="w-5 h-5 text-signal" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="text-foreground font-semibold text-sm">
                Save as your usual preference?
              </h4>
              <Badge className={`text-xs border ${getConfidenceColor(suggestion.confidenceScore)}`}>
                {Math.round(suggestion.confidenceScore * 100)}% confident
              </Badge>
            </div>
            <p className="text-muted-foreground text-xs">
              Based on {suggestion.basedOnSearches} recent searches
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReject}
            disabled={isRejecting || isAccepting}
            className="h-8 px-2 text-muted-foreground hover:text-foreground/90 hover:bg-accent"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Suggestion Content */}
        <div className="mb-3 p-3 bg-surface-2 rounded-lg border border-border">
          <div className="flex items-start gap-2">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Badge variant="outline" className="text-xs border-signal/30 text-signal">
                  {formatPreferenceType(suggestion.preferenceType)}
                </Badge>
              </div>
              <p className="text-foreground text-sm">
                {formatPreferenceValue(suggestion.preferenceValue)}
              </p>
            </div>
          </div>
        </div>

        {/* Rationale (Expandable) */}
        <div className="mb-3">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground/90 text-xs transition-colors"
          >
            <Info className="w-3 h-3" />
            <span>{isExpanded ? 'Hide' : 'Show'} reasoning</span>
          </button>
          {isExpanded && (
            <div className="mt-2 p-2 bg-card rounded text-foreground/90 text-xs animate-in fade-in duration-200">
              {suggestion.rationale}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button
            onClick={handleAccept}
            disabled={isAccepting || isRejecting}
            size="sm"
            className="flex-1 glow-signal"
          >
            {isAccepting ? (
              <>
                <div className="w-3 h-3 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin mr-2" />
                Saving...
              </>
            ) : (
              <>
                <Check className="w-4 h-4 mr-2" />
                Save Preference
              </>
            )}
          </Button>
          <Button
            onClick={handleReject}
            disabled={isRejecting || isAccepting}
            variant="outline"
            size="sm"
            className="border-border text-foreground/90 hover:bg-accent"
          >
            Not Now
          </Button>
          {onModify && (
            <Button
              onClick={() => onModify(suggestion)}
              disabled={isAccepting || isRejecting}
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground/90"
            >
              Modify
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
