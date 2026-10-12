/**
 * SafetyLanding.tsx — Calm, safety-first landing screen.
 */
import type { FC } from 'react';
import type { Strings } from '../i18n/en';

interface Props {
  strings: Strings;
  onStart: () => void;
  locale: string;
  onLocaleChange: (locale: string) => void;
}

export const SafetyLanding: FC<Props> = ({ strings: s, onStart, locale, onLocaleChange }) => {
  return (
    <div className="min-h-screen bg-calm-teal-50 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-sm border border-calm-teal-100 p-8 space-y-6">

        {/* Locale switcher */}
        <div className="flex justify-end gap-2">
          {(['en', 'hi'] as const).map((loc) => (
            <button
              key={loc}
              onClick={() => onLocaleChange(loc)}
              className={`text-xs px-2 py-1 rounded ${locale === loc ? 'bg-calm-teal-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              aria-pressed={locale === loc}
            >
              {loc === 'en' ? 'English' : 'हिंदी'}
            </button>
          ))}
        </div>

        {/* Shield icon */}
        <div className="text-center">
          <span className="text-5xl" role="img" aria-label="Shield">🛡️</span>
          <h1 className="mt-3 text-2xl font-bold text-calm-teal-700">{s.app.title}</h1>
          <p className="text-gray-500 text-sm mt-1">{s.app.tagline}</p>
        </div>

        {/* Core message */}
        <div className="bg-calm-teal-50 border-l-4 border-calm-teal-500 rounded-lg px-5 py-4">
          <p className="text-calm-teal-800 font-semibold text-lg">{s.landing.notAtFault}</p>
          <p className="text-calm-teal-700 text-sm mt-1">{s.landing.notAtFaultDetail}</p>
        </div>

        {/* Privacy explanation */}
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-1">{s.landing.privacyHeading}</h2>
          <p className="text-gray-600 text-sm">{s.landing.privacyDetail}</p>
        </div>

        {/* Helplines */}
        <div className="bg-gray-50 rounded-lg px-4 py-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{s.landing.helplines}</p>
          <p className="text-gray-700 text-sm">{s.landing.helplinesDetail}</p>
          <a
            href="https://cybercrime.gov.in"
            target="_blank"
            rel="noopener noreferrer"
            className="text-calm-teal-600 text-sm underline mt-1 inline-block"
          >
            {s.landing.cybercrimePortal}
          </a>
        </div>

        {/* Start button */}
        <button
          onClick={onStart}
          className="w-full bg-calm-teal-600 hover:bg-calm-teal-700 text-white font-semibold py-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-calm-teal-400 transition-colors"
        >
          {s.landing.startButton}
        </button>
      </div>
    </div>
  );
};
