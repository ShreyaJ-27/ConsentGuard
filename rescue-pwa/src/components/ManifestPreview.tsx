/**
 * ManifestPreview.tsx — Reviewable manifest preview before export.
 */
import { type FC } from 'react';
import type { ManifestData } from '../lib/manifest';
import type { Strings } from '../i18n/en';

interface Props {
  strings: Strings;
  manifest: ManifestData;
}

export const ManifestPreview: FC<Props> = ({ strings: s, manifest }) => {
  return (
    <section className="space-y-4" aria-labelledby="manifest-preview-heading">
      <h2 id="manifest-preview-heading" className="text-lg font-semibold text-gray-800">
        {s.manifestPreview.heading}
      </h2>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 text-yellow-800 text-xs">
        {s.manifestPreview.disclaimer}
      </div>

      <p className="text-gray-600 text-sm">{s.manifestPreview.description}</p>

      <pre className="bg-gray-900 text-green-300 rounded-xl p-4 text-xs overflow-auto max-h-80 font-mono leading-relaxed">
        {JSON.stringify(manifest, null, 2)}
      </pre>
    </section>
  );
};
