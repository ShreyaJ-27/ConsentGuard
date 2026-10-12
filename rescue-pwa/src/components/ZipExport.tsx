/**
 * ZipExport.tsx — Evidence ZIP download + session clear.
 */
import { useState, useRef, type FC } from 'react';
import { buildEvidenceZip } from '../lib/zip';
import type { ManifestData } from '../lib/manifest';
import type { Strings } from '../i18n/en';

interface Props {
  strings: Strings;
  manifest: ManifestData;
  takedownDraft: string;
  cybercrimeDraft: string;
  selectedFile: File | null;
  onClearSession: () => void;
}

export const ZipExport: FC<Props> = ({
  strings: s,
  manifest,
  takedownDraft,
  cybercrimeDraft,
  selectedFile,
  onClearSession,
}) => {
  const [includeFile, setIncludeFile] = useState(false);
  const [zipUrl, setZipUrl] = useState<string | null>(null);
  const prevZipUrl = useRef<string | null>(null);

  const handleBuildZip = async () => {
    // Revoke previous object URL to free memory.
    if (prevZipUrl.current) {
      URL.revokeObjectURL(prevZipUrl.current);
    }

    let userFiles: Array<{ name: string; data: Uint8Array }> | undefined;

    if (includeFile && selectedFile) {
      const buffer = await selectedFile.arrayBuffer();
      userFiles = [{ name: selectedFile.name, data: new Uint8Array(buffer) }];
    }

    const url = buildEvidenceZip({ manifest, takedownDraft, cybercrimeDraft, userFiles });
    prevZipUrl.current = url;
    setZipUrl(url);
  };

  const handleClearSession = () => {
    if (prevZipUrl.current) {
      URL.revokeObjectURL(prevZipUrl.current);
      prevZipUrl.current = null;
    }
    setZipUrl(null);
    onClearSession();
  };

  return (
    <section className="space-y-4" aria-labelledby="zip-export-heading">
      <h2 id="zip-export-heading" className="text-lg font-semibold text-gray-800">
        {s.zipExport.heading}
      </h2>

      {selectedFile && (
        <div className="flex items-start gap-3">
          <input
            id="include-file"
            type="checkbox"
            checked={includeFile}
            onChange={(e) => setIncludeFile(e.target.checked)}
            className="mt-1 h-4 w-4 text-calm-teal-600 focus:ring-calm-teal-400 border-gray-300 rounded"
          />
          <div>
            <label htmlFor="include-file" className="text-sm text-gray-700 font-medium">
              {s.zipExport.includeFile}
            </label>
            <p className="text-xs text-amber-600 mt-0.5">{s.zipExport.fileWarning}</p>
          </div>
        </div>
      )}

      <button
        onClick={handleBuildZip}
        className="bg-calm-teal-600 hover:bg-calm-teal-700 text-white font-semibold px-5 py-2.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-calm-teal-400"
      >
        Build ZIP
      </button>

      {zipUrl && (
        <a
          href={zipUrl}
          download="evidence-pack.zip"
          className="inline-block bg-green-600 hover:bg-green-700 text-white font-semibold px-5 py-2.5 rounded-xl ml-3 focus:outline-none focus:ring-2 focus:ring-green-400"
        >
          {s.zipExport.downloadButton}
        </a>
      )}

      <div className="pt-4 border-t border-gray-200">
        <button
          onClick={handleClearSession}
          className="text-red-600 hover:text-red-700 text-sm font-medium underline focus:outline-none"
        >
          {s.zipExport.clearSession}
        </button>
        <p className="text-xs text-gray-500 mt-1">{s.zipExport.clearWarning}</p>
      </div>
    </section>
  );
};
