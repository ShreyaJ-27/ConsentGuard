/**
 * ScopeSelector.tsx — Structured edit-scope selection.
 * Maps to gateway Scope enum values with human-readable labels and tier info.
 */
import type { FC } from 'react';

export interface ScopeOption {
  value: string;
  label: string;
  tier: 0 | 1 | 2;
  description: string;
}

export const SCOPE_OPTIONS: ScopeOption[] = [
  {
    value: 'filter',
    label: 'Apply a style filter',
    tier: 0,
    description: 'Cartoon / watercolour / sketch style — Tier 0 (benign)',
  },
  {
    value: 'lighting',
    label: 'Adjust lighting',
    tier: 0,
    description: 'Brightness, contrast, colour balance — Tier 0 (benign)',
  },
  {
    value: 'crop',
    label: 'Crop / resize',
    tier: 0,
    description: 'Crop and resize only — Tier 0 (benign)',
  },
  {
    value: 'background',
    label: 'Replace background',
    tier: 0,
    description: 'Background removal or replacement — Tier 0 (benign)',
  },
  {
    value: 'face_swap',
    label: 'Face swap',
    tier: 1,
    description: 'Replace a face — Tier 1 (requires consent)',
  },
  {
    value: 'photo_animation',
    label: 'Animate photo',
    tier: 1,
    description: 'Make a still photo appear to move — Tier 1 (requires consent)',
  },
  {
    value: 'body_edit',
    label: 'Body edit',
    tier: 1,
    description: 'Edit body proportions — Tier 1 (requires consent)',
  },
  {
    value: 'voice_clone',
    label: 'Voice clone',
    tier: 1,
    description: 'Clone a voice — Tier 1 (requires consent)',
  },
  {
    value: 'sexual_transformation',
    label: 'Sexual transformation',
    tier: 2,
    description: 'Hard-blocked — Tier 2 (always blocked for real faces)',
  },
  {
    value: 'nude_transformation',
    label: 'Nude transformation',
    tier: 2,
    description: 'Hard-blocked — Tier 2 (always blocked for real faces)',
  },
];

const tierColour: Record<0 | 1 | 2, string> = {
  0: 'text-green-600',
  1: 'text-amber-600',
  2: 'text-red-600',
};

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export const ScopeSelector: FC<Props> = ({ value, onChange }) => {
  const selected = SCOPE_OPTIONS.find((o) => o.value === value);

  return (
    <div className="space-y-2">
      <label htmlFor="scope-select" className="block text-sm font-medium text-gray-700">
        Edit type / scope
      </label>
      <select
        id="scope-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
      >
        {SCOPE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            [{`Tier ${opt.tier}`}] {opt.label}
          </option>
        ))}
      </select>
      {selected && (
        <p className={`text-xs ${tierColour[selected.tier]}`}>{selected.description}</p>
      )}
    </div>
  );
};
