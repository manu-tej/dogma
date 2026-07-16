/**
 * ActivePreferencesBar Component
 *
 * Shows currently applied preferences in search interface with override toggle option.
 * Displays badge/chip UI showing preference count and active filters.
 */

import { useState } from 'react';
import { Filter, X, ChevronDown, ChevronUp } from 'lucide-react';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card } from './ui/card';
import type { PreferenceResponse } from '@/types/preferences';

interface ActivePreferencesBarProps {
  preferences: PreferenceResponse[];
  isEnabled: boolean;
  onToggle: (enabled: boolean) => void;
  onRemovePreference?: (preferenceId: string) => void;
}

export function ActivePreferencesBar({
  preferences,
  isEnabled,
  onToggle,
  onRemovePreference,
}: ActivePreferencesBarProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (preferences.length === 0) {
    return null;
  }

  const formatPreferenceValue = (value: Record<string, any>) => {
    if (value.preferred && Array.isArray(value.preferred)) {
      return value.preferred.slice(0, 2).join(', ') +
        (value.preferred.length > 2 ? ` +${value.preferred.length - 2}` : '');
    }
    return String(value);
  };

  const formatPreferenceType = (type: string) => {
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const getPreferenceTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'organism':
        return 'bg-surface-2 text-signal border-signal/30';
      case 'platform':
        return 'bg-surface-2 text-foreground/90 border-border';
      case 'disease_area':
        return 'bg-surface-2 text-foreground/90 border-border';
      default:
        return 'bg-surface-2 text-muted-foreground border-border';
    }
  };

  return (
    <Card className={`elev transition-[transform,box-shadow,border-color] duration-150 ease-out ${
      isEnabled
        ? 'trace-band border-border-strong'
        : 'border-border bg-card'
    }`}>
      <div className="p-3">
        {/* Compact View */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Filter className={`w-4 h-4 flex-shrink-0 ${
              isEnabled ? 'text-signal' : 'text-muted-foreground'
            }`} />
            <div className="flex items-center gap-2 flex-wrap flex-1 min-w-0">
              <span className={`text-sm font-medium ${
                isEnabled ? 'text-foreground' : 'text-muted-foreground'
              }`}>
                Preferences
              </span>
              <Badge variant="outline" className={`text-xs ${
                isEnabled
                  ? 'border-signal/30 text-signal'
                  : 'border-border text-muted-foreground/70'
              }`}>
                {preferences.length}
              </Badge>
              {!isExpanded && preferences.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {preferences.slice(0, 3).map((pref) => (
                    <Badge
                      key={pref.id}
                      className={`text-xs border ${
                        isEnabled
                          ? getPreferenceTypeColor(pref.preferenceType)
                          : 'bg-surface-2 text-muted-foreground/70 border-border'
                      }`}
                    >
                      {formatPreferenceType(pref.preferenceType)}
                    </Badge>
                  ))}
                  {preferences.length > 3 && (
                    <span className="text-muted-foreground/70 text-xs">
                      +{preferences.length - 3} more
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Toggle Enable/Disable */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onToggle(!isEnabled)}
              className={`text-xs ${
                isEnabled
                  ? 'text-signal hover:text-signal hover:bg-accent'
                  : 'text-muted-foreground hover:text-foreground/90 hover:bg-accent'
              }`}
            >
              {isEnabled ? 'Disable' : 'Enable'}
            </Button>

            {/* Expand/Collapse */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-muted-foreground hover:text-foreground/90 hover:bg-accent"
            >
              {isExpanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>

        {/* Expanded View */}
        {isExpanded && (
          <div className="mt-3 pt-3 border-t border-border space-y-2 animate-in fade-in duration-200">
            {preferences.map((pref) => (
              <div
                key={pref.id}
                className={`flex items-start justify-between gap-2 p-2 rounded-lg transition-colors ${
                  isEnabled
                    ? 'bg-surface-2 hover:bg-surface-2'
                    : 'bg-card opacity-50'
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge
                      className={`text-xs border ${
                        isEnabled
                          ? getPreferenceTypeColor(pref.preferenceType)
                          : 'bg-surface-2 text-muted-foreground/70 border-border'
                      }`}
                    >
                      {formatPreferenceType(pref.preferenceType)}
                    </Badge>
                    {pref.confidenceScore && (
                      <span className="text-muted-foreground/70 text-xs font-mono">
                        {Math.round(pref.confidenceScore * 100)}%
                      </span>
                    )}
                  </div>
                  <p className={`text-sm break-words ${
                    isEnabled ? 'text-foreground' : 'text-muted-foreground/70'
                  }`}>
                    {formatPreferenceValue(pref.preferenceValue)}
                  </p>
                </div>
                {onRemovePreference && isEnabled && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRemovePreference(pref.id)}
                    className="h-6 px-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                    title="Remove from active filters"
                  >
                    <X className="w-3 h-3" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Status Message */}
        {isEnabled && (
          <p className="text-muted-foreground/70 text-xs mt-2">
            Your preferences are being applied to searches
          </p>
        )}
      </div>
    </Card>
  );
}
