/**
 * OriginLookup.tsx — Optional perceptual hash lookup.
 * Sends ONLY the phash after explicit user confirmation.
 */
import { useState, type FC } from 'react';
import { lookupByPhash, isMockMode } from '../api/lookupClient';
import type { Strings } from '../i18n/en';

interface Props {
  strings: Strings;
  dhash: string | null;
  dhashUnavailable: boolean;
}

type LookupState = 'idle' | 'confirming' | 'checking' | 'match' | 'no-match' | 'error';

export const OriginLookup: FC<Props> = ({ strings: s, dhash, dhashUnavailable }) => {
  const [state, setState] = useState<LookupState>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [provenance, setProvenance] = useState<Partial<import('../api/lookupClient').LookupResult>>({});

  const disabled = dhashUnavailable || dhash === null;

  const handleCheck = async () => {
    if (!dhash) return;
    setState('checking');
    try {
      const result = await lookupByPhash(dhash);
      setProvenance(result);
      setState(result.match ? 'match' : 'no-match');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Unknown error');
      setState('error');
    }
  };


  return (
    <section className="space-y-4" aria-labelledby="origin-lookup-heading">
      <h2 id="origin-lookup-heading" className="text-lg font-semibold text-gray-800">
        {s.originLookup.heading}
      </h2>

      {isMockMode && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 text-amber-700 text-xs font-medium">
          {s.originLookup.mockBadge}
        </div>
      )}

      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-blue-700 text-sm">
        <p>{s.originLookup.notConfirmed}</p>
      </div>

      {disabled ? (
        <p className="text-gray-500 text-sm">{s.originLookup.disabled}</p>
      ) : (
        <>
          <p className="text-gray-600 text-sm">{s.originLookup.explanation}</p>

          {state === 'idle' && (
            <button
              onClick={() => setState('confirming')}
              className="bg-calm-teal-600 hover:bg-calm-teal-700 text-white text-sm font-semibold px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-calm-teal-400"
            >
              {s.originLookup.confirmButton}
            </button>
          )}

          {state === 'confirming' && (
            <div className="bg-yellow-50 border border-yellow-300 rounded-lg px-4 py-3 space-y-3">
              <p className="text-yellow-800 text-sm font-medium">
                Confirm: send only the perceptual hash (not the file) to ConsentGuard?
              </p>
              <div className="flex gap-3">
                <button
                  onClick={handleCheck}
                  className="bg-calm-teal-600 hover:bg-calm-teal-700 text-white text-sm font-semibold px-4 py-2 rounded-lg"
                >
                  {s.originLookup.confirmButton}
                </button>
                <button
                  onClick={() => setState('idle')}
                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-semibold px-4 py-2 rounded-lg"
                >
                  {s.originLookup.cancelButton}
                </button>
              </div>
            </div>
          )}

          {state === 'checking' && (
            <p className="text-calm-teal-600 text-sm animate-pulse">{s.originLookup.checking}</p>
          )}

          {state === 'match' && (
            <div className="bg-orange-50 border border-orange-200 rounded-lg px-4 py-3 space-y-1">
              <p className="text-orange-800 text-sm font-medium">{s.originLookup.resultMatch}</p>
              {provenance.check_id && (
                <p className="text-orange-700 text-xs"><strong>Check ID:</strong> {provenance.check_id}</p>
              )}
              {provenance.label && (
                <p className="text-orange-700 text-xs"><strong>Label:</strong> {provenance.label}</p>
              )}
              {provenance.matched_at && (
                <p className="text-orange-700 text-xs"><strong>Stamped At:</strong> {provenance.matched_at}</p>
              )}
              {provenance.output_sha256 && (
                <p className="text-orange-700 text-xs break-all"><strong>Output SHA-256:</strong> {provenance.output_sha256}</p>
              )}
            </div>
          )}

          {state === 'no-match' && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3">
              <p className="text-gray-700 text-sm">{s.originLookup.resultNoMatch}</p>
            </div>
          )}

          {state === 'error' && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3">
              <p className="text-red-700 text-sm">
                {s.originLookup.resultError}: {errorMessage}
              </p>
              <button
                onClick={() => setState('idle')}
                className="text-red-600 text-xs underline mt-1"
              >
                {s.common.retry}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
};
