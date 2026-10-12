/**
 * DecisionPanel.tsx — Renders the gateway decision honestly.
 * Shows allow, needs_consent, and block with appropriate UI.
 */
import type { FC } from 'react';
import type { CheckResponse } from '../api/gatewayClient';
import { ConsentHandoff } from './ConsentHandoff';
import { ProvenanceReceipt } from './ProvenanceReceipt';

interface Props {
  response: CheckResponse;
}

export const DecisionPanel: FC<Props> = ({ response }) => {
  const { decision, check_id, tier, reasons, request_risk, mocked } = response;

  return (
    <div className="space-y-4">
      {/* Mock badge on the response */}
      {mocked && (
        <div className="bg-amber-50 border border-amber-200 rounded px-3 py-1.5 text-xs text-amber-700 font-medium">
          🟡 MOCK RESPONSE — gateway not connected. Set VITE_GATEWAY_BASE_URL to go live.
        </div>
      )}

      {/* Check metadata */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 text-xs space-y-1 font-mono text-gray-600">
        <p><strong>check_id:</strong> {check_id}</p>
        <p><strong>tier:</strong> {tier}</p>
        <p><strong>reasons:</strong> {reasons.join(', ')}</p>
        <p><strong>risk_score:</strong> {request_risk.score} ({request_risk.source})</p>
      </div>

      {/* Decision rendering */}
      {decision === 'allow' && (
        <ProvenanceReceipt checkId={check_id} />
      )}

      {decision === 'needs_consent' && (
        <ConsentHandoff checkId={check_id} reasons={reasons} />
      )}

      {decision === 'block' && (
        <div className="bg-red-50 border border-red-300 rounded-xl p-5 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🚫</span>
            <div>
              <h3 className="font-semibold text-red-900">Blocked</h3>
              <p className="text-red-800 text-sm">
                This request was blocked by the ConsentGuard gateway.
              </p>
            </div>
          </div>
          <div className="bg-red-100 rounded px-3 py-2 text-xs text-red-700">
            <strong>Reason codes:</strong> {reasons.join(', ')}
          </div>
          <p className="text-xs text-red-600">
            Tier 2 edits (sexual/nude transformation) are always hard-blocked for real faces.
            No consent route exists for Tier 2.
          </p>
        </div>
      )}
    </div>
  );
};
