/**
 * drafts.test.ts — Unit tests for complaint draft templates.
 */
import { describe, it, expect } from 'vitest';
import {
  buildTakedownDraft,
  buildCybercrimeComplaintDraft,
  DRAFT_DISCLAIMER,
} from '../lib/drafts';

describe('DRAFT_DISCLAIMER', () => {
  it('contains "NOT LEGAL ADVICE"', () => {
    expect(DRAFT_DISCLAIMER).toContain('NOT LEGAL ADVICE');
  });

  it('instructs user to review before submitting', () => {
    expect(DRAFT_DISCLAIMER).toContain('Review all details before submitting');
  });
});

describe('buildTakedownDraft', () => {
  it('starts with the disclaimer', () => {
    const draft = buildTakedownDraft({});
    expect(draft.startsWith(DRAFT_DISCLAIMER)).toBe(true);
  });

  it('includes placeholders for missing fields', () => {
    const draft = buildTakedownDraft({});
    expect(draft).toContain('[');
    expect(draft).toContain('please fill in');
  });

  it('includes provided platform name', () => {
    const draft = buildTakedownDraft({ platform: 'Instagram' });
    expect(draft).toContain('Instagram');
  });

  it('includes provided content URL', () => {
    const draft = buildTakedownDraft({ contentUrl: 'https://example.com/bad-post' });
    expect(draft).toContain('https://example.com/bad-post');
  });

  it('includes SHA-256 when provided', () => {
    const draft = buildTakedownDraft({ fileSha256: 'abc123def456' });
    expect(draft).toContain('abc123def456');
  });

  it('does NOT invent SHA-256 when not provided', () => {
    const draft = buildTakedownDraft({});
    // Should not contain a hex string that looks like an invented hash
    expect(draft).not.toMatch(/SHA-256.*: [0-9a-f]{64}/);
  });

  it('includes name when provided', () => {
    const draft = buildTakedownDraft({ yourName: 'Priya Sharma' });
    expect(draft).toContain('Priya Sharma');
  });

  it('does not auto-submit or include submission mechanism', () => {
    const draft = buildTakedownDraft({});
    // Should be text only — no URLs to auto-submit to, no base64 data
    expect(draft).not.toContain('fetch(');
    expect(draft).not.toContain('XMLHttpRequest');
  });

  it('includes the note about verifying contact info', () => {
    const draft = buildTakedownDraft({});
    expect(draft).toContain('independently verified');
  });
});

describe('buildCybercrimeComplaintDraft', () => {
  it('starts with the disclaimer', () => {
    const draft = buildCybercrimeComplaintDraft({});
    expect(draft.startsWith(DRAFT_DISCLAIMER)).toBe(true);
  });

  it('references cybercrime.gov.in', () => {
    const draft = buildCybercrimeComplaintDraft({});
    expect(draft).toContain('cybercrime.gov.in');
  });

  it('includes helpline 1930', () => {
    const draft = buildCybercrimeComplaintDraft({});
    expect(draft).toContain('1930');
  });

  it('includes Meri Trustline number', () => {
    const draft = buildCybercrimeComplaintDraft({});
    expect(draft).toContain('6363176363');
  });

  it('includes placeholders for missing suspect details', () => {
    const draft = buildCybercrimeComplaintDraft({});
    expect(draft).toContain('[Suspect name or "Unknown"');
  });

  it('includes iCall number', () => {
    const draft = buildCybercrimeComplaintDraft({});
    expect(draft).toContain('9152987821');
  });

  it('includes SHA-256 when provided', () => {
    const draft = buildCybercrimeComplaintDraft({ fileSha256: 'deadbeef12345678' });
    expect(draft).toContain('deadbeef12345678');
  });

  it('labels SHA-256 as browser-computed (not server-computed)', () => {
    const draft = buildCybercrimeComplaintDraft({ fileSha256: 'abc' });
    expect(draft).toContain('browser-computed');
  });

  it('does NOT claim to be a filed complaint', () => {
    const draft = buildCybercrimeComplaintDraft({});
    expect(draft).toContain('does not constitute a filed complaint');
  });
});
