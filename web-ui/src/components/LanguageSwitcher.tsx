import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';
import { setLanguage } from '@/i18n';

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  const currentLang = i18n.language;

  const toggleLanguage = () => {
    const newLang = currentLang === 'fi' ? 'en' : 'fi';
    setLanguage(newLang);
  };

  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
      title={t('language.select')}
    >
      <Globe className="w-4 h-4 text-muted-foreground" />
      <span className="text-sm font-medium text-foreground">
        {currentLang === 'fi' ? 'FI' : 'EN'}
      </span>
    </button>
  );
}
