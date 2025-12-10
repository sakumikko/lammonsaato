import { Settings, Sun, Moon, Globe, Wrench, Database } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '@/contexts/ThemeContext';
import { setLanguage } from '@/i18n';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface SettingsDropdownProps {
  onOpenHeatPumpSettings: () => void;
}

/**
 * Settings dropdown containing theme, language, and heat pump settings.
 */
export function SettingsDropdown({ onOpenHeatPumpSettings }: SettingsDropdownProps) {
  const { t, i18n } = useTranslation();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const currentLang = i18n.language;

  const toggleLanguage = () => {
    const newLang = currentLang === 'fi' ? 'en' : 'fi';
    setLanguage(newLang);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          data-testid="settings-dropdown"
        >
          <Settings className="h-4 w-4" />
          <span className="sr-only">{t('settings.title')}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        {/* Heat pump settings */}
        <DropdownMenuItem onClick={onOpenHeatPumpSettings} className="cursor-pointer">
          <Wrench className="mr-2 h-4 w-4" />
          <span>{t('settings.title')}</span>
        </DropdownMenuItem>

        {/* Entity browser */}
        <DropdownMenuItem onClick={() => navigate('/entities')} className="cursor-pointer">
          <Database className="mr-2 h-4 w-4" />
          <span>{t('entityBrowser.title')}</span>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* Theme toggle */}
        <DropdownMenuItem onClick={toggleTheme} className="cursor-pointer">
          {theme === 'dark' ? (
            <Moon className="mr-2 h-4 w-4" />
          ) : (
            <Sun className="mr-2 h-4 w-4" />
          )}
          <span>{theme === 'dark' ? t('theme.dark') : t('theme.light')}</span>
        </DropdownMenuItem>

        {/* Language toggle */}
        <DropdownMenuItem onClick={toggleLanguage} className="cursor-pointer">
          <Globe className="mr-2 h-4 w-4" />
          <span>{t('language.select')}: {currentLang === 'fi' ? 'FI' : 'EN'}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
