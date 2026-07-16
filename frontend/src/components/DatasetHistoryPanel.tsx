/**
 * DatasetHistoryPanel Component
 *
 * Displays a user's dataset interaction history, providing quick access to
 * previously viewed datasets with filtering and search capabilities.
 */

import { useState, useEffect } from 'react';
import { Clock, Database, Eye, BarChart3, Download, Search, X, ChevronRight, AlertCircle } from 'lucide-react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { LoadingSpinner } from './LoadingSpinner';
import { contextApi } from '../services/contextApi';
import type { RecalledDataset } from '@/types/context';

interface DatasetHistoryPanelProps {
  userId: string;
  isOpen: boolean;
  onClose: () => void;
  onDatasetSelect: (datasetId: string, metadata?: Record<string, any>) => void;
}

export function DatasetHistoryPanel({
  userId,
  isOpen,
  onClose,
  onDatasetSelect,
}: DatasetHistoryPanelProps) {
  const [datasets, setDatasets] = useState<RecalledDataset[]>([]);
  const [filteredDatasets, setFilteredDatasets] = useState<RecalledDataset[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch dataset history when panel opens
  useEffect(() => {
    if (isOpen && userId) {
      fetchDatasetHistory();
    }
  }, [isOpen, userId]);

  // Filter datasets when search query changes
  useEffect(() => {
    if (searchQuery.trim() === '') {
      setFilteredDatasets(datasets);
    } else {
      const query = searchQuery.toLowerCase();
      const filtered = datasets.filter(
        (dataset) =>
          dataset.dataset_id.toLowerCase().includes(query) ||
          dataset.dataset_type.toLowerCase().includes(query) ||
          dataset.metadata?.title?.toLowerCase().includes(query)
      );
      setFilteredDatasets(filtered);
    }
  }, [searchQuery, datasets]);

  const fetchDatasetHistory = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const recalledDatasets = await contextApi.getRecalledDatasets(userId, 50);
      setDatasets(recalledDatasets);
      setFilteredDatasets(recalledDatasets);
    } catch (err) {
      console.error('Failed to fetch dataset history:', err);
      setError(err instanceof Error ? err.message : 'Failed to load dataset history');
    } finally {
      setIsLoading(false);
    }
  };

  const getTimeAgo = (timestamp: string): string => {
    const now = new Date();
    const past = new Date(timestamp);
    const diff = now.getTime() - past.getTime();
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
      return `${days}d ago`;
    } else if (hours > 0) {
      return `${hours}h ago`;
    } else if (minutes > 0) {
      return `${minutes}m ago`;
    } else {
      return 'Just now';
    }
  };

  const getInteractionIcon = (type: string) => {
    switch (type) {
      case 'view':
        return <Eye className="w-3 h-3" />;
      case 'analyze':
        return <BarChart3 className="w-3 h-3" />;
      case 'download':
        return <Download className="w-3 h-3" />;
      default:
        return <Database className="w-3 h-3" />;
    }
  };

  const getInteractionColor = (type: string) => {
    switch (type) {
      case 'view':
        return 'bg-surface-2 text-signal border-signal/30';
      case 'analyze':
        return 'bg-surface-2 text-foreground/90 border-border';
      case 'download':
        return 'bg-surface-2 text-positive border-border';
      default:
        return 'bg-surface-2 text-muted-foreground border-border';
    }
  };

  const getDatasetTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'geo':
        return 'bg-surface-2 text-signal border-signal/30';
      case 'sra':
        return 'bg-surface-2 text-foreground/90 border-border';
      case 'pride':
        return 'bg-surface-2 text-foreground/90 border-border';
      default:
        return 'bg-surface-2 text-muted-foreground border-border';
    }
  };

  const handleDatasetClick = (dataset: RecalledDataset) => {
    onDatasetSelect(dataset.dataset_id, dataset.metadata);
    // Optionally close panel after selection
    // onClose();
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="w-80 h-full bg-background border-l border-border flex flex-col animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="p-4 border-b border-border bg-surface-1">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-signal" />
            <h3 className="text-foreground font-semibold">Dataset History</h3>
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

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search datasets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 bg-surface-2 border-border text-foreground placeholder:text-muted-foreground/70"
          />
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 p-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="md" variant="primary" text="Loading history..." />
          </div>
        ) : error ? (
          <Card className="p-4 border border-destructive/40 bg-destructive/10">
            <div className="flex items-start gap-2 text-destructive">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold mb-1">Error loading history</p>
                <p className="text-xs text-destructive/90">{error}</p>
              </div>
            </div>
          </Card>
        ) : filteredDatasets.length === 0 ? (
          <Card className="p-6 border border-border bg-card">
            <div className="text-center">
              <Database className="w-12 h-12 text-muted-foreground/70 mx-auto mb-3" />
              <p className="text-muted-foreground text-sm mb-1">
                {searchQuery ? 'No matching datasets' : 'No dataset history yet'}
              </p>
              <p className="text-muted-foreground/70 text-xs">
                {searchQuery
                  ? 'Try a different search term'
                  : 'Start exploring datasets to build your history'}
              </p>
            </div>
          </Card>
        ) : (
          <div className="space-y-3">
            {filteredDatasets.map((dataset) => (
              <Card
                key={dataset.dataset_id}
                className="elev p-3 border border-border bg-card hover:-translate-y-0.5 hover:border-border-strong cursor-pointer transition-[transform,box-shadow,border-color] duration-150 ease-out group"
                onClick={() => handleDatasetClick(dataset)}
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    {/* Dataset ID and Type */}
                    <div className="flex items-center gap-2 mb-2">
                      <Badge
                        className={`text-xs font-mono border ${getDatasetTypeColor(
                          dataset.dataset_type
                        )}`}
                      >
                        {dataset.dataset_type.toUpperCase()}
                      </Badge>
                      <span className="text-foreground font-medium truncate font-mono">
                        {dataset.dataset_id}
                      </span>
                    </div>

                    {/* Metadata Title (if available) */}
                    {dataset.metadata?.title && (
                      <p className="text-muted-foreground text-xs mb-2 line-clamp-2">
                        {dataset.metadata.title}
                      </p>
                    )}

                    {/* Interaction Badges */}
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      {dataset.interaction_types.map((type) => (
                        <Badge
                          key={type}
                          className={`text-xs border ${getInteractionColor(type)}`}
                        >
                          <span className="mr-1">{getInteractionIcon(type)}</span>
                          {type}
                        </Badge>
                      ))}
                    </div>

                    {/* Time and Count */}
                    <div className="flex items-center gap-3 text-muted-foreground/70 text-xs">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span className="font-mono">{getTimeAgo(dataset.last_interaction)}</span>
                      </div>
                      <span>•</span>
                      <span>{dataset.interaction_count} interaction{dataset.interaction_count !== 1 ? 's' : ''}</span>
                    </div>
                  </div>

                  {/* Arrow Icon (shown on hover) */}
                  <ChevronRight className="w-4 h-4 text-muted-foreground/70 group-hover:text-signal transition-colors flex-shrink-0 mt-1" />
                </div>
              </Card>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* Footer */}
      {!isLoading && !error && filteredDatasets.length > 0 && (
        <div className="p-4 border-t border-border bg-surface-1">
          <p className="text-muted-foreground/70 text-xs text-center">
            Showing {filteredDatasets.length} of {datasets.length} dataset{datasets.length !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </div>
  );
}
