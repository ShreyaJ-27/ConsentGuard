/**
 * QuickExit.tsx — Quick-exit button with honest warning.
 * Navigates to a neutral site. CANNOT erase browser history or network logs.
 */
import type { FC } from 'react';

interface Props {
  label: string;
  warning: string;
}

export const QuickExit: FC<Props> = ({ label, warning }) => {
  const handleExit = () => {
    // Replace current history entry so Back doesn't return here.
    window.location.replace('https://www.google.com');
  };

  return (
    <div className="fixed top-3 right-3 z-50">
      <button
        onClick={handleExit}
        title={warning}
        aria-label={`${label} — ${warning}`}
        className="bg-red-600 hover:bg-red-700 text-white text-sm font-semibold px-3 py-1.5 rounded shadow-md focus:outline-none focus:ring-2 focus:ring-red-400"
      >
        {label} ✕
      </button>
    </div>
  );
};
