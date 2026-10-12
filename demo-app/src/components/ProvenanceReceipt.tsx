/**
 * ProvenanceReceipt.tsx — Output stamping / provenance receipt display.
 * Member 3's endpoint is mocked; clearly labelled.
 */
import { useState, type FC } from 'react';
import { stampOutput } from '../api/gatewayClient';
import type { StampResponse } from '../api/gatewayClient';

interface Props {
  checkId: string;
}

export const ProvenanceReceipt: FC<Props> = ({ checkId }) => {
  const [status, setStatus] = useState<'idle' | 'stamping' | 'done' | 'error'>('idle');
  const [receipt, setReceipt] = useState<StampResponse | null>(null);
  const [error, setError] = useState('');

  const handleStamp = async () => {
    setStatus('stamping');
    try {
      const result = await stampOutput(checkId);
      setReceipt(result);
      setStatus('done');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setStatus('error');
    }
  };

  return (
    <div className="bg-green-50 border border-green-200 rounded-xl p-5 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-2xl">✅</span>
        <div>
          <h3 className="font-semibold text-green-900">Allowed — Provenance Stamping</h3>
          <p className="text-green-800 text-sm">
            The request was allowed. Calling Member 3's output-stamping endpoint.
          </p>
        </div>
      </div>

      {/* Mock placeholder output */}
      <div className="bg-white border border-green-200 rounded-lg p-4 text-center">
        <div className="w-full h-32 bg-gradient-to-br from-green-100 to-teal-100 rounded flex items-center justify-center">
          <span className="text-gray-500 text-sm italic">
            [Harmless cartoon-style placeholder — no explicit-capable generator connected]
          </span>
        </div>
      </div>

      {status === 'idle' && (
        <button
          onClick={handleStamp}
          className="bg-green-600 hover:bg-green-700 text-white text-sm font-semibold px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-400"
        >
          Request Provenance Stamp
        </button>
      )}

      {status === 'stamping' && (
        <p className="text-green-700 text-sm animate-pulse">Requesting provenance stamp…</p>
      )}

      {status === 'done' && receipt && (
        <div className="bg-white border border-green-200 rounded-lg px-4 py-3 space-y-1 text-xs">
          {receipt.mocked && (
            <p className="text-amber-600 font-semibold">
              🟡 MOCK — POST /v1/output/stamp not yet implemented by Member 3.
            </p>
          )}
          <p><strong>Check ID:</strong> {receipt.check_id}</p>
          <p><strong>AI Label:</strong> {receipt.label}</p>
          <p><strong>Provenance ID:</strong> {receipt.provenance_id}</p>
          <p><strong>Stamped at:</strong> {receipt.stamped_at}</p>
        </div>
      )}

      {status === 'error' && (
        <div className="text-red-600 text-sm">
          Stamp failed: {error}
          <button onClick={() => setStatus('idle')} className="ml-2 text-red-500 underline text-xs">
            Retry
          </button>
        </div>
      )}
    </div>
  );
};
