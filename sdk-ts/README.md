# @consentguard/sdk

Official TypeScript SDK for the **ConsentGuard** AI safety and provenance gateway.

ConsentGuard provides a layered safety defense for AI photo and video generation applications:
1. **Request check** – structured scope categorization, prompt risk assessment, and consent gate routing.
2. **Result scan** – defensive output safety checks before image acceptance.
3. **Provenance stamping** – visible `AI-generated` label, unambiguous SHA-256 digests, and 64-bit perceptual hashing (`dhash-64`).
4. **Hash-chained ledger** – tamper-evident provenance records and perceptual hash origin lookup.

---

## Installation

```bash
npm install @consentguard/sdk
```

---

## Quickstart

```typescript
import { ConsentGuard, ConsentGuardApiError } from "@consentguard/sdk";

// Initialize client
const cg = new ConsentGuard({
  apiKey: process.env.CONSENTGUARD_API_KEY!,
  baseUrl: process.env.CONSENTGUARD_URL || "http://127.0.0.1:8000",
  timeoutMs: 10000,
});

async function main() {
  // Step 1: Request check
  const check = await cg.check({
    prompt: "Apply subtle cartoon portrait styling",
    scope: "face_swap",
    userRef: "user_session_123",
  });

  if (check.decision === "needs_consent") {
    console.log("Consent required before generation.");
    return;
  }
  if (check.decision === "block") {
    console.log("Request blocked by policy:", check.reasons);
    return;
  }

  // Step 2: Generate output using your model
  const generatedBytes: Uint8Array = await myModel.generate(prompt);

  // Step 3: Verify output safety and stamp provenance
  try {
    const receipt = await cg.stamp({
      checkId: check.checkId,
      image: generatedBytes,
      filename: "output.png",
    });

    console.log("Output stamped successfully!");
    console.log("Entry ID:", receipt.entryId);
    console.log("Output SHA-256:", receipt.outputSha256);
    console.log("Perceptual Hash:", receipt.phash);
    console.log("Ledger Hash:", receipt.ledgerEntryHash);

    // Optional Step 4: Lookup in provenance ledger
    const lookup = await cg.lookup(receipt.phash);
    console.log("Origin lookup match:", lookup.match);
  } catch (err) {
    if (err instanceof ConsentGuardApiError) {
      console.error(`Safety check failed (status ${err.statusCode}): ${err.errorCode}`);
    } else {
      throw err;
    }
  }
}
```

---

## API Reference

### `new ConsentGuard(config: ConsentGuardConfig)`

- `apiKey` (string, required): Partner application API key.
- `baseUrl` (string, optional): Gateway URL (defaults to `http://127.0.0.1:8000`).
- `timeoutMs` (number, optional): Request timeout in milliseconds (defaults to `10000`).
- `fetch` (function, optional): Custom fetch implementation.

### `cg.check(request: CheckRequest): Promise<CheckResponse>`
Submits an input request to `/v1/check`. Evaluates prompt risk, scope tier (Tiers 0, 1, 2), and consent state.

### `cg.stamp(request: StampRequest): Promise<StampReceipt>`
Executes output safety checks on generated image bytes. If safe, overlays a visible `AI-generated` label, records pre- and post-stamp SHA-256 digests, computes a 64-bit difference hash (`dhash-64`), appends a tamper-evident entry to the hash-chained ledger, and returns a verified `StampReceipt`.

### `cg.downloadOutput(outputRef: string): Promise<Uint8Array>`
Fetches the stamped image bytes from the gateway's short-lived output store.

### `cg.lookup(phash: string, maxDistance: number = 0): Promise<LookupResponse>`
Performs an origin lookup against the provenance ledger. Supports exact hash matching (`maxDistance = 0`) or Hamming-distance matching (`maxDistance > 0`).

### `cg.verify(request: VerifyConsentRequest): Promise<VerifyConsentResponse>`
Checks consent token state before generation with the Member 2 consent verifier.

---

## Error Handling

The SDK exposes strongly typed errors:

- `ConsentGuardApiError`: Gateway returned a 4xx or 5xx response.
  - `statusCode`: HTTP status (e.g. 401, 422, 429).
  - `errorCode`: Machine-readable error code (e.g. `harmful_content_detected`, `unauthorized`, `rate_limited`).
  - `message`: Human-readable error message with any sensitive API keys automatically sanitized.
- `ConsentGuardNetworkError`: Connectivity or DNS failure.
- `ConsentGuardTimeoutError`: Request exceeded configured `timeoutMs`.

---

## Security & Privacy Guarantees

- **No Secret Leakage**: The client automatically redacts API keys from error messages, representations, and logs.
- **Privacy Preservation**: The provenance ledger records only cryptographic hashes and metadata; raw image bytes, prompts, and user references are never stored.
- **Fail-Closed Safety**: Outputs flagged during safety checks are rejected immediately and never stamped or returned as accepted.

---

## Limitations & Prototype Notice

- The default result checker in the gateway prototype is an explicitly labelled test stub. It exercises gateway fail-closed semantics and does not provide real-world NSFW, nudity, or biometric face detection.
- A hash does not prove authorship. An unsigned label is not a certified C2PA manifest.
- A ledger lookup no-match result indicates only that no matching perceptual hash was found in the configured ledger; it does not prove whether an image is authentic or fake.

---

## License

Apache-2.0
