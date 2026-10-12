/**
 * useStrings.ts — Minimal i18n hook.
 * Switches between English (default) and Hindi string tables.
 * Extend by adding more locales to the LOCALES map.
 */
import { useState } from 'react';
import { en } from './en';
import { hi } from './hi';
import type { Strings } from './en';

const LOCALES: Record<string, Strings> = { en, hi };
export type Locale = keyof typeof LOCALES;

export function useStrings(defaultLocale: Locale = 'en') {
  const [locale, setLocale] = useState<Locale>(defaultLocale);
  const strings = LOCALES[locale] ?? en;
  return { strings, locale, setLocale, availableLocales: Object.keys(LOCALES) as Locale[] };
}
