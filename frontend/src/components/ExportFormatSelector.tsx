/**
 * Export Format Selector Component
 *
 * Allows users to select export format for curated datasets
 * Supports: JSON, JSON-LD, Parquet, MAGE-TAB, ISA-TAB
 */

import { Button } from './ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu';
import { Download, FileJson, Database, FileSpreadsheet } from 'lucide-react';

interface ExportFormat {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  category: 'standard' | 'analytics' | 'submission';
}

const exportFormats: ExportFormat[] = [
  {
    id: 'json',
    name: 'JSON',
    description: 'Standard JSON format',
    icon: <FileJson className="w-4 h-4" />,
    category: 'standard'
  },
  {
    id: 'jsonld',
    name: 'JSON-LD',
    description: 'Semantic web compatible',
    icon: <FileJson className="w-4 h-4" />,
    category: 'standard'
  },
  {
    id: 'parquet',
    name: 'Parquet',
    description: 'Columnar format for analytics',
    icon: <Database className="w-4 h-4" />,
    category: 'analytics'
  },
  {
    id: 'magetab',
    name: 'MAGE-TAB',
    description: 'ArrayExpress submission',
    icon: <FileSpreadsheet className="w-4 h-4" />,
    category: 'submission'
  },
  {
    id: 'isatab',
    name: 'ISA-TAB',
    description: 'MetaboLights submission',
    icon: <FileSpreadsheet className="w-4 h-4" />,
    category: 'submission'
  }
];

interface ExportFormatSelectorProps {
  datasetId: string;
  onExport: (datasetId: string, format: string) => void;
  disabled?: boolean;
}

export function ExportFormatSelector({ datasetId, onExport, disabled = false }: ExportFormatSelectorProps) {
  const handleExport = (format: string) => {
    onExport(datasetId, format);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled}
          className="gap-2"
        >
          <Download className="w-4 h-4" />
          Export
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[280px]">
        <DropdownMenuLabel>Export Format</DropdownMenuLabel>
        <DropdownMenuSeparator />

        <div className="px-2 py-1.5">
          <div className="text-xs font-medium text-muted-foreground mb-1">Standard Formats</div>
        </div>
        {exportFormats.filter(f => f.category === 'standard').map((format) => (
          <DropdownMenuItem
            key={format.id}
            onClick={() => handleExport(format.id)}
            className="gap-2"
          >
            {format.icon}
            <div className="flex flex-col">
              <span className="font-medium">{format.name}</span>
              <span className="text-xs text-muted-foreground">{format.description}</span>
            </div>
          </DropdownMenuItem>
        ))}

        <DropdownMenuSeparator />

        <div className="px-2 py-1.5">
          <div className="text-xs font-medium text-muted-foreground mb-1">Analytics</div>
        </div>
        {exportFormats.filter(f => f.category === 'analytics').map((format) => (
          <DropdownMenuItem
            key={format.id}
            onClick={() => handleExport(format.id)}
            className="gap-2"
          >
            {format.icon}
            <div className="flex flex-col">
              <span className="font-medium">{format.name}</span>
              <span className="text-xs text-muted-foreground">{format.description}</span>
            </div>
          </DropdownMenuItem>
        ))}

        <DropdownMenuSeparator />

        <div className="px-2 py-1.5">
          <div className="text-xs font-medium text-muted-foreground mb-1">Repository Submission</div>
        </div>
        {exportFormats.filter(f => f.category === 'submission').map((format) => (
          <DropdownMenuItem
            key={format.id}
            onClick={() => handleExport(format.id)}
            className="gap-2"
          >
            {format.icon}
            <div className="flex flex-col">
              <span className="font-medium">{format.name}</span>
              <span className="text-xs text-muted-foreground">{format.description}</span>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
