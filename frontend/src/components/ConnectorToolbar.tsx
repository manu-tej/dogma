/**
 * Connector Toolbar Component
 *
 * Displays current connector and export capabilities
 * Minimal MVP version for conference demo
 */

import { ConnectorSelector } from './ConnectorSelector';
import { Badge } from './ui/badge';
import { Database } from 'lucide-react';

interface ConnectorToolbarProps {
  selectedConnector: string;
  onSelectConnector: (connectorId: string) => void;
}

export function ConnectorToolbar({ selectedConnector, onSelectConnector }: ConnectorToolbarProps) {
  return (
    <div className="border-b border-border bg-surface-1 px-4 py-3">
      <div className="flex items-center justify-between max-w-7xl mx-auto">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-signal" />
            <span className="text-sm font-medium text-foreground">Unified Framework</span>
          </div>
          <ConnectorSelector
            selectedConnector={selectedConnector}
            onSelectConnector={onSelectConnector}
          />
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            Export: JSON, JSON-LD, Parquet, MAGE-TAB, ISA-TAB
          </Badge>
        </div>
      </div>
    </div>
  );
}
