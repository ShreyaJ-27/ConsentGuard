/**
 * App.tsx — PhotoMagic demo application.
 * Demonstrates all three gateway decisions: allow, needs_consent, block.
 */
import { useState } from 'react';
import { ModeBadge } from './components/ModeBadge';
import { ScopeSelector } from './components/ScopeSelector';
import { DecisionPanel } from './components/DecisionPanel';
import { check } from './api/gatewayClient';
import type { CheckResponse } from './api/gatewayClient';

type AppState = 'idle' | 'checking' | 'result' | 'error';

// Harmless fixture descriptions — no explicit images
const FIXTURES = [
  { id: 'portrait', label: 'Portrait photo (person present)' },
  { id: 'landscape', label: 'Landscape / scenery (no person)' },
  { id: 'group', label: 'Group photo (multiple people)' },
];

export default function App() {
  const [fixture, setFixture] = useState('portrait');
  const [scope, setScope] = useState('filter');
  const [prompt, setPrompt] = useState('Apply a cartoon filter to the image');
  const [appState, setAppState] = useState<AppState>('idle');
  const [response, setResponse] = useState<CheckResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const handleCheck = async () => {
    setAppState('checking');
    setResponse(null);
    setErrorMsg('');

    try {
      // For demo purposes, real_face is true for portraits, false for landscapes.
      // In production, face detection would be server-side.
      const hasRealFace = fixture === 'portrait' || fixture === 'group';
      const result = await check({
        prompt,
        scope,
        user_ref: 'photomagic-demo-user',
        // Demo-only test signals — only used when CONSENTGUARD_ENABLE_TEST_SIGNALS=true
        test_signals: { real_face: hasRealFace, minor_risk: false },
      });
      setResponse(result);
      setAppState('result');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Unknown error');
      setAppState('error');
    }
  };

  const handleReset = () => {
    setAppState('idle');
    setResponse(null);
    setErrorMsg('');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-blue-700 text-white px-4 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">PhotoMagic</h1>
          <p className="text-blue-200 text-xs">ConsentGuard End-to-End Demo</p>
        </div>
        <ModeBadge />
      </header>

      <main className="max-w-xl mx-auto px-4 py-8 space-y-6">
        {/* Safety notice */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-blue-800 text-sm">
          <strong>Demo only.</strong> This demonstrates the ConsentGuard gateway decision flow.
          No real images are processed. No explicit-capable generator is connected.
        </div>

        {/* Request form */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Submit a Request</h2>

          {/* Fixture selector */}
          <div>
            <label htmlFor="fixture-select" className="block text-sm font-medium text-gray-700 mb-1">
              Image fixture (harmless demo placeholder)
            </label>
            <select
              id="fixture-select"
              value={fixture}
              onChange={(e) => setFixture(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              {FIXTURES.map((f) => (
                <option key={f.id} value={f.id}>{f.label}</option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Portrait/Group → face_detected=true. Landscape → face_detected=false.
              (Demo signals only — not real face detection.)
            </p>
          </div>

          {/* Scope selector */}
          <ScopeSelector value={scope} onChange={setScope} />

          {/* Prompt */}
          <div>
            <label htmlFor="prompt-input" className="block text-sm font-medium text-gray-700 mb-1">
              Request description
            </label>
            <input
              id="prompt-input"
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              maxLength={4000}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <p className="text-xs text-gray-500 mt-1">
              The gateway uses the structured <code>scope</code> field, not prompt text, for tier routing.
            </p>
          </div>

          {/* Submit */}
          <button
            onClick={handleCheck}
            disabled={appState === 'checking' || !prompt.trim()}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-semibold py-2.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-400 transition-colors"
          >
            {appState === 'checking' ? 'Checking…' : 'Submit to ConsentGuard'}
          </button>
        </div>

        {/* Error */}
        {appState === 'error' && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3">
            <p className="text-red-700 text-sm font-medium">Gateway error: {errorMsg}</p>
            <p className="text-red-600 text-xs mt-1">
              Is the gateway running? Check VITE_GATEWAY_BASE_URL in .env.
            </p>
            <button onClick={handleReset} className="text-red-500 text-sm underline mt-2">
              Try again
            </button>
          </div>
        )}

        {/* Decision result */}
        {appState === 'result' && response && (
          <div className="space-y-4">
            <DecisionPanel response={response} />
            <button
              onClick={handleReset}
              className="text-blue-600 hover:text-blue-800 text-sm underline"
            >
              Try another request
            </button>
          </div>
        )}

        {/* All three outcomes guide */}
        <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-xs text-gray-600">
          <p className="font-semibold mb-2">Try all three gateway outcomes:</p>
          <ul className="space-y-1">
            <li>🟢 <strong>Allow</strong> — Landscape + any Tier 0 scope (filter, crop…)</li>
            <li>🟡 <strong>Needs consent</strong> — Portrait + Tier 1 scope (face_swap, body_edit…)</li>
            <li>🔴 <strong>Block</strong> — Any fixture + Tier 2 scope (sexual/nude transformation)</li>
          </ul>
        </div>
      </main>
    </div>
  );
}
