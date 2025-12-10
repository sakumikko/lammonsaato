import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface StatusIndicatorProps {
  connected: boolean;
  systemActive: boolean;
  error?: string | null;
  className?: string;
}

/**
 * Consolidated status indicator showing connection and system state.
 * - Green: connected & system active
 * - Yellow: connected but system idle
 * - Red: disconnected
 */
export function StatusIndicator({
  connected,
  systemActive,
  error,
  className,
}: StatusIndicatorProps) {
  const { t } = useTranslation();

  // Determine status
  const status = !connected ? 'disconnected' : systemActive ? 'active' : 'idle';

  const statusConfig = {
    disconnected: {
      color: 'bg-destructive',
      pulseColor: 'bg-destructive/50',
      label: t('status.disconnected'),
      description: error || t('status.noConnection'),
    },
    idle: {
      color: 'bg-warning',
      pulseColor: 'bg-warning/50',
      label: t('status.connected'),
      description: t('status.systemIdle'),
    },
    active: {
      color: 'bg-success',
      pulseColor: 'bg-success/50',
      label: t('status.connected'),
      description: t('status.systemActive'),
    },
  };

  const config = statusConfig[status];

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            className={cn(
              'relative flex items-center justify-center w-8 h-8 rounded-lg',
              'bg-muted/50 hover:bg-muted transition-colors',
              className
            )}
            aria-label={`${config.label}: ${config.description}`}
            data-testid="status-indicator"
            data-status={status}
          >
            {/* Pulse animation for active state */}
            {status === 'active' && (
              <span
                className={cn(
                  'absolute w-3 h-3 rounded-full animate-ping',
                  config.pulseColor
                )}
              />
            )}
            {/* Status dot */}
            <span
              className={cn(
                'relative w-3 h-3 rounded-full',
                config.color
              )}
            />
          </button>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          <div className="text-sm">
            <div className="font-medium">{config.label}</div>
            <div className="text-muted-foreground">{config.description}</div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
