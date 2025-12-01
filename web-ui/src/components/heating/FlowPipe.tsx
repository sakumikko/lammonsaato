import { cn } from '@/lib/utils';

interface FlowPipeProps {
  variant: 'hot' | 'cold' | 'inactive';
  direction?: 'horizontal' | 'vertical';
  flowing?: boolean;
  reverse?: boolean;
  className?: string;
  thickness?: 'thin' | 'normal' | 'thick';
}

export function FlowPipe({
  variant,
  direction = 'horizontal',
  flowing = true,
  reverse = false,
  className,
  thickness = 'normal',
}: FlowPipeProps) {
  const thicknessClasses = {
    thin: direction === 'horizontal' ? 'h-1' : 'w-1',
    normal: direction === 'horizontal' ? 'h-2' : 'w-2',
    thick: direction === 'horizontal' ? 'h-3' : 'w-3',
  };

  const baseColor = {
    hot: 'bg-hot/30',
    cold: 'bg-cold/30',
    inactive: 'bg-muted',
  };

  const glowColor = {
    hot: 'shadow-glow-hot',
    cold: 'shadow-glow-cold',
    inactive: '',
  };

  return (
    <div
      className={cn(
        'relative rounded-full overflow-hidden transition-all duration-500',
        thicknessClasses[thickness],
        baseColor[variant],
        flowing && variant !== 'inactive' && glowColor[variant],
        className
      )}
    >
      {flowing && variant !== 'inactive' && (
        <div
          className={cn(
            'absolute inset-0',
            variant === 'hot' && 'pipe-flow-hot',
            variant === 'cold' && 'pipe-flow-cold',
            reverse && 'pipe-flow-reverse'
          )}
        />
      )}
    </div>
  );
}
