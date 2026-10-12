/**
 * lookupClient.ts — Origin lookup API client for the Rescue Kit.
 *
 * Privacy contract:
 *  - ONLY sends the perceptual hash (phash), never the file itself.
 *  - Returns null in mock mode; clearly labelled.
 *  - Caller must get explicit user confirmation before calling lookup().
 */

const BASE_URL = import.meta.env.VITE_GATEWAY_BASE_URL as string | undefined;

/** True when no gateway URL is configured. */
export const isMockMode = !BASE_URL || BASE_URL.trim() === '';

export interface LookupResult {
  match: boolean;
  method?: string;
  matched_at?: string;
  check_id?: string;
  label?: string;
  output_sha256?: string;
  distance?: number;
  message?: string;
  mocked: boolean;
}

/**
 * Look up a perceptual hash in the ConsentGuard ledger.
 *
 * @param phash - The perceptual hash hex string (16 hex chars / dHash-64).
 *                ONLY this value is sent; the original file is never sent.
 * @returns LookupResult or throws on network/HTTP error.
 */
export async function lookupByPhash(phash: string): Promise<LookupResult> {
  if (isMockMode) {
    // Simulate a random result so all three states can be demonstrated.
    await delay(800);
    const mockMatch = phash.startsWith('0') || phash.startsWith('1');
    return {
      match: mockMatch,
      method: 'mock_phash',
      matched_at: mockMatch ? new Date().toISOString() : undefined,
      check_id: mockMatch ? 'c_mock_demo' : undefined,
      label: mockMatch ? 'AI-generated' : undefined,
      output_sha256: mockMatch ? 'mock_sha256_hash_here' : undefined,
      mocked: true,
    };
  }

  const url = new URL('/v1/ledger/lookup', BASE_URL);
  url.searchParams.set('phash', phash);

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Ledger lookup failed: HTTP ${response.status}`);
  }

  const json = await response.json() as Record<string, any>;
  const prov = json.provenance;
  return {
    match: Boolean(json.match),
    method: json.method,
    matched_at: prov?.created_at,
    check_id: prov?.check_id,
    label: prov?.label,
    output_sha256: prov?.output_sha256,
    distance: json.distance,
    message: json.message,
    mocked: false,
  };
}


function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
