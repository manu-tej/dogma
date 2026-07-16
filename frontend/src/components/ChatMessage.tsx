import { User, Bot, Wrench, FileText, ExternalLink } from 'lucide-react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import ReactMarkdown from 'react-markdown';
import { ReasoningSteps } from './ReasoningSteps';
import { Button } from './ui/button';
import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { DatasetTable } from './DatasetTable';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  reasoning?: ReasoningStep[];
  analysis?: {
    type: string;
    data: any;
  };
}

interface ReasoningStep {
  id: string;
  type: 'query_analysis' | 'query_planning' | 'database_search' | 'harmonization' | 'filtering' | 'synthesis';
  title: string;
  description: string;
  status: 'pending' | 'running' | 'complete';
}

interface ChatMessageProps {
  message: Message;
  onAction?: (action: string, data?: any) => void;
}

export function ChatMessage({ message, onAction }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : ''} animate-in fade-in slide-in-from-bottom-4 duration-500`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-signal flex items-center justify-center text-primary-foreground flex-shrink-0">
          <Bot className="w-5 h-5" />
        </div>
      )}

      <div className={`flex-1 max-w-3xl ${isUser ? 'flex justify-end' : ''}`}>
        <div className={`space-y-4 ${isUser ? '' : ''}`}>
          {/* Reasoning Steps */}
          {message.reasoning && message.reasoning.length > 0 && (
            <div className="bg-card border border-border rounded-xl p-4 elev">
              <ReasoningSteps steps={message.reasoning} />
            </div>
          )}

          {/* Message Content */}
          {(message.content || message.analysis) && (
            <div className={`rounded-xl p-4 elev ${
              isUser
                ? 'bg-surface-2 text-foreground'
                : 'bg-card border border-border'
            }`}>
              {message.content && (
                <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : ''}`}>
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className={isUser ? 'text-foreground' : 'text-foreground/90'}>{children}</p>,
                      strong: ({ children }) => <strong className="text-foreground">{children}</strong>,
                      ul: ({ children }) => <ul className={`list-disc pl-5 space-y-1 ${isUser ? 'text-foreground' : 'text-foreground/90'}`}>{children}</ul>,
                      ol: ({ children }) => <ol className={`list-decimal pl-5 space-y-1 ${isUser ? 'text-foreground' : 'text-foreground/90'}`}>{children}</ol>,
                      li: ({ children }) => <li className={isUser ? 'text-foreground' : 'text-foreground/90'}>{children}</li>,
                      code: ({ children }) => <code className="bg-surface-2 text-signal px-1.5 py-0.5 rounded text-sm font-mono">{children}</code>,
                      h1: ({ children }) => <h1 className="text-xl mb-2 text-foreground">{children}</h1>,
                      h2: ({ children }) => <h2 className="text-lg mb-2 text-foreground">{children}</h2>,
                      h3: ({ children }) => <h3 className="mb-1 text-foreground">{children}</h3>,
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
              )}

              {message.analysis && (
                <Card className="mt-4 p-4 bg-surface-1 border-border elev">
                  <div className="flex items-center gap-2 mb-3">
                    <Badge variant="secondary" className="bg-surface-2 text-foreground/90 border-border">{message.analysis.type}</Badge>
                  </div>

                  {message.analysis.type === 'Sequence Analysis' && (
                    <div className="space-y-2 text-sm">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-muted-foreground/70">Sequence Length</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.length} bp</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">GC Content</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.gcContent}%</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">Organism</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.organism}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">Gene</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.gene}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {message.analysis.type === 'Expression Analysis' && (
                    <div className="space-y-2 text-sm">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-muted-foreground/70">Samples</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.samples}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">DEGs Found</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.degs}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">Upregulated</p>
                          <p className="text-positive font-mono">{message.analysis.data.upregulated}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">Downregulated</p>
                          <p className="text-destructive font-mono">{message.analysis.data.downregulated}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {message.analysis.type === 'Dataset Search Results' && (
                    <div className="space-y-4">
                      {/* Summary Stats */}
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-muted-foreground/70">Datasets Found</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.datasets}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">Total Samples</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.totalSamples}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">Organisms</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.organisms}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">Platform</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.platform}</p>
                        </div>
                      </div>

                      {/* Detailed Dataset Characteristics Table */}
                      {message.analysis.data.datasetDetails && (
                        <DatasetTable datasets={message.analysis.data.datasetDetails} />
                      )}

                      {/* Interactive Action Buttons */}
                      <div className="flex flex-wrap gap-2 pt-2">
                        <button
                          onClick={() => onAction?.('viewDetails', message.analysis?.data.datasetDetails)}
                          className="px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg transition-[transform,box-shadow,border-color] duration-150 ease-out active:scale-[0.98] glow-signal flex items-center gap-2"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                          View Full Details
                        </button>
                        <button
                          onClick={() => onAction?.('analyzeMetadata', message.analysis?.data.datasetDetails)}
                          className="px-4 py-2 bg-surface-2 hover:bg-accent text-foreground/90 text-sm rounded-lg transition-colors duration-150 ease-out active:scale-[0.98] flex items-center gap-2"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                          </svg>
                          Analyze Metadata
                        </button>
                        <button
                          onClick={() => onAction?.('downloadSummary', message.analysis?.data)}
                          className="px-4 py-2 bg-surface-2 hover:bg-accent text-foreground/90 text-sm rounded-lg transition-colors duration-150 ease-out active:scale-[0.98] flex items-center gap-2"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                          </svg>
                          Download Summary
                        </button>
                        <button
                          onClick={() => onAction?.('runSurvivalAnalysis', message.analysis?.data.datasetDetails?.filter((d: any) => d.survivalData))}
                          className="px-4 py-2 bg-surface-2 hover:bg-accent text-foreground/90 text-sm rounded-lg transition-colors duration-150 ease-out active:scale-[0.98] flex items-center gap-2"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                          Run Survival Analysis
                        </button>
                      </div>
                    </div>
                  )}

                  {message.analysis.type === 'Protein Structure' && (
                    <div className="space-y-2 text-sm">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-muted-foreground/70">PDB ID</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.pdbId}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">Resolution</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.resolution} Å</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">Method</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.method}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground/70">Chains</p>
                          <p className="text-foreground/90 font-mono">{message.analysis.data.chains}</p>
                        </div>
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {/* Suggested Replies */}
              {!isUser && message.analysis?.type === 'Dataset Search Results' && (
                <div className="mt-4 space-y-2">
                  <p className="text-muted-foreground/70 text-xs">Suggested follow-ups:</p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => onAction?.('suggestedReply', 'Generate a bioinformatics analysis plan')}
                      className="px-3 py-1.5 bg-surface-2 hover:bg-accent border border-border hover:border-border-strong text-foreground/90 text-xs rounded-lg transition-colors duration-150 ease-out active:scale-[0.98]"
                    >
                      Generate a bioinformatics plan
                    </button>
                    <button
                      onClick={() => onAction?.('suggestedReply', 'Compare these datasets by quality metrics')}
                      className="px-3 py-1.5 bg-surface-2 hover:bg-accent border border-border hover:border-border-strong text-foreground/90 text-xs rounded-lg transition-colors duration-150 ease-out active:scale-[0.98]"
                    >
                      Compare by quality metrics
                    </button>
                    <button
                      onClick={() => onAction?.('suggestedReply', 'Show me statistical power analysis for these datasets')}
                      className="px-3 py-1.5 bg-surface-2 hover:bg-accent border border-border hover:border-border-strong text-foreground/90 text-xs rounded-lg transition-colors duration-150 ease-out active:scale-[0.98]"
                    >
                      Statistical power analysis
                    </button>
                    <button
                      onClick={() => onAction?.('suggestedReply', 'Create a data integration workflow')}
                      className="px-3 py-1.5 bg-surface-2 hover:bg-accent border border-border hover:border-border-strong text-foreground/90 text-xs rounded-lg transition-colors duration-150 ease-out active:scale-[0.98]"
                    >
                      Create integration workflow
                    </button>
                  </div>
                </div>
              )}

              <p className="text-xs mt-2 font-mono text-muted-foreground/70">
                {message.timestamp.toLocaleTimeString()}
              </p>
            </div>
          )}
        </div>
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-surface-2 flex items-center justify-center flex-shrink-0">
          <User className="w-5 h-5 text-muted-foreground" />
        </div>
      )}
    </div>
  );
}
