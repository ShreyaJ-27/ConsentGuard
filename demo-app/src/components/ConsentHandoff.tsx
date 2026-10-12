/**
 * ConsentHandoff.tsx — Mock Consent Passport hand-off panel.
 * Clearly labelled as mock until Member 2 implements the flow.
 */
import { useState, type FC } from 'react';
import { requestConsent } from '../api/gatewayClient';

interface Props {
  checkId: string;
  reasons: string[];
}

export const ConsentHandoff: FC<Props> = ({ checkId, reasons }) => {
  const [status, setStatus] = useState<'idle' | 'requesting' | 'done' | 'error'>('idle');
  const [passportUrl, setPassportUrl] = useState('');
  const [requestId, setRequestId] = useState('');
  const [error, setError] = useState('');

  const handleRequestConsent = async () => {
    setStatus('requesting');
    try {
      const result = await requestConsent(checkId);
      setPassportUrl(result.passport_url);
      setRequestId(result.request_id);
      setStatus('done');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setStatus('error');
    }
  };

  return (
    <div className="bg-amber-50 border border-amber-300 rounded-xl p-5 space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-2xl">🔑</span>
        <div>
          <h3 className="font-semibold text-amber-900">Consent Required</h3>
          <p className="text-amber-800 text-sm">
            This edit requires the person in the photo to approve it.
          </p>
        </div>
      </div>

      <div className="bg-amber-100 rounded-lg px-3 py-2 text-xs text-amber-700">
        <strong>Reasons:</strong> {reasons.join(', ')}
      </div>

      {/* Mock badge */}
      <div className="bg-white border border-amber-200 rounded px-3 py-2 text-xs text-amber-700 font-medium">
        🟡 MOCK — Consent Passport flow pending Member 2 integration.
        In production, this would open the Passport PWA for the subject to approve.
      </div>

      {status === 'idle' && (
        <button
          onClick={handleRequestConsent}
          className="bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-400"
        >
          Request Consent
        </button>
      )}

      {status === 'requesting' && (
        <p className="text-amber-700 text-sm animate-pulse">Initiating consent request…</p>
      )}

      {status === 'done' && (
        <div className="space-y-2">
          <p className="text-sm text-green-700 font-medium">
            ✓ Consent request created: <code>{requestId}</code>
          </p>
          <p className="text-sm text-gray-700">
            Open the Consent Passport PWA to simulate subject approval:
          </p>
          <a
            href={passportUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-teal-700 hover:bg-teal-800 text-white font-medium text-xs px-3 py-1.5 rounded"
          >
            Open Consent Passport ({passportUrl}) ↗
          </a>
          <p className="text-xs text-gray-500">
            The Passport PWA allows the simulated subject to inspect the request, approve with demo action code,
            and issue a cryptographically signed consent token.
          </p>
        </div>
      )}


      {status === 'error' && (
        <div className="text-red-600 text-sm">
          Error: {error}
          <button onClick={() => setStatus('idle')} className="ml-2 text-red-500 underline text-xs">
            Retry
          </button>
        </div>
      )}
    </div>
  );
};
