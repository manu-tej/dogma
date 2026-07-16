/**
 * Connector Selector Component
 *
 * Allows users to select which data connector to use (GEO, ENA, PDB, DrugBank)
 * Demonstrates the unified framework's multi-connector capability
 */

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Database, Dna, Pill, Microscope } from 'lucide-react';

interface ConnectorOption {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  status: 'active' | 'coming-soon';
}

const connectors: ConnectorOption[] = [
  {
    id: 'geo',
    name: 'GEO',
    description: 'Gene Expression Omnibus',
    icon: <Dna className="w-4 h-4" />,
    status: 'active'
  },
  {
    id: 'ena',
    name: 'ENA',
    description: 'European Nucleotide Archive',
    icon: <Database className="w-4 h-4" />,
    status: 'coming-soon'
  },
  {
    id: 'pdb',
    name: 'PDB',
    description: 'Protein Data Bank',
    icon: <Microscope className="w-4 h-4" />,
    status: 'coming-soon'
  },
  {
    id: 'drugbank',
    name: 'DrugBank',
    description: 'Drug Database',
    icon: <Pill className="w-4 h-4" />,
    status: 'coming-soon'
  }
];

interface ConnectorSelectorProps {
  selectedConnector: string;
  onSelectConnector: (connectorId: string) => void;
}

export function ConnectorSelector({ selectedConnector, onSelectConnector }: ConnectorSelectorProps) {
  const selectedOption = connectors.find(c => c.id === selectedConnector);

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground">Data Source:</span>
      <Select value={selectedConnector} onValueChange={onSelectConnector}>
        <SelectTrigger className="w-[200px]">
          <SelectValue>
            <div className="flex items-center gap-2">
              {selectedOption?.icon}
              <span>{selectedOption?.name}</span>
              {selectedOption?.status === 'coming-soon' && (
                <span className="text-xs text-muted-foreground">(Soon)</span>
              )}
            </div>
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {connectors.map((connector) => (
            <SelectItem
              key={connector.id}
              value={connector.id}
              disabled={connector.status === 'coming-soon'}
            >
              <div className="flex items-center gap-2">
                {connector.icon}
                <div className="flex flex-col">
                  <span className="font-medium">{connector.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {connector.description}
                    {connector.status === 'coming-soon' && ' • Coming Soon'}
                  </span>
                </div>
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
