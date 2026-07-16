/**
 * PreferencesPanel Component
 *
 * Displays user preferences in a collapsible side panel with ability to view,
 * edit, and delete saved preferences with confidence scores.
 */

import { useState, useEffect } from 'react';
import { Settings, X, Trash2, Edit2, Check, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { LoadingSpinner } from './LoadingSpinner';
import { useUserPreferences } from '../hooks/useUserPreferences';
import type { PreferenceResponse } from '@/types/preferences';

interface PreferencesPanelProps {
  userId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function PreferencesPanel({
  userId,
  isOpen,
  onClose,
}: PreferencesPanelProps) {
  const {
    preferences,
    loadingState,
    deletePreference,
    refreshPreferences,
  } = useUserPreferences({
    userId,
    autoFetch: isOpen,
  });

  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set(['organism', 'platform', 'disease_area']));
  const [editingId, setEditingId] = useState<string | null>(null);

  // Refresh preferences when panel opens
  useEffect(() => {
    if (isOpen && userId) {
      refreshPreferences();
    }
  }, [isOpen, userId, refreshPreferences]);

  // Group preferences by type
  const groupedPreferences = preferences.reduce((acc, pref) => {
    const type = pref.preferenceType;
    if (!acc[type]) {
      acc[type] = [];
    }
    acc[type].push(pref);
    return acc;
  }, {} as Record<string, PreferenceResponse[]>);

  const toggleTypeExpansion = (type: string) => {
    setExpandedTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  const handleDelete = async (preferenceId: string) => {
    if (confirm('Are you sure you want to delete this preference?')) {
      const success = await deletePreference(preferenceId);
      if (success) {
        console.log('Preference deleted successfully');
      }
    }
  };

  const getConfidenceColor = (score?: number) => {
    if (!score) return 'bg-surface-2 text-muted-foreground border-border';
    if (score >= 0.8) return 'bg-surface-2 text-positive border-border';
    if (score >= 0.6) return 'bg-surface-2 text-signal border-signal/30';
    return 'bg-surface-2 text-muted-foreground border-border';
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

  const formatPreferenceValue = (value: Record<string, any>) => {
    // Handle common preference value structures
    if (value.preferred && Array.isArray(value.preferred)) {
      return value.preferred.join(', ');
    }
    if (typeof value === 'object') {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  };

  const formatPreferenceType = (type: string) => {
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="w-96 h-full bg-background border-l border-border flex flex-col animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="p-4 border-b border-border bg-surface-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-signal" />
            <h3 className="text-foreground font-semibold">My Preferences</h3>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="hover:bg-accent text-muted-foreground"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>
        <p className="text-muted-foreground text-xs mt-2">
          Manage your saved search preferences and filters
        </p>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 p-4">
        {loadingState.isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="md" variant="primary" text="Loading preferences..." />
          </div>
        ) : loadingState.error ? (
          <Card className="p-4 border border-destructive/40 bg-destructive/10">
            <div className="flex items-start gap-2 text-destructive">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold mb-1">Error loading preferences</p>
                <p className="text-xs text-destructive/90">{loadingState.error}</p>
              </div>
            </div>
          </Card>
        ) : preferences.length === 0 ? (
          <Card className="p-6 border border-border bg-card">
            <div className="text-center">
              <Settings className="w-12 h-12 text-muted-foreground/70 mx-auto mb-3" />
              <p className="text-muted-foreground text-sm mb-1">No saved preferences yet</p>
              <p className="text-muted-foreground/70 text-xs">
                Preferences will be suggested based on your search patterns
              </p>
            </div>
          </Card>
        ) : (
          <div className="space-y-3">
            {Object.entries(groupedPreferences).map(([type, prefs]) => (
              <Card
                key={type}
                className="elev border border-border bg-card overflow-hidden"
              >
                {/* Type Header */}
                <div
                  className="p-3 cursor-pointer hover:bg-surface-1 transition-colors"
                  onClick={() => toggleTypeExpansion(type)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {expandedTypes.has(type) ? (
                        <ChevronDown className="w-4 h-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      )}
                      <Badge className={`text-xs border ${getPreferenceTypeColor(type)}`}>
                        {formatPreferenceType(type)}
                      </Badge>
                      <span className="text-muted-foreground text-sm">({prefs.length})</span>
                    </div>
                  </div>
                </div>

                {/* Preferences List */}
                {expandedTypes.has(type) && (
                  <div className="border-t border-border divide-y divide-border">
                    {prefs.map((pref) => (
                      <div
                        key={pref.id}
                        className="p-3 hover:bg-surface-1 transition-colors group"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            {/* Preference Value */}
                            <p className="text-foreground text-sm mb-2 break-words">
                              {formatPreferenceValue(pref.preferenceValue)}
                            </p>

                            {/* Metadata */}
                            <div className="flex items-center gap-2 flex-wrap">
                              {/* Confidence Score */}
                              {pref.confidenceScore && (
                                <Badge
                                  className={`text-xs border ${getConfidenceColor(
                                    pref.confidenceScore
                                  )}`}
                                >
                                  {Math.round(pref.confidenceScore * 100)}% confidence
                                </Badge>
                              )}

                              {/* Created Date */}
                              <span className="text-muted-foreground/70 text-xs font-mono">
                                Added {new Date(pref.createdAt).toLocaleDateString()}
                              </span>
                            </div>
                          </div>

                          {/* Actions */}
                          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(pref.id)}
                              className="h-8 px-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                              title="Delete preference"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Footer */}
      {!loadingState.isLoading && !loadingState.error && preferences.length > 0 && (
        <div className="p-4 border-t border-border bg-surface-1">
          <p className="text-muted-foreground/70 text-xs text-center">
            {preferences.length} saved preference{preferences.length !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </div>
  );
}
