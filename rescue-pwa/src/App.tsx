/**
 * App.tsx — Rescue Kit main application.
 * Orchestrates all steps; keeps all case data in React state (never localStorage).
 */
import { useState } from 'react';
import { useStrings } from './i18n/useStrings';
import type { Locale } from './i18n/useStrings';
import { QuickExit } from './components/QuickExit';
import { SafetyLanding } from './components/SafetyLanding';
import { FileHasher } from './components/FileHasher';
import type { HashResult } from './components/FileHasher';
import { OriginLookup } from './components/OriginLookup';
import { EvidenceForm } from './components/EvidenceForm';
import { ManifestPreview } from './components/ManifestPreview';
import { ZipExport } from './components/ZipExport';
import { ComplaintDrafts } from './components/ComplaintDrafts';
import { buildManifest } from './lib/manifest';
import type { EvidenceItem } from './lib/manifest';
import { buildTakedownDraft, buildCybercrimeComplaintDraft } from './lib/drafts';

type Step = 'landing' | 'kit';

export default function App() {
  const { strings, locale, setLocale } = useStrings('en');
  const [step, setStep] = useState<Step>('landing');

  // Case state — session-only, cleared on reset
  const [hashResult, setHashResult] = useState<HashResult | null>(null);
  const [evidenceItems, setEvidenceItems] = useState<EvidenceItem[]>([
    { index: 0, url: '', platform: '', observed_at: '', notes: '' },
  ]);
  const [yourName, setYourName] = useState('');

  // Derived drafts — regenerated whenever name or hash changes
  const draftInputs = {
    platform: evidenceItems[0]?.platform,
    contentUrl: evidenceItems[0]?.url,
    observedAt: evidenceItems[0]?.observed_at,
    incidentDescription: evidenceItems[0]?.notes,
    fileSha256: hashResult?.sha256,
    filename: hashResult?.file?.name,
    yourName: yourName || undefined,
  };
  const [takedownDraft, setTakedownDraft] = useState(() =>
    buildTakedownDraft(draftInputs)
  );
  const [cybercrimeDraft, setCybercrimeDraft] = useState(() =>
    buildCybercrimeComplaintDraft(draftInputs)
  );

  // Regenerate drafts whenever form data changes
  const refreshDrafts = (overrides?: Partial<typeof draftInputs>) => {
    const inputs = { ...draftInputs, ...overrides };
    setTakedownDraft(buildTakedownDraft(inputs));
    setCybercrimeDraft(buildCybercrimeComplaintDraft(inputs));
  };

  const handleHashComplete = (result: HashResult) => {
    setHashResult(result);
    refreshDrafts({ fileSha256: result.sha256, filename: result.file.name });
  };

  const handleEvidenceChange = (items: EvidenceItem[]) => {
    setEvidenceItems(items);
    const first = items[0];
    refreshDrafts({
      platform: first?.platform,
      contentUrl: first?.url,
      observedAt: first?.observed_at,
      incidentDescription: first?.notes,
    });
  };

  const handleNameChange = (name: string) => {
    setYourName(name);
    refreshDrafts({ yourName: name || undefined });
  };

  const manifest = buildManifest({
    evidenceItems,
    fileSha256: hashResult?.sha256,
    fileDHash: hashResult?.dhash ?? undefined,
    selectedFilename: hashResult?.file?.name,
    appVersion: import.meta.env.VITE_APP_VERSION as string | undefined,
  });

  const handleClearSession = () => {
    setHashResult(null);
    setEvidenceItems([{ index: 0, url: '', platform: '', observed_at: '', notes: '' }]);
    setYourName('');
    setTakedownDraft(buildTakedownDraft({}));
    setCybercrimeDraft(buildCybercrimeComplaintDraft({}));
    setStep('landing');
  };

  if (step === 'landing') {
    return (
      <>
        <QuickExit
          label={strings.landing.quickExitLabel}
          warning={strings.landing.quickExitWarning}
        />
        <SafetyLanding
          strings={strings}
          onStart={() => setStep('kit')}
          locale={locale}
          onLocaleChange={(l) => setLocale(l as Locale)}
        />
      </>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <QuickExit
        label={strings.landing.quickExitLabel}
        warning={strings.landing.quickExitWarning}
      />

      {/* Header */}
      <header className="bg-calm-teal-700 text-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl" role="img" aria-label="Shield">🛡️</span>
          <span className="font-bold text-lg">{strings.app.title}</span>
        </div>
        <div className="flex gap-2">
          {(['en', 'hi'] as const).map((loc) => (
            <button
              key={loc}
              onClick={() => setLocale(loc as Locale)}
              className={`text-xs px-2 py-1 rounded ${locale === loc ? 'bg-white text-calm-teal-700' : 'text-calm-teal-100 hover:text-white'}`}
            >
              {loc === 'en' ? 'EN' : 'हि'}
            </button>
          ))}
        </div>
      </header>

      {/* Helplines banner */}
      <div className="bg-calm-teal-100 text-calm-teal-800 text-xs text-center py-1.5 px-4">
        {strings.landing.helplines}: {strings.landing.helplinesDetail}
      </div>

      {/* Main content */}
      <main className="max-w-2xl mx-auto px-4 py-8 space-y-10">

        {/* Step 1 — File hashing */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <FileHasher strings={strings} onHashComplete={handleHashComplete} />
        </div>

        {/* Step 2 — Origin lookup */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <OriginLookup
            strings={strings}
            dhash={hashResult?.dhash ?? null}
            dhashUnavailable={hashResult?.dhashUnavailable ?? true}
          />
        </div>

        {/* Step 3 — Evidence form */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <EvidenceForm
            strings={strings}
            items={evidenceItems}
            onChange={handleEvidenceChange}
          />
        </div>

        {/* Step 4 — Manifest preview */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <ManifestPreview strings={strings} manifest={manifest} />
        </div>

        {/* Step 5 — ZIP export */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <ZipExport
            strings={strings}
            manifest={manifest}
            takedownDraft={takedownDraft}
            cybercrimeDraft={cybercrimeDraft}
            selectedFile={hashResult?.file ?? null}
            onClearSession={handleClearSession}
          />
        </div>

        {/* Step 6 — Complaint drafts */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <ComplaintDrafts
            strings={strings}
            takedownDraft={takedownDraft}
            cybercrimeDraft={cybercrimeDraft}
            onTakedownChange={setTakedownDraft}
            onCybercrimeChange={setCybercrimeDraft}
            yourName={yourName}
            onYourNameChange={handleNameChange}
          />
        </div>

      </main>

      {/* Footer */}
      <footer className="text-center text-xs text-gray-400 py-6">
        ConsentGuard Rescue Kit — prototype. Not legal advice. All hashing occurs in your browser.
      </footer>
    </div>
  );
}
