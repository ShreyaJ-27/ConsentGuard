/**
 * gatewayClient.test.ts — Unit tests for the PhotoMagic gateway client.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';

describe('gatewayClient — mock mode decisions', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('isMockMode is true when env var is empty', async () => {
    const { isMockMode } = await import('../api/gatewayClient');
    // In test, VITE_GATEWAY_BASE_URL and VITE_MOCK_MODE are not set.
    expect(isMockMode).toBe(true);
  });

  it('returns allow for Tier 0 scope (filter)', async () => {
    const { check } = await import('../api/gatewayClient');
    const result = await check({ prompt: 'Apply a filter', scope: 'filter', user_ref: 'test' });
    expect(result.decision).toBe('allow');
    expect(result.tier).toBe(0);
    expect(result.mocked).toBe(true);
  });

  it('returns needs_consent for Tier 1 scope with real face', async () => {
    const { check } = await import('../api/gatewayClient');
    const result = await check({
      prompt: 'Swap face',
      scope: 'face_swap',
      user_ref: 'test',
      test_signals: { real_face: true, minor_risk: false },
    });
    expect(result.decision).toBe('needs_consent');
    expect(result.tier).toBe(1);
    expect(result.consent_required).toBe(true);
  });

  it('returns allow for Tier 1 scope with no real face', async () => {
    const { check } = await import('../api/gatewayClient');
    const result = await check({
      prompt: 'Animate photo',
      scope: 'photo_animation',
      user_ref: 'test',
      test_signals: { real_face: false, minor_risk: false },
    });
    expect(result.decision).toBe('allow');
  });

  it('returns block for Tier 2 scope (hard block)', async () => {
    const { check } = await import('../api/gatewayClient');
    const result = await check({
      prompt: 'Sexual transformation',
      scope: 'sexual_transformation',
      user_ref: 'test',
    });
    expect(result.decision).toBe('block');
    expect(result.tier).toBe(2);
    expect(result.reasons).toContain('sexual_real_face_hard_block');
  });

  it('returns block for nude_transformation (hard block)', async () => {
    const { check } = await import('../api/gatewayClient');
    const result = await check({
      prompt: 'Nude transformation',
      scope: 'nude_transformation',
      user_ref: 'test',
    });
    expect(result.decision).toBe('block');
    expect(result.tier).toBe(2);
  });

  it('does NOT call fetch in mock mode', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const { check } = await import('../api/gatewayClient');
    await check({ prompt: 'test', scope: 'filter', user_ref: 'test' });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('check_id starts with "c_mock_" in mock mode', async () => {
    const { check } = await import('../api/gatewayClient');
    const result = await check({ prompt: 'test', scope: 'filter', user_ref: 'test' });
    expect(result.check_id).toMatch(/^c_mock_/);
  });

  it('stampOutput returns mocked=true', async () => {
    const { stampOutput } = await import('../api/gatewayClient');
    const result = await stampOutput('c_test_123');
    expect(result.mocked).toBe(true);
    expect(result.check_id).toBe('c_test_123');
    expect(result.label).toContain('mock');
  });

  it('requestConsent returns mocked=true', async () => {
    const { requestConsent } = await import('../api/gatewayClient');
    const result = await requestConsent('c_test_456');
    expect(result.mocked).toBe(true);
    expect(result.request_id).toMatch(/^cr_mock_/);
  });
});

describe('gatewayClient — all three tier outcomes', () => {
  const TIER_0_SCOPES = ['filter', 'lighting', 'crop', 'background'];
  const TIER_2_SCOPES = ['sexual_transformation', 'nude_transformation'];

  for (const scope of TIER_0_SCOPES) {
    it(`${scope} → allow (Tier 0)`, async () => {
      const { check } = await import('../api/gatewayClient');
      const result = await check({ prompt: 'test', scope, user_ref: 'test' });
      expect(result.decision).toBe('allow');
      expect(result.tier).toBe(0);
    });
  }

  for (const scope of TIER_2_SCOPES) {
    it(`${scope} → block (Tier 2)`, async () => {
      const { check } = await import('../api/gatewayClient');
      const result = await check({ prompt: 'test', scope, user_ref: 'test' });
      expect(result.decision).toBe('block');
      expect(result.tier).toBe(2);
    });
  }
});
