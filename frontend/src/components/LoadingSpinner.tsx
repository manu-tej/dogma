/**
 * LoadingSpinner Component
 *
 * Reusable loading spinner with different sizes and variants.
 */

import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'primary' | 'subtle';
  text?: string;
  className?: string;
}

export function LoadingSpinner({
  size = 'md',
  variant = 'default',
  text,
  className = '',
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  const variantClasses = {
    default: 'text-muted-foreground',
    primary: 'text-signal',
    subtle: 'text-muted-foreground/70',
  };

  const textSizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <Loader2
        className={`animate-spin ${sizeClasses[size]} ${variantClasses[variant]}`}
      />
      {text && (
        <span className={`${variantClasses[variant]} ${textSizeClasses[size]}`}>
          {text}
        </span>
      )}
    </div>
  );
}

/**
 * Full page loading overlay
 */
export function LoadingOverlay({ text = 'Loading...' }: { text?: string }) {
  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-card rounded-xl p-6 border border-border elev">
        <LoadingSpinner size="lg" variant="primary" text={text} />
      </div>
    </div>
  );
}

/**
 * Skeleton loader for conversation list
 */
export function ConversationSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="p-4 rounded-xl border border-border bg-card elev signal-sweep"
        >
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-surface-2 shimmer" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-surface-2 rounded w-3/4 shimmer" />
              <div className="h-3 bg-surface-2 rounded w-1/2 shimmer" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Skeleton loader for messages
 */
export function MessageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {[1, 2].map((i) => (
        <div key={i} className="flex gap-3">
          <div className="w-8 h-8 rounded-full bg-surface-2 shimmer" />
          <div className="flex-1 space-y-2">
            <div className="bg-card rounded-xl p-4 border border-border elev">
              <div className="space-y-2">
                <div className="h-4 bg-surface-2 rounded w-full shimmer" />
                <div className="h-4 bg-surface-2 rounded w-5/6 shimmer" />
                <div className="h-4 bg-surface-2 rounded w-4/6 shimmer" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
