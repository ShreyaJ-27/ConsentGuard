# ConsentGuard

ConsentGuard is an early, local prototype exploring consent-gated safety checks
and output provenance for AI media applications. It does not currently prevent
non-consensual media creation in general and does not provide victim evidence,
takedown, or complaint tooling. See the implementation boundaries below and the
[Issue 4 handoff](docs/ISSUE-4-HANDOFF.md) before integrating it.

---

## 🚨 Problem

The project is motivated by concerns about non-consensual synthetic media and
the difficulty of responding to it. These statements describe motivation, not
measured detection performance, legal advice, or a claim about regulatory
compliance.

---

## 💡 Solution

The intended product direction is a plug-in that an AI app could integrate.
The current prototype has only the following implemented backend flow:

1. **Request check** – Routes from a structured scope. Risk and face/age
   assessment are stubs, not production detection.
2. **Consent prototype** – Issues and verifies short-lived grants. Demo subject
   actions are simulated bearer-code actions, not identity verification.
3. **Output check and stamp** – Runs an explicitly labelled stub, applies the
   visible `AI-generated` label, and records hashes in a process-local ledger.
4. **Lookup and download** – Provides ledger lookup and authenticated access to
   process-local stamped outputs.

Victim-support features are future product goals and are not implemented.

---

## ✨ Key Features
- Structured scope routing (request-risk scoring is a stub)
- Consent request/token lifecycle stored in single-host SQLite
- Visible labeling and a process-local tamper-evident hash chain
- A TypeScript SDK for check, stamp, output download, lookup, and consent verification

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
partner endpoints including `POST /v1/check`, consent request creation,
stamping, and output download require `X-API-Key`. Consent subject demo
actions are instead controlled by a simulated action code and are disabled by
default. The authenticated app identity is configured server-side as
`CONSENTGUARD_APP_ID`; a client-supplied `app_id` is rejected.

### Consent tokens (Issue 2)

Consent tokens are short-lived Ed25519-signed JWTs. Generate a private key
outside the repository and restrict access to the service account. For example,
with OpenSSL in PowerShell:

```powershell
$keyDirectory = Join-Path $env:LOCALAPPDATA "ConsentGuard"
New-Item -ItemType Directory -Force $keyDirectory | Out-Null
openssl genpkey -algorithm Ed25519 -out (Join-Path $keyDirectory "consentguard-ed25519-private.pem")
```

Set these values in the ignored `.env` file:

```text
CONSENTGUARD_SIGNING_KEY_PATH=C:\Users\<you>\AppData\Local\ConsentGuard\consentguard-ed25519-private.pem
CONSENTGUARD_CONSENT_DATABASE_PATH=C:\Users\<you>\AppData\Local\ConsentGuard\consentguard.sqlite3
CONSENTGUARD_CONSENT_ISSUER=consentguard.local
CONSENTGUARD_CONSENT_TOKEN_TTL_SECONDS=900
CONSENTGUARD_ENABLE_DEMO_SUBJECT_ACTIONS=false
```

The private key and SQLite database are ignored by Git (`*.pem`, `*.key`,
`*.sqlite3`, and `*.db`). Do not place key contents in `.env`, source, logs, or
API responses. Back up and rotate signing keys using a controlled operational
process; this prototype supports one active key ID and does not implement
multi-key rotation.

The consent flow is:

1. `POST /v1/check` with a stable opaque `target_ref`; a check that returns
   `needs_consent` records the authenticated app, scope, target digest, and
   decision server-side.
2. The partner calls `POST /v1/consent/requests` with that server-issued
   `check_id`. Unknown, expired, ineligible, cross-app, or target-less checks
   are rejected. One request may be created for a check.
3. `POST /v1/consent/approve` or `POST /v1/consent/deny` uses the request ID and
   demo action code. `POST /v1/consent/status` checks the request state with the
   same code. Approval issues a token bound to the request, internal simulated
   subject reference, app, scope, and target digest.
4. `POST /v1/consent/revoke` uses the token `jti` and action code.
   `POST /v1/generate/verify` accepts a recorded `check_id`, token, and target
   reference; each verification checks the JWT and current SQLite state.

### Consent Passport demo UI

The repository has no separate frontend framework; the prototype UI is a
dependency-free page served by FastAPI at `http://127.0.0.1:8000/passport/`.
There is no frontend package installation or build step. Start the backend as
described above and set the following **only for a local demo** in `.env`:

```text
CONSENTGUARD_ENABLE_TEST_SIGNALS=true
CONSENTGUARD_ENABLE_DEMO_SUBJECT_ACTIONS=true
```

Restart Uvicorn after changing `.env`, open `/passport/`, enter the local
partner API key in the password field, and:

1. Select an operation and target reference, enable the demo-signal checkbox,
   then run the check. It should return `needs_consent` with the demo signals
   enabled.
2. Create a consent request from the resulting server-issued check ID.
3. Review the status and use the simulated approve or deny action. Approval
   returns a signed token; verify it against the same check and target, then
   revoke it and verify that it is rejected.

The UI keeps the API key and token in page memory only and sends partner API
requests to the same gateway origin. The key is still privileged while entered;
use only a local demo key and close the tab when finished. The generated demo
action code is provided to the partner caller for convenience, so this interface
does **not** securely separate partner and subject roles. Never enable either
demo setting or use this approval flow in production. With demo subject actions
disabled, the page can create a request but approval, denial, status lookup,
and revocation are unavailable. Real subject authentication and a production
Passport experience remain unimplemented.

The signed JWT includes `iss`, exact `aud`, `iat`, `exp`, `jti`, `sub`,
`consent_request_id`, `scope`, and the target-reference digest. Verification
rejects malformed or invalid signatures, invalid time claims, mismatched app,
scope, request, subject, target, or database state. Revocation is read from
SQLite for every check. `sub` is a random internal request binding, not a
verified person; target hashes do not prove real-world identity. Tier 2 and
minor-risk blocks remain higher priority than consent.

**Subject authentication is not implemented.** The approval/denial/revocation
code is an explicitly simulated bearer capability, not proof of the subject’s
identity. It is disabled by default. Setting
`CONSENTGUARD_ENABLE_DEMO_SUBJECT_ACTIONS=true` enables the local demo behavior;
the code is returned to the partner API caller and therefore is not suitable
for production or for a real Passport. Do not enable it in a deployed service.
The prototype also does not detect faces or establish that a target reference
belongs to the approving person. A signed token proves that this service issued
the encoded grant, not that a real person’s identity was verified.

SQLite provides persistence for a single-host prototype. Its state is not
shared safely across replicated hosts; use a shared transactional database and
real subject authentication before scaling or production use.

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

The UI is served from the backend; a smoke check is included in the Python test
suite (`GET /passport/`). Focused token and gateway security tests can be run
with:

```powershell
python -m pytest gateway\tests\test_consent.py gateway\tests\test_api.py gateway\tests\test_router.py -q
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
- Consent requests and revocation state are stored in SQLite and survive
  application restarts on the same host. Audit and enforcement repositories
  remain in-memory and process-local.
- `StubRequestRiskScorer` returns an unassessed zero score and does not classify
  prompts or languages. It provides no real risk protection.
- Consent tokens are Ed25519-signed and checked against expiry, revocation,
  app, scope, target digest, and originating check. The target reference is
  opaque input, not identity proof.
- Request risk, face/age assessment, and output safety checking are stubs.
  Tier 2 operations remain blocked by policy; demo signals are untrusted
  client-provided test inputs and must remain disabled outside local testing.
- Output bytes and the ledger are in-memory and process-local. Consent state is
  SQLite-backed for one host. This is not a production safety system.

---

## Issue 3 output safety hooks, provenance stamping, ledger, and TypeScript SDK

Issue 3 implements defensive result checks, visible AI labelling, hash-chained provenance logging, origin lookup, and a typed TypeScript SDK.

### Added endpoints

- `POST /v1/output/stamp`: Accepts `check_id` and an uploaded image. Runs defensive result checks before acceptance. Allowed outputs receive a visible `AI-generated` label, compute pre/post SHA-256 and 64-bit difference hash (`dhash-64`), append a tamper-evident record to the ledger, and return a `StampReceipt`.
- `GET /v1/output/download/{output_ref}`: Downloads a process-local stamped output; requires the same authenticated app API key and is limited by a fixed in-memory capacity.
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

The typed SDK is located in `sdk-ts/`. From PowerShell on Windows:

```powershell
Set-Location sdk-ts
npm ci
npm run build
npm test
```

### Tested behaviors and empirical measurements

1. **Defensive fail-closed checks**: Outputs marked flagged (`mock_signal="flagged"` or containing `FLAGGED_FIXTURE_MARKER`) are rejected with HTTP 422 and are not added to the ledger. Indeterminate results fail closed.
2. **Hash-chained ledger**: Canonical JSON serialization ensures deterministic key ordering. Tampering with any entry payload, broken previous-hash link, or swapped order is detected by `verify_ledger_chain()`.
3. **Perceptual hashing format and experiments**:
   - Format: `dhash-64` (64-bit difference hash, 16 hexadecimal characters).
   - Scaling experiment (256x256 -> 128x128 downscale and 256x256 -> 512x512 upscale): measured Hamming distance <= 6 bits out of 64 (>90% bit agreement).
   - JPEG recompression experiment (quality 85 and 60): measured Hamming distance <= 4 bits (quality 85) and <= 6 bits (quality 60).
4. **Data handling**: Ledger records contain hashes and metadata, not raw image bytes, prompts, API keys, bearer tokens, or face embeddings. Stamped image bytes are retained in process-local output memory. The gateway route code does not intentionally log those request values; deployments must review their own logging and adapters.
5. **Real vs. stubbed boundaries**:
   - `StubResultChecker` is an explicitly labelled test stub for prototype validation; it is not a production NSFW or biometric classifier.
   - An image hash or watermark does not prove legal authorship, and unsigned metadata is not a certified C2PA manifest.
   - A lookup no-match result indicates only that the hash is absent from the ledger; it does not prove authenticity or falsity.
