/**
 * ModeBadge.tsx — Always-visible API mode badge.
 * Live and mock modes are visually distinct; never confused.
 */
import type { FC } from 'react';
import { isMockMode } from '../api/gatewayClient';

export const ModeBadge: FC = () => {
  if (isMockMode) {
    return (
      <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 text-xs font-semibold px-2.5 py-0.5 rounded-full border border-amber-300">
        🟡 MOCK MODE — simulated responses
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 bg-green-100 text-green-800 text-xs font-semibold px-2.5 py-0.5 rounded-full border border-green-300">
      🟢 LIVE — connected to gateway
    </span>
  );
};
