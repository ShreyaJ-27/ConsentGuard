/**
 * gatewayClient.ts — API client for the ConsentGuard gateway.
 *
 * Handles:
 *  - POST /v1/check  (Member 1)
 *  - POST /v1/output/stamp  (Member 3 — mocked until implemented)
 *  - Mock consent request hand-off (Member 2 — mocked until implemented)
 *
 * SECURITY NOTE: The API key is exposed in this browser bundle.
 * This is a PROTOTYPE pattern only. Production requires a backend proxy.
 */

const RAW_BASE = import.meta.env.VITE_GATEWAY_BASE_URL as string | undefined;
const API_KEY = import.meta.env.VITE_GATEWAY_API_KEY as string | undefined;
const FORCE_MOCK = import.meta.env.VITE_MOCK_MODE === 'true';

/** True when no gateway URL is configured or mock mode is forced. */
export const isMockMode = FORCE_MOCK || !RAW_BASE || RAW_BASE.trim() === '';

const BASE_URL = RAW_BASE?.replace(/\/$/, '') ?? '';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Decision = 'allow' | 'needs_consent' | 'block';

export interface CheckRequest {
  prompt: string;
  scope: string;
  user_ref: string;
  /** Optional: demo-only test signals (requires CONSENTGUARD_ENABLE_TEST_SIGNALS=true on server) */
  test_signals?: { real_face?: boolean; minor_risk?: boolean };
}

export interface RequestRisk {
  score: number;
  label: string;
  source: string;
}

export interface CheckResponse {
  check_id: string;
  decision: Decision;
  tier: number;
  reasons: string[];
  consent_required: boolean;
  request_risk: RequestRisk;
  /** True when this is a mock response */
  mocked: boolean;
}

export interface StampResponse {
  check_id: string;
  label: string;
  provenance_id: string;
  stamped_at: string;
  mocked: boolean;
}

// ---------------------------------------------------------------------------
// POST /v1/check
// ---------------------------------------------------------------------------

/**
 * Send a check request to the gateway.
 * In mock mode, returns a simulated response based on scope without network call.
 */
export async function check(req: CheckRequest): Promise<CheckResponse> {
  if (isMockMode) {
    return mockCheckResponse(req);
  }

  const response = await fetch(`${BASE_URL}/v1/check`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
    },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`/v1/check failed: HTTP ${response.status} — ${text}`);
  }

  const json = await response.json() as CheckResponse;
  return { ...json, mocked: false };
}

export interface StampResponse {
  check_id: string;
  label: string;
  provenance_id: string;
  stamped_at: string;
  output_sha256?: string;
  ledger_entry_hash?: string;
  output_ref?: string;
  mocked: boolean;
}

// ---------------------------------------------------------------------------
// POST /v1/output/stamp  (Member 3 backend contract)
// ---------------------------------------------------------------------------

/**
 * Request output stamping/provenance labelling.
 * When live backend is configured, calls POST /v1/output/stamp with a harmless sample image.
 * Otherwise returns clearly labelled mock data.
 */
export async function stampOutput(checkId: string): Promise<StampResponse> {
  if (isMockMode) {
    await delay(600);
    return {
      check_id: checkId,
      label: 'AI-generated (mock label)',
      provenance_id: `prov_mock_${checkId.slice(-6)}`,
      stamped_at: new Date().toISOString(),
      mocked: true,
    };
  }

  // Create a minimal 1x1 harmless PNG for demonstration
  const pngHeader = new Uint8Array([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
    0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00,
    0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00, 0x00, 0x00, 0x00, 0x49,
    0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
  ]);
  const blob = new Blob([pngHeader], { type: 'image/png' });

  const formData = new FormData();
  formData.append('check_id', checkId);
  formData.append('image', blob, 'demo-output.png');

  try {
    const response = await fetch(`${BASE_URL}/v1/output/stamp`, {
      method: 'POST',
      headers: {
        ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
      },
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Stamp endpoint returned ${response.status}`);
    }

    const json = await response.json() as Record<string, any>;
    return {
      check_id: json.check_id,
      label: json.label,
      provenance_id: json.entry_id,
      stamped_at: json.created_at,
      output_sha256: json.output_sha256,
      ledger_entry_hash: json.ledger_entry_hash,
      output_ref: json.output_ref,
      mocked: false,
    };
  } catch {
    // Graceful fallback to mock with clear label
    await delay(300);
    return {
      check_id: checkId,
      label: 'AI-generated (mock fallback)',
      provenance_id: `prov_mock_${checkId.slice(-6)}`,
      stamped_at: new Date().toISOString(),
      mocked: true,
    };
  }
}

// ---------------------------------------------------------------------------
// Consent hand-off  (Member 2 backend contract)
// ---------------------------------------------------------------------------

export interface ConsentHandoffResult {
  request_id: string;
  passport_url: string;
  mocked: boolean;
}

/**
 * Initiate a consent request. Calls POST /v1/consent/requests if live,
 * or returns clearly labelled mock data.
 */
export async function requestConsent(checkId: string): Promise<ConsentHandoffResult> {
  if (isMockMode) {
    await delay(400);
    return {
      request_id: `cr_mock_${checkId.slice(-6)}`,
      passport_url: `${BASE_URL || 'http://127.0.0.1:8000'}/passport/`,
      mocked: true,
    };
  }

  try {
    const response = await fetch(`${BASE_URL}/v1/consent/requests`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
      },
      body: JSON.stringify({ check_id: checkId }),
    });

    if (response.ok) {
      const json = await response.json() as Record<string, any>;
      return {
        request_id: json.request_id,
        passport_url: `${BASE_URL}/passport/`,
        mocked: false,
      };
    }
  } catch {
    // ignore, fall back
  }

  await delay(300);
  return {
    request_id: `cr_mock_${checkId.slice(-6)}`,
    passport_url: `${BASE_URL || 'http://127.0.0.1:8000'}/passport/`,
    mocked: true,
  };
}


// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

function mockCheckResponse(req: CheckRequest): CheckResponse {
  // Tier 0 scopes: filter, lighting, crop, background
  const tier0 = ['filter', 'lighting', 'crop', 'background'];
  // Tier 2 scopes: hard-block
  const tier2 = ['sexual_transformation', 'nude_transformation'];

  let decision: Decision;
  let tier: number;
  let reasons: string[];
  let consentRequired: boolean;

  if (tier2.includes(req.scope)) {
    decision = 'block';
    tier = 2;
    reasons = ['sexual_real_face_hard_block'];
    consentRequired = false;
  } else if (tier0.includes(req.scope)) {
    decision = 'allow';
    tier = 0;
    reasons = ['benign_edit'];
    consentRequired = false;
  } else {
    // Tier 1: needs consent unless test_signals say no real face
    const realFace = req.test_signals?.real_face ?? true;
    if (realFace) {
      decision = 'needs_consent';
      tier = 1;
      reasons = ['consent_required'];
      consentRequired = true;
    } else {
      decision = 'allow';
      tier = 1;
      reasons = ['benign_edit'];
      consentRequired = false;
    }
  }

  return {
    check_id: `c_mock_${Math.random().toString(36).slice(2, 8)}`,
    decision,
    tier,
    reasons,
    consent_required: consentRequired,
    request_risk: { score: 0.0, label: 'unassessed', source: 'mock' },
    mocked: true,
  };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
