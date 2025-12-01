import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en.json';
import fi from './locales/fi.json';

// Get saved language or detect from browser
const getSavedLanguage = (): string => {
  const saved = localStorage.getItem('language');
  if (saved && ['en', 'fi'].includes(saved)) {
    return saved;
  }
  // Check browser language
  const browserLang = navigator.language.split('-')[0];
  return browserLang === 'fi' ? 'fi' : 'en';
};

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      fi: { translation: fi },
    },
    lng: getSavedLanguage(),
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // React already escapes
    },
  });

export default i18n;

export const setLanguage = (lang: string) => {
  i18n.changeLanguage(lang);
  localStorage.setItem('language', lang);
};

export const getCurrentLanguage = () => i18n.language;
