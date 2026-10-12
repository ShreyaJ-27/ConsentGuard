/**
 * zip.ts — Client-side ZIP builder using fflate.
 *
 * Creates the downloadable evidence ZIP in the browser without uploading
 * anything to a server.
 *
 * Contents:
 *   - manifest.json
 *   - summary.txt
 *   - drafts/takedown-request.txt
 *   - drafts/cybercrime-complaint.txt
 *
 * Files selected for inclusion by the user are added only when explicitly
 * requested; the user is informed of their inclusion before export.
 */

import { zipSync, strToU8 } from 'fflate';
import type { ManifestData } from './manifest';

export interface ZipContents {
  manifest: ManifestData;
  takedownDraft: string;
  cybercrimeDraft: string;
  /** Optional user files to include when explicitly selected */
  userFiles?: Array<{ name: string; data: Uint8Array }>;
}

/**
 * Build a ZIP blob client-side and return an object URL.
 * Caller is responsible for calling URL.revokeObjectURL() when done.
 */
export function buildEvidenceZip(contents: ZipContents): string {
  const { manifest, takedownDraft, cybercrimeDraft, userFiles } = contents;

  const summary = buildSummaryText(manifest);

  const files: Record<string, Uint8Array> = {
    'manifest.json': strToU8(JSON.stringify(manifest, null, 2)),
    'summary.txt': strToU8(summary),
    'drafts/takedown-request.txt': strToU8(takedownDraft),
    'drafts/cybercrime-complaint.txt': strToU8(cybercrimeDraft),
    'README.txt': strToU8(buildReadme()),
  };

  if (userFiles) {
    for (const { name, data } of userFiles) {
      files[`evidence/${name}`] = data;
    }
  }

  const zipped = zipSync(files, { level: 6 });
  const blob = new Blob([zipped], { type: 'application/zip' });
  return URL.createObjectURL(blob);
}

function buildSummaryText(manifest: ManifestData): string {
  const lines: string[] = [
    '=== ConsentGuard Rescue Kit — Evidence Summary ===',
    '',
    'DISCLAIMER: This summary is a collection aid. It has not been reviewed by',
    'a lawyer and is not legally admissible on its own.',
    '',
    `Generated: ${manifest.created_at}`,
    `Tool: ${manifest.tool} v${manifest.tool_version}`,
    '',
    '--- Evidence Items ---',
  ];

  for (const item of manifest.evidence_items) {
    lines.push('');
    lines.push(`Item ${item.index + 1}:`);
    lines.push(`  Platform:     ${item.platform || '(not provided)'}`);
    lines.push(`  URL:          ${item.url || '(not provided)'}`);
    lines.push(`  Observed at:  ${item.observed_at || '(not provided)'}`);
    if (item.sha256) lines.push(`  SHA-256:      ${item.sha256}`);
    if (item.dhash) lines.push(`  dHash:        ${item.dhash} [PLACEHOLDER format — verify with Member 3]`);
    if (item.notes) lines.push(`  Notes:        ${item.notes}`);
  }

  if (manifest.file_sha256) {
    lines.push('');
    lines.push('--- Selected File ---');
    lines.push(`  Filename: ${manifest.selected_filename ?? '(unnamed)'}`);
    lines.push(`  SHA-256:  ${manifest.file_sha256}`);
    if (manifest.file_dhash) {
      lines.push(`  dHash:    ${manifest.file_dhash} [PLACEHOLDER format — pending Member 3 confirmation]`);
    }
  }

  lines.push('');
  lines.push('--- Helplines ---');
  lines.push('  National Cyber Helpline: 1930');
  lines.push('  Meri Trustline: 6363176363');
  lines.push('  Cybercrime Portal: cybercrime.gov.in');
  lines.push('  iCall: 9152987821');

  return lines.join('\n');
}

function buildReadme(): string {
  return `ConsentGuard Rescue Kit — Evidence Pack
=========================================

This ZIP was created by the ConsentGuard Rescue Kit browser tool.

IMPORTANT LIMITATIONS:
- This pack is a collection aid and is NOT guaranteed to be legally admissible.
- It has not been timestamped by an RFC 3161 Time Stamp Authority.
- It has not been reviewed by a lawyer.
- Do not share this file without consulting a legal professional.
- The SHA-256 hashes were computed in your browser and have not been
  independently verified.

FILES IN THIS PACK:
- manifest.json          Full evidence manifest with schema and field sources
- summary.txt            Human-readable summary
- drafts/               Editable complaint drafts (review before use)
- evidence/             Any files you explicitly chose to include
- README.txt            This file

HELPLINES:
- National Cyber Helpline: 1930
- Meri Trustline (emotional support): 6363176363
- Cybercrime Portal: cybercrime.gov.in
- iCall: 9152987821
`;
}
