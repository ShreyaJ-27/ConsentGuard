# ConsentGuard

ConsentGuard is a safety layer for AI photo and video applications that prevents the creation of fake or morphed content of real people—especially women—without their explicit consent. It also empowers victims by providing tools to generate evidence packs and file takedown requests.

---

## 🚨 Problem

Deepfake and morphed images/videos of women are being created and shared online every day. Current AI apps rely mostly on keyword filters, which are easily bypassed by rewording or using Hindi/Hinglish. Victims often lack accessible tools to prove harm and request takedowns quickly. India’s new AI regulations (Feb 2026) mandate proactive blocking, labelling, and fast takedown of harmful content, but small AI apps struggle to comply.

---

## 💡 Solution

ConsentGuard is a plug-in that any AI app can integrate. It works in **five steps**:

1. **Request Check** – Detect suspicious prompts across English, Hindi, and Hinglish.  
2. **Consent Verification** – If a real face is used, the person must prove identity via live selfie or provide explicit permission.  
3. **Result Scan** – Block outputs that combine real faces with nudity or harmful edits.  
4. **Labelling & Provenance** – Every allowed output is watermarked “AI-generated” with hidden tracking data.  
5. **Repeat Attempts** – Accounts making repeated harmful requests are restricted, with human review before escalation.

For victims, ConsentGuard provides a **self-help tool** to privately upload fakes, generate evidence packs (time, links, file fingerprints), and auto-create takedown and cybercrime complaints with helpline info.

---

## ✨ Key Features
- Multilingual detection (English, Hindi, Hinglish)  
- Consent-first verification workflow  
- Cryptographic watermarking & provenance tracking  
- Automated victim support tools  
- Compliance-ready for India’s 2026 AI safety regulations  

---

## 📌 Use Cases
- AI photo/video apps needing compliance with new safety rules  
- Victims of deepfake abuse seeking fast takedown support  
- Developers building ethical AI platforms  

---

## 📜 License
Under Apache 2.0 License.

---

## Issue 1 gateway MVP

The repository includes a local FastAPI gateway for `GET /health` and
`POST /v1/check`. It assigns tiers from a structured `scope` and returns the
stable decisions `allow`, `needs_consent`, or `block`. OpenAPI is available at
`/docs`.

### Run locally (Windows PowerShell)

Use Python 3.11 as specified in `IMPLEMENTATION-PLAN.md`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Replace both `replace-me` values in `.env` with independently generated random
secrets of at least 32 characters. For example, generate each secret in
PowerShell with:

```powershell
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$bytes = New-Object byte[] 32
$rng.GetBytes($bytes)
[BitConverter]::ToString($bytes).Replace("-", "")
```

Keep `.env` private; it is ignored by Git. The API key and HMAC key must be
different. Then start the service:

```powershell
uvicorn gateway.app.main:create_app --factory --reload --env-file .env
```

Open `http://127.0.0.1:8000/docs`. The `/health` endpoint is public;
`POST /v1/check` requires the `X-API-Key` header. The authenticated app identity
is configured server-side as `CONSENTGUARD_APP_ID`; a client-supplied `app_id`
is rejected.

### Example check

```powershell
$apiKey = (Get-Content .env | Where-Object { $_ -match '^CONSENTGUARD_API_KEY=' }) -replace '^CONSENTGUARD_API_KEY=', ''
$body = @{
    prompt = "Apply a cartoon filter"
    scope = "filter"
    user_ref = "demo-user-1"
} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/check -Method Post `
    -Headers @{ "X-API-Key" = $apiKey } -ContentType "application/json" -Body $body
```

A benign-scope response has this shape:

```json
{
  "check_id": "c_0123456789ab",
  "decision": "allow",
  "tier": 0,
  "reasons": ["benign_edit"],
  "consent_required": false,
  "request_risk": {
    "score": 0.0,
    "label": "unassessed",
    "source": "stub"
  }
}
```

For demo-only safety-signal tests, `test_signals` accepts optional `real_face`
and `minor_risk` booleans. These are untrusted client inputs isolated behind
`MockFaceRiskService`. They are rejected unless
`CONSENTGUARD_ENABLE_TEST_SIGNALS=true` is explicitly set; leave it false outside
local tests. They are not face or age detection and must not be used as
production safety signals. Without a minor-risk result, Tier 1/2 fails closed.

### Tests

```powershell
python -m pytest -q
```

### Implemented behavior and boundaries

- Central scope policy: Tier 0 for filter, lighting, crop, and background;
  Tier 1 for face swap, photo animation, body edit, and voice clone; Tier 2 for
  sexual/nude transformation. Unknown scopes fail validation.
- Tier 2 with a real or unknown face is hard-blocked; Tier 1/2 with child risk
  or unavailable minor-risk assessment is blocked. Tier 1 real-face requests
  require a consent verifier to return a valid result.
- API-key authentication uses a SHA-256 digest for comparison and does not
  retain the raw key. Request user references are HMAC-pseudonymized before use
  in audit and enforcement records. Prompt text, tokens, and raw user references
  are not written to audit records or application logs.
- Blocked-attempt threshold/window and per-app rate limit are configurable.
  Defaults are three blocked attempts in seven days and 60 checks per minute.
  Reviewer/appeal support is an interface only; the default review adapter does
  not clear restrictions.
- Audit and enforcement repositories are in-memory, process-local
  implementations. They are not durable or shared across workers/restarts.
- `StubRequestRiskScorer` returns an unassessed zero score and does not classify
  prompts or languages. It provides no real risk protection.
- `UnavailableConsentVerifier` never validates a supplied token. Member 2 must
  replace it with signature, expiry, revocation, app, scope, and face-match
  verification before Tier 1 real-face checks can be allowed. No consent-token
  minting is implemented here.
- No image upload, face detector, age classifier, or explicit-capable generator
  is implemented in Issue 1. This is a prototype gateway, not a production safety system.

---

## Issue 3 output safety hooks, provenance stamping, ledger, and TypeScript SDK

Issue 3 implements defensive result checks, visible AI labelling, hash-chained provenance logging, origin lookup, and a typed TypeScript SDK.

### Added endpoints

- `POST /v1/output/stamp`: Accepts `check_id` and an uploaded image. Runs defensive result checks before acceptance. Allowed outputs receive a visible `AI-generated` label, compute pre/post SHA-256 and 64-bit difference hash (`dhash-64`), append a tamper-evident record to the ledger, and return a `StampReceipt`.
- `GET /v1/output/download/{output_ref}`: Downloads the stamped output image using the short-lived reference.
- `GET /v1/ledger/lookup?phash=...&max_distance=0`: Looks up an image by perceptual hash. Returns match/no-match and qualified provenance metadata.
- `GET /v1/ledger/verify`: Verifies the cryptographic integrity of the hash-chained ledger.

### Example stamp request

```bash
curl -X POST http://127.0.0.1:8000/v1/output/stamp \
  -H "X-API-Key: $API_KEY" \
  -F "check_id=c_9f2a01234567" \
  -F "image=@output.png"
```

Response:
```json
{
  "check_id": "c_9f2a01234567",
  "entry_id": "entry_9f2a01234567",
  "output_sha256": "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92",
  "pre_stamp_sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
  "phash": "8ed0d1d2f279cc96",
  "label": "AI-generated",
  "created_at": "2026-10-11T12:00:00Z",
  "ledger_entry_hash": "a1b2c3d4e5f6...",
  "output_ref": "out_0123456789ab"
}
```

### Example lookup request

```bash
curl http://127.0.0.1:8000/v1/ledger/lookup?phash=8ed0d1d2f279cc96
```

Response:
```json
{
  "match": true,
  "method": "exact_phash",
  "provenance": {
    "check_id": "c_9f2a01234567",
    "label": "AI-generated",
    "created_at": "2026-10-11T12:00:00Z",
    "output_sha256": "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"
  },
  "message": "Matching provenance ledger entry found."
}
```

### TypeScript SDK (`sdk-ts/`)

The typed SDK is located in `sdk-ts/`. To install, build, and test:

```bash
cd sdk-ts
npm install
npm run build
npm test
```

### Tested behaviors and empirical measurements

1. **Defensive fail-closed checks**: Outputs marked flagged (`mock_signal="flagged"` or containing `FLAGGED_FIXTURE_MARKER`) are rejected with HTTP 422 and are never stamped or logged as accepted. Indeterminate checks on high-risk requests fail closed.
2. **Hash-chained ledger**: Canonical JSON serialization ensures deterministic key ordering. Tampering with any entry payload, broken previous-hash link, or swapped order is detected by `verify_chain()`.
3. **Perceptual hashing format and experiments**:
   - Format: `dhash-64` (64-bit difference hash, 16 hexadecimal characters).
   - Scaling experiment (256x256 -> 128x128 downscale and 256x256 -> 512x512 upscale): measured Hamming distance <= 6 bits out of 64 (>90% bit agreement).
   - JPEG recompression experiment (quality 85 and 60): measured Hamming distance <= 4 bits (quality 85) and <= 6 bits (quality 60).
4. **Data privacy**: Ledger records and application logs NEVER store raw image bytes, prompts, API keys, bearer tokens, or face embeddings.
5. **Real vs. stubbed boundaries**:
   - `StubResultChecker` is an explicitly labelled test stub for prototype validation; it is not a production NSFW or biometric classifier.
   - An image hash or watermark does not prove legal authorship, and unsigned metadata is not a certified C2PA manifest.
   - A lookup no-match result indicates only that the hash is absent from the ledger; it does not prove authenticity or falsity.
