/**
 * manifest.test.ts — Unit tests for manifest builder.
 */
import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { buildManifest, manifestToJsonString, MANIFEST_SCHEMA_VERSION } from '../lib/manifest';
import type { EvidenceItem } from '../lib/manifest';

const ITEM: EvidenceItem = {
  index: 0,
  url: 'https://example.com/fake-post',
  platform: 'TestPlatform',
  observed_at: '2026-10-01T12:00:00',
  notes: 'Saw this content on the platform.',
};

describe('buildManifest', () => {
  beforeAll(() => {
    // Fix time for deterministic created_at
    vi.setSystemTime(new Date('2026-10-12T12:00:00Z'));
  });

  afterAll(() => {
    vi.useRealTimers();
  });

  it('includes correct schema version', () => {
    const m = buildManifest({ evidenceItems: [], appVersion: '0.1.0' });
    expect(m.schema_version).toBe(MANIFEST_SCHEMA_VERSION);
  });

  it('includes tool name', () => {
    const m = buildManifest({ evidenceItems: [] });
    expect(m.tool).toBe('ConsentGuard Rescue Kit');
  });

  it('includes created_at as ISO string', () => {
    const m = buildManifest({ evidenceItems: [] });
    expect(() => new Date(m.created_at)).not.toThrow();
    expect(m.created_at).toBe('2026-10-12T12:00:00.000Z');
  });

  it('includes the disclaimer', () => {
    const m = buildManifest({ evidenceItems: [] });
    expect(m.disclaimer).toContain('not legally admissible');
  });

  it('includes evidence items unchanged', () => {
    const m = buildManifest({ evidenceItems: [ITEM] });
    expect(m.evidence_items).toHaveLength(1);
    expect(m.evidence_items[0].url).toBe('https://example.com/fake-post');
    expect(m.evidence_items[0].platform).toBe('TestPlatform');
  });

  it('includes file_sha256 when provided', () => {
    const m = buildManifest({
      evidenceItems: [],
      fileSha256: 'abc123',
    });
    expect(m.file_sha256).toBe('abc123');
    expect(m.included_fields).toContain('file_sha256');
  });

  it('does NOT include file_sha256 when not provided', () => {
    const m = buildManifest({ evidenceItems: [] });
    expect(m.file_sha256).toBeUndefined();
    expect(m.included_fields).not.toContain('file_sha256');
  });

  it('includes file_dhash when provided', () => {
    const m = buildManifest({ evidenceItems: [], fileDHash: 'deadbeefdeadbeef' });
    expect(m.file_dhash).toBe('deadbeefdeadbeef');
    expect(m.included_fields).toContain('file_dhash');
  });

  it('includes data_sources description', () => {
    const m = buildManifest({ evidenceItems: [] });
    expect(m.data_sources).toContain('user-provided');
    expect(m.data_sources).toContain('tool-computed');
  });

  it('never fabricates evidence items', () => {
    const m = buildManifest({ evidenceItems: [] });
    expect(m.evidence_items).toHaveLength(0);
  });
});

describe('manifestToJsonString', () => {
  it('produces valid JSON', () => {
    const m = buildManifest({ evidenceItems: [ITEM] });
    const json = manifestToJsonString(m);
    expect(() => JSON.parse(json)).not.toThrow();
  });

  it('is pretty-printed (indented)', () => {
    const m = buildManifest({ evidenceItems: [] });
    const json = manifestToJsonString(m);
    expect(json).toContain('\n  ');
  });

  it('round-trips correctly', () => {
    const m = buildManifest({ evidenceItems: [ITEM], fileSha256: 'abc' });
    const parsed = JSON.parse(manifestToJsonString(m));
    expect(parsed.file_sha256).toBe('abc');
    expect(parsed.evidence_items[0].url).toBe('https://example.com/fake-post');
  });
});
