/**
 * ComplaintDrafts.tsx — Editable complaint drafts with visible disclaimer.
 */
import { useState, type FC } from 'react';
import type { Strings } from '../i18n/en';

interface Props {
  strings: Strings;
  takedownDraft: string;
  cybercrimeDraft: string;
  onTakedownChange: (text: string) => void;
  onCybercrimeChange: (text: string) => void;
  yourName: string;
  onYourNameChange: (name: string) => void;
}

export const ComplaintDrafts: FC<Props> = ({
  strings: s,
  takedownDraft,
  cybercrimeDraft,
  onTakedownChange,
  onCybercrimeChange,
  yourName,
  onYourNameChange,
}) => {
  const [activeTab, setActiveTab] = useState<'takedown' | 'cybercrime'>('takedown');
  const [copiedTakedown, setCopiedTakedown] = useState(false);
  const [copiedCybercrime, setCopiedCybercrime] = useState(false);

  const copyToClipboard = async (text: string, type: 'takedown' | 'cybercrime') => {
    try {
      await navigator.clipboard.writeText(text);
      if (type === 'takedown') {
        setCopiedTakedown(true);
        setTimeout(() => setCopiedTakedown(false), 2000);
      } else {
        setCopiedCybercrime(true);
        setTimeout(() => setCopiedCybercrime(false), 2000);
      }
    } catch {
      // Clipboard API not available — ignore silently.
    }
  };

  return (
    <section className="space-y-4" aria-labelledby="complaints-heading">
      <h2 id="complaints-heading" className="text-lg font-semibold text-gray-800">
        {s.complaints.heading}
      </h2>

      {/* Disclaimer — always visible */}
      <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-800 text-xs font-semibold">
        ⚠ {s.complaints.disclaimer}
      </div>

      {/* Your name */}
      <div>
        <label htmlFor="your-name" className="block text-sm font-medium text-gray-700 mb-1">
          {s.complaints.yourNameLabel}
        </label>
        <input
          id="your-name"
          type="text"
          value={yourName}
          onChange={(e) => onYourNameChange(e.target.value)}
          placeholder={s.complaints.yourNamePlaceholder}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-calm-teal-400"
        />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab('takedown')}
          className={`px-4 py-2 text-sm font-medium focus:outline-none ${
            activeTab === 'takedown'
              ? 'border-b-2 border-calm-teal-500 text-calm-teal-700'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          aria-selected={activeTab === 'takedown'}
          role="tab"
        >
          {s.complaints.takedownTab}
        </button>
        <button
          onClick={() => setActiveTab('cybercrime')}
          className={`px-4 py-2 text-sm font-medium focus:outline-none ${
            activeTab === 'cybercrime'
              ? 'border-b-2 border-calm-teal-500 text-calm-teal-700'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          aria-selected={activeTab === 'cybercrime'}
          role="tab"
        >
          {s.complaints.cybercrimeTab}
        </button>
      </div>

      {/* Draft editor */}
      {activeTab === 'takedown' && (
        <div className="space-y-2">
          <p className="text-xs text-gray-500">{s.complaints.editNote}</p>
          <textarea
            value={takedownDraft}
            onChange={(e) => onTakedownChange(e.target.value)}
            rows={18}
            aria-label={s.complaints.takedownTab}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-calm-teal-400 resize-y"
          />
          <button
            onClick={() => copyToClipboard(takedownDraft, 'takedown')}
            className="text-sm text-calm-teal-600 hover:text-calm-teal-800 font-medium"
          >
            {copiedTakedown ? s.complaints.copied : s.complaints.copyButton}
          </button>
        </div>
      )}

      {activeTab === 'cybercrime' && (
        <div className="space-y-2">
          <p className="text-xs text-gray-500">{s.complaints.editNote}</p>
          <textarea
            value={cybercrimeDraft}
            onChange={(e) => onCybercrimeChange(e.target.value)}
            rows={22}
            aria-label={s.complaints.cybercrimeTab}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-calm-teal-400 resize-y"
          />
          <button
            onClick={() => copyToClipboard(cybercrimeDraft, 'cybercrime')}
            className="text-sm text-calm-teal-600 hover:text-calm-teal-800 font-medium"
          >
            {copiedCybercrime ? s.complaints.copied : s.complaints.copyButton}
          </button>
        </div>
      )}
    </section>
  );
};
