# @consentguard/sdk

TypeScript client for the **ConsentGuard** local prototype gateway.

The SDK wraps request checks, multipart stamping, output download, perceptual-hash
lookup, and consent-token verification. Gateway risk and safety assessments are
stubs; this SDK is not a production safety control.

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
    scope: "filter",
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

  // Step 2: Generate output using your separately configured model.
  const generatedBytes: Uint8Array = await myModel.generate(
    "Apply subtle cartoon portrait styling"
  );

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

    if (receipt.outputRef) {
      const stampedBytes = await cg.downloadOutput(receipt.outputRef);
      console.log("Downloaded stamped bytes:", stampedBytes.byteLength);
    }

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

For identity-altering scopes, provide a stable opaque `targetRef`. If the
response is `needs_consent`, the caller must use the consent API flow and then
perform a new check with `consentToken` and `consentCheckId`; the SDK does not
create, approve, deny, query, or revoke consent requests. The backend still
requires valid server-side consent at stamp time.

### `cg.stamp(request: StampRequest): Promise<StampReceipt>`
Submits image bytes as multipart form data. The gateway only stamps an
unexpired, app-bound `allow` check and revalidates consent for identity-altering
scopes. Its current result checker is a test stub. Accepted images receive the
visible `AI-generated` label, SHA-256 digests and a `dhash-64` value, then a
hash-chained ledger entry.

### `cg.downloadOutput(outputRef: string): Promise<Uint8Array>`
Fetches stamped image bytes from the gateway's in-memory output store. Adds the
`X-API-Key` header. Outputs may disappear on restart or after the fixed-capacity
store evicts older entries.

### `cg.lookup(phash: string, maxDistance: number = 0): Promise<LookupResponse>`
Performs an origin lookup against the provenance ledger. Supports exact hash matching (`maxDistance = 0`) or Hamming-distance matching (`maxDistance > 0`).

### `cg.verify(request: VerifyConsentRequest): Promise<VerifyConsentResponse>`
Checks consent token state at `/v1/generate/verify` using the supplied check,
token, and target reference. Adds the `X-API-Key` header.

The SDK does not currently expose `/v1/ledger/verify`; call that endpoint
directly if ledger-chain verification is required.

---

## Error Handling

The SDK exposes strongly typed errors:

- `ConsentGuardApiError`: Gateway returned a non-2xx response.
  - `statusCode`: HTTP status (e.g. 401, 422, 429).
  - `errorCode`: Machine-readable error code (e.g. `harmful_content_detected`, `unauthorized`, `rate_limited`).
  - `message`: Human-readable error message with any sensitive API keys automatically sanitized.
- `ConsentGuardNetworkError`: Connectivity, DNS, or other fetch failure.
- `ConsentGuardTimeoutError`: Request or response-body processing exceeded
  configured `timeoutMs`.

---

## Security & Privacy Guarantees

- The SDK sends the configured API key as `X-API-Key` and sanitizes matching
  key text in surfaced fetch/API error messages. Applications remain
  responsible for not logging credentials or sensitive request data.
- The gateway ledger stores hash and metadata records, not raw images or
  prompts. Stamped output bytes are retained in process-local memory. Do not
  send victim images or sensitive content to a public deployment of this
  prototype.
- The gateway rejects flagged, errored, and indeterminate test checks, but its
  result checker is not a production classifier.

---

## Limitations & Prototype Notice

- Request-risk scoring, face/age assessment, and output safety checking are
  explicitly labelled stubs. They provide no real-world detection.
- Consent actions enabled for local demos are simulated bearer-code actions,
  not subject authentication or identity verification.
- Consent state is SQLite-backed for a single host; output bytes, audit,
  enforcement, and the provenance ledger are in-memory and reset on restart.
- A hash does not prove authorship. An unsigned label is not a certified C2PA manifest.
- A ledger lookup no-match result indicates only that no matching perceptual hash was found in the configured ledger; it does not prove whether an image is authentic or fake.
- See the repository's [Issue 4 handoff](../docs/ISSUE-4-HANDOFF.md) for the
  backend contracts and integration limitations.

---

## License

Apache-2.0
