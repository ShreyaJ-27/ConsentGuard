/**
 * EvidenceForm.tsx — Multi-item evidence metadata form.
 * All fields are user-provided and clearly labelled as such.
 */
import { type FC } from 'react';
import type { Strings } from '../i18n/en';
import type { EvidenceItem } from '../lib/manifest';

interface Props {
  strings: Strings;
  items: EvidenceItem[];
  onChange: (items: EvidenceItem[]) => void;
}

function emptyItem(index: number): EvidenceItem {
  return { index, url: '', platform: '', observed_at: '', notes: '' };
}

export const EvidenceForm: FC<Props> = ({ strings: s, items, onChange }) => {
  const addItem = () => {
    onChange([...items, emptyItem(items.length)]);
  };

  const removeItem = (idx: number) => {
    const updated = items.filter((_, i) => i !== idx).map((item, i) => ({ ...item, index: i }));
    onChange(updated);
  };

  const updateItem = (idx: number, field: keyof EvidenceItem, value: string) => {
    const updated = items.map((item, i) =>
      i === idx ? { ...item, [field]: value } : item
    );
    onChange(updated);
  };

  return (
    <section className="space-y-4" aria-labelledby="evidence-form-heading">
      <h2 id="evidence-form-heading" className="text-lg font-semibold text-gray-800">
        {s.evidenceForm.heading}
      </h2>

      <p className="text-xs text-gray-500 italic">{s.evidenceForm.userProvidedNote}</p>

      {items.map((item, idx) => (
        <div key={idx} className="border border-gray-200 rounded-xl p-4 space-y-3 bg-gray-50">
          <div className="flex justify-between items-center">
            <span className="text-sm font-semibold text-gray-600">Item {idx + 1}</span>
            <button
              onClick={() => removeItem(idx)}
              className="text-xs text-red-500 hover:text-red-700 focus:outline-none focus:ring-1 focus:ring-red-400 rounded"
              aria-label={`${s.evidenceForm.removeItem} item ${idx + 1}`}
            >
              {s.evidenceForm.removeItem}
            </button>
          </div>

          {/* URL */}
          <div>
            <label htmlFor={`url-${idx}`} className="block text-xs font-medium text-gray-600 mb-1">
              {s.evidenceForm.urlLabel}
            </label>
            <input
              id={`url-${idx}`}
              type="url"
              value={item.url}
              onChange={(e) => updateItem(idx, 'url', e.target.value)}
              placeholder={s.evidenceForm.urlPlaceholder}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-calm-teal-400"
            />
          </div>

          {/* Platform */}
          <div>
            <label htmlFor={`platform-${idx}`} className="block text-xs font-medium text-gray-600 mb-1">
              {s.evidenceForm.platformLabel}
            </label>
            <input
              id={`platform-${idx}`}
              type="text"
              value={item.platform}
              onChange={(e) => updateItem(idx, 'platform', e.target.value)}
              placeholder={s.evidenceForm.platformPlaceholder}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-calm-teal-400"
            />
          </div>

          {/* Observed at */}
          <div>
            <label htmlFor={`observed-${idx}`} className="block text-xs font-medium text-gray-600 mb-1">
              {s.evidenceForm.observedAtLabel}
            </label>
            <input
              id={`observed-${idx}`}
              type="datetime-local"
              value={item.observed_at}
              onChange={(e) => updateItem(idx, 'observed_at', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-calm-teal-400"
            />
          </div>

          {/* Notes */}
          <div>
            <label htmlFor={`notes-${idx}`} className="block text-xs font-medium text-gray-600 mb-1">
              {s.evidenceForm.notesLabel}
            </label>
            <textarea
              id={`notes-${idx}`}
              value={item.notes}
              onChange={(e) => updateItem(idx, 'notes', e.target.value)}
              placeholder={s.evidenceForm.notesPlaceholder}
              rows={3}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-calm-teal-400 resize-y"
            />
          </div>
        </div>
      ))}

      <button
        onClick={addItem}
        className="text-calm-teal-600 hover:text-calm-teal-800 text-sm font-semibold border border-calm-teal-300 hover:border-calm-teal-500 px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-calm-teal-400"
      >
        + {s.evidenceForm.addItem}
      </button>
    </section>
  );
};
