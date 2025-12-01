import { Sun, Moon } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();
  const { t } = useTranslation();

  return (
    <button
      onClick={toggleTheme}
      className={cn(
        'flex items-center gap-1 md:gap-2 px-2 md:px-3 py-1.5 md:py-2 rounded-lg',
        'bg-muted/50 hover:bg-muted transition-colors',
        'text-foreground',
        className
      )}
      title={t('theme.toggle')}
      aria-label={t('theme.toggle')}
    >
      {theme === 'dark' ? (
        <>
          <Moon className="w-4 h-4" />
          <span className="text-sm font-medium hidden md:inline">{t('theme.dark')}</span>
        </>
      ) : (
        <>
          <Sun className="w-4 h-4" />
          <span className="text-sm font-medium hidden md:inline">{t('theme.light')}</span>
        </>
      )}
    </button>
  );
}
