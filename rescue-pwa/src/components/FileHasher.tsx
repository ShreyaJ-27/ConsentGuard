/**
 * FileHasher.tsx — File selector with browser-side SHA-256 + dHash.
 * The selected file is NEVER sent anywhere by this component.
 */
import { useRef, useState, type FC } from 'react';
import { computeSha256, computeDHash } from '../lib/hash';
import type { Strings } from '../i18n/en';

export interface HashResult {
  file: File;
  sha256: string;
  dhash: string | null;
  dhashUnavailable: boolean;
}

interface Props {
  strings: Strings;
  onHashComplete: (result: HashResult) => void;
}

export const FileHasher: FC<Props> = ({ strings: s, onHashComplete }) => {
  const [hashing, setHashing] = useState(false);
  const [result, setResult] = useState<HashResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setHashing(true);
    setError(null);
    setResult(null);

    try {
      const sha256 = await computeSha256(file);
      const isImage = file.type.startsWith('image/');
      let dhash: string | null = null;
      let dhashUnavailable = false;

      if (isImage) {
        try {
          dhash = await computeDHash(file);
          if (dhash === null) dhashUnavailable = true;
        } catch {
          dhashUnavailable = true;
        }
      } else {
        dhashUnavailable = true;
      }

      const hashResult: HashResult = { file, sha256, dhash, dhashUnavailable };
      setResult(hashResult);
      onHashComplete(hashResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Hashing failed.');
    } finally {
      setHashing(false);
    }
  };

  return (
    <section className="space-y-4" aria-labelledby="file-hasher-heading">
      <h2 id="file-hasher-heading" className="text-lg font-semibold text-gray-800">
        {s.fileHasher.heading}
      </h2>
      <p className="text-gray-600 text-sm">{s.fileHasher.instruction}</p>

      <div>
        <label htmlFor="file-input" className="sr-only">{s.fileHasher.chooseFile}</label>
        <input
          id="file-input"
          ref={inputRef}
          type="file"
          accept="image/*,video/*"
          onChange={handleFileChange}
          disabled={hashing}
          className="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-calm-teal-100 file:text-calm-teal-700 hover:file:bg-calm-teal-200 cursor-pointer focus:outline-none focus:ring-2 focus:ring-calm-teal-400"
        />
      </div>

      {hashing && (
        <p className="text-calm-teal-600 text-sm animate-pulse">{s.fileHasher.hashing}</p>
      )}

      {error && (
        <p role="alert" className="text-red-600 text-sm">{error}</p>
      )}

      {result && (
        <div className="bg-gray-50 rounded-lg p-4 space-y-3 text-sm">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              {s.fileHasher.sha256Label}
            </p>
            <code className="break-all text-gray-800 font-mono text-xs">{result.sha256}</code>
          </div>

          {result.dhash && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {s.fileHasher.dhashLabel}
              </p>
              <code className="break-all text-gray-800 font-mono text-xs">{result.dhash}</code>
            </div>
          )}

          {result.dhashUnavailable && (
            <p className="text-amber-600 text-xs">
              {result.file.type.startsWith('image/')
                ? s.fileHasher.dhashUnavailable
                : s.fileHasher.notAnImage}
            </p>
          )}

          <p className="text-green-700 text-xs font-medium">✓ {s.fileHasher.privacy}</p>
        </div>
      )}
    </section>
  );
};
