import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import en from './locales/en.json'
import mk from './locales/mk.json'

// Supported languages
export const LANGUAGES = {
  en: {
    code: 'en',
    name: 'English',
    nativeName: 'English',
    flag: '🇬🇧', // Union Jack
  },
  mk: {
    code: 'mk',
    name: 'Macedonian',
    nativeName: 'Македонски',
    flag: '🇲🇰', // Macedonian flag
  },
} as const

export type LanguageCode = keyof typeof LANGUAGES

// Language storage key
const LANGUAGE_STORAGE_KEY = 'qms-ui-language'

// Initialize i18n
i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      mk: { translation: mk },
    },
    fallbackLng: 'en',
    defaultNS: 'translation',
    interpolation: {
      escapeValue: false, // React already escapes values
    },
    detection: {
      // Order of language detection
      order: ['localStorage', 'navigator'],
      // Cache user language selection
      caches: ['localStorage'],
      // Key for localStorage
      lookupLocalStorage: LANGUAGE_STORAGE_KEY,
    },
  })

// Helper to get current language
export const getCurrentLanguage = (): LanguageCode => {
  const lang = i18n.language?.substring(0, 2)
  return lang === 'mk' ? 'mk' : 'en'
}

// Helper to set language
export const setLanguage = (lang: LanguageCode): void => {
  i18n.changeLanguage(lang)
  localStorage.setItem(LANGUAGE_STORAGE_KEY, lang)
}

export default i18n
