/**
 * Scope categories mapped to safety risk tiers.
 */
export type Scope =
  | "filter"
  | "lighting"
  | "crop"
  | "background"
  | "face_swap"
  | "photo_animation"
  | "body_edit"
  | "voice_clone"
  | "sexual_transformation"
  | "nude_transformation";

/**
 * Demo-only mock safety signals for testing gateway routing.
 * Production systems must use trusted server-side models.
 */
export interface MockSafetySignals {
  real_face?: boolean;
  minor_risk?: boolean;
}

/**
 * Configuration options for the ConsentGuard client.
 */
export interface ConsentGuardConfig {
  /** API key for partner application authentication. */
  apiKey: string;
  /** Base URL for the ConsentGuard gateway (e.g. "http://127.0.0.1:8000"). */
  baseUrl?: string;
  /** HTTP request timeout in milliseconds. Defaults to 10000ms. */
  timeoutMs?: number;
  /** Optional custom fetch implementation for testing or polyfills. */
  fetch?: typeof fetch;
}

/**
 * Request payload for POST /v1/check.
 */
export interface CheckRequest {
  prompt: string;
  scope: Scope;
  userRef: string;
  consentToken?: string;
  testSignals?: MockSafetySignals;
}

export type DecisionName = "allow" | "needs_consent" | "block";

export interface RequestRiskInfo {
  score: number;
  label: string;
  source: string;
}

/**
 * Gateway response from POST /v1/check.
 */
export interface CheckResponse {
  checkId: string;
  decision: DecisionName;
  tier: number;
  reasons: string[];
  consentRequired: boolean;
  requestRisk: RequestRiskInfo;
}

/**
 * Input parameters for POST /v1/output/stamp.
 */
export interface StampRequest {
  checkId: string;
  image: Uint8Array | ArrayBuffer | Blob | Buffer;
  filename?: string;
  mockSignal?: string;
  highRisk?: boolean;
}

/**
 * Provenance receipt returned when an output passes result checks and is stamped.
 */
export interface StampReceipt {
  checkId: string;
  entryId: string;
  outputSha256: string;
  preStampSha256: string;
  phash: string;
  label: string;
  createdAt: string;
  ledgerEntryHash: string;
  outputRef?: string;
}

/**
 * Qualified provenance details in a ledger lookup response.
 */
export interface LookupProvenance {
  checkId: string;
  label: string;
  createdAt: string;
  outputSha256: string;
}

/**
 * Response from GET /v1/ledger/lookup.
 */
export interface LookupResponse {
  match: boolean;
  method: string;
  provenance?: LookupProvenance | null;
  message?: string | null;
  distance?: number | null;
}

/**
 * Request to verify a consent token with the Member 2 consent gate.
 */
export interface VerifyConsentRequest {
  jti: string;
  checkId: string;
}

/**
 * Response from consent token verification.
 */
export interface VerifyConsentResponse {
  valid: boolean;
  jti: string;
  scope?: string;
}
