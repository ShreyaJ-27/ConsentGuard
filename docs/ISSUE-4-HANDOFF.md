# Issue 4 frontend handoff: Issues 1–3 API

This handoff records the current FastAPI/OpenAPI contract for the local
prototype. Treat `/openapi.json` and the Pydantic schemas as authoritative if
the implementation changes. No Issue 4 frontend or victim-support feature is
implemented here.

## Local prerequisites and startup

Use Python 3.11. From a fresh PowerShell clone at the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Replace both `replace-me` values in `.env` with separate random secrets of at
least 32 characters. Create a protected Ed25519 private key outside the
repository and update `CONSENTGUARD_SIGNING_KEY_PATH` to its absolute path.
Update `CONSENTGUARD_CONSENT_DATABASE_PATH` to a local writable SQLite path.
The sample contains Windows paths with a `<you>` placeholder; replace the
placeholder rather than using it literally. Keep `.env`, the private key, and
the database out of version control.

Start the gateway:

```powershell
.\.venv\Scripts\python.exe -m uvicorn gateway.app.main:create_app --factory --reload --env-file .env
```

Check `http://127.0.0.1:8000/health`, `/docs`, and `/openapi.json`. The check,
consent request creation, verification, stamp, and output download partner
routes require `X-API-Key`. The server maps that key to the configured
`CONSENTGUARD_APP_ID`; clients cannot choose their own app identity.

Important settings:

| Variable | Meaning |
|---|---|
| `CONSENTGUARD_API_KEY` | Required partner API secret (minimum 32 characters). |
| `CONSENTGUARD_USER_REF_HMAC_KEY` | Required separate secret for pseudonymizing user references (minimum 32 characters). |
| `CONSENTGUARD_APP_ID` | Server-configured identity associated with the API key. |
| `CONSENTGUARD_SIGNING_KEY_PATH` | Required path to an Ed25519 PEM private key. Invalid or non-Ed25519 keys stop startup. |
| `CONSENTGUARD_CONSENT_DATABASE_PATH` | SQLite file for checks, consent requests, tokens, and revocations. |
| `CONSENTGUARD_CONSENT_ISSUER` | Issuer claim expected in consent JWTs. |
| `CONSENTGUARD_CONSENT_TOKEN_TTL_SECONDS` | Consent request/token lifetime, capped by originating check expiry. |
| `CONSENTGUARD_ENABLE_DEMO_SUBJECT_ACTIONS` | Defaults to `false`; enables simulated bearer-code approve/deny/status/revoke routes. |
| `CONSENTGUARD_ENABLE_TEST_SIGNALS` | Defaults to `false`; enables explicitly untrusted test signals for local tests only. |
| `CONSENTGUARD_MAX_OUTPUT_SIZE_BYTES` | Maximum image bytes, enforced while reading the upload (default 10 MiB). |
| `CONSENTGUARD_BLOCKED_ATTEMPT_THRESHOLD`, `CONSENTGUARD_RESTRICTION_WINDOW_SECONDS` | In-memory repeat-block restriction parameters. |
| `CONSENTGUARD_RATE_LIMIT_REQUESTS`, `CONSENTGUARD_RATE_LIMIT_WINDOW_SECONDS` | In-memory per-app request rate limit. |

## Shared request and error conventions

Partner API routes use:

```http
X-API-Key: <configured partner API key>
```

Successful JSON responses use the snake_case property names shown below.
Validation and application errors use:

```json
{
  "error": {
    "code": "machine_readable_code",
    "message": "Safe, user-readable explanation."
  }
}
```

Common statuses are `400` for disabled test inputs or invalid operation
parameters, `401` for missing/invalid API key, `403` for demo subject actions
disabled, `404` for unavailable/expired or app-mismatched records, `409` for
ineligible checks, conflicts or failed consent authorization, `413` for an
oversized upload, `422` for schema or safety-check failure, `429` for the
in-memory rate limit (`Retry-After` is supplied), and `503` when consent
storage or verification is unavailable. A frontend must treat any non-2xx
response as failure; never interpret missing, malformed, or unavailable
authorization as allow.

## Request check

### `POST /v1/check`

JSON request:

```json
{
  "prompt": "Apply a color filter",
  "scope": "filter",
  "user_ref": "opaque-session-reference",
  "target_ref": null,
  "consent_token": null,
  "consent_check_id": null,
  "test_signals": null
}
```

Required: `prompt` (1–4000 characters), `scope`, and `user_ref` (1–256
characters). The supported scopes are `filter`, `lighting`, `crop`,
`background`, `face_swap`, `photo_animation`, `body_edit`, `voice_clone`,
`sexual_transformation`, and `nude_transformation`. `target_ref` is optional
for the check schema (1–512 characters when present), but is required to open
a consent request. A consent re-check supplies `consent_token`,
`consent_check_id` (the original consent-request check ID), and the same
`target_ref`.

`test_signals` can contain `real_face` and `minor_risk` booleans. These are
untrusted client test inputs and are rejected unless
`CONSENTGUARD_ENABLE_TEST_SIGNALS=true`. Do not enable this outside isolated
local testing.

Response:

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

`decision` is `allow`, `needs_consent`, or `block`. `check_id` is issued and
stored server-side for 15 minutes. Tier 2 (`sexual_transformation`,
`nude_transformation`) remains blocked; consent cannot override it. Tier 1
requires a target and valid grant when the configured face-risk adapter
identifies or cannot rule out a real face; unknown minor risk fails closed.
The current request-risk and face/age adapters are stubs, not detection
systems.

## Consent lifecycle

Consent request creation and verification are partner routes and require
`X-API-Key`. The simulated subject actions do not use that header; they require
the demo action code and return `403 demo_subject_actions_disabled` unless
`CONSENTGUARD_ENABLE_DEMO_SUBJECT_ACTIONS=true`.

### `POST /v1/consent/requests`

JSON request:

```json
{ "check_id": "c_0123456789ab" }
```

Only a current, same-app `needs_consent` check with a target can create one
request. A second request for that check conflicts. Response:

```json
{
  "request_id": "cr_<uuid>",
  "status": "pending",
  "expires_at": 0,
  "demo_action_code": null
}
```

`demo_action_code` is returned only when demo subject actions are enabled. It
is a simulated bearer capability, not an authenticated subject identity. Keep
it out of logs and do not use this flow to collect real consent.

### `POST /v1/consent/approve` and `POST /v1/consent/deny`

Both accept JSON:

```json
{
  "request_id": "cr_<uuid>",
  "demo_action_code": "<returned local-demo code>"
}
```

Approval response:

```json
{
  "request_id": "cr_<uuid>",
  "status": "approved",
  "consent_token": "<signed JWT>",
  "expires_at": 0
}
```

Denial response:

```json
{ "request_id": "cr_<uuid>", "status": "denied", "expires_at": 0 }
```

Each pending request can transition only once. Approval and creation of its
single token are committed atomically. Possible terminal states include
`approved`, `denied`, `expired`, and `revoked`.

### `POST /v1/consent/status`

Accepts the same `request_id` and `demo_action_code` JSON body; returns
`{ "request_id": "...", "status": "...", "expires_at": 0 }`. The action code
must match the request. With demo actions disabled this route is unavailable.

### `POST /v1/consent/revoke`

Accepts:

```json
{
  "jti": "<jti claim from the issued consent JWT>",
  "demo_action_code": "<same request action code>"
}
```

Returns the request ID, `status: "revoked"`, and expiry. The server checks the
stored token and action-code digest; parsing a JWT claim client-side is only
for identifying the grant to revoke, not evidence that the token is valid.
With demo actions disabled this route is unavailable.

### `POST /v1/generate/verify`

Requires `X-API-Key`. JSON request:

```json
{
  "check_id": "c_original_or_authorized_check",
  "consent_token": "<signed JWT>",
  "target_ref": "same-opaque-target-reference"
}
```

Response:

```json
{ "valid": true, "state": "valid" }
```

An invalid grant is represented as `valid: false` plus a state such as
`expired`, `revoked`, `wrong_scope`, `wrong_app`, `face_mismatch`,
`invalid_signature`, `invalid_token`, `check_not_found`,
`check_not_eligible`, or `unavailable`. A store failure may instead return
`503`. Do not proceed to generation/stamping unless `valid` is exactly true.
The endpoint checks the app, scope, target digest, original check binding,
signature, time claims, and current SQLite revocation state.

## Output stamping and retrieval

### `POST /v1/output/stamp`

Requires `X-API-Key`, `multipart/form-data`:

| Part | Required | Meaning |
|---|---:|---|
| `check_id` | yes | Current, unexpired, same-app `allow` check ID. |
| `image` | yes | PNG, JPEG, or WEBP image, single frame, within configured byte limit. |
| `consent_token` | for Tier 1 grant-bound check | Signed token used by the authorized check. |
| `target_ref` | for Tier 1 grant-bound check | Exact opaque target reference bound to the check and token. |
| `mock_signal` | no | `flagged`, `error`, or `indeterminate`; local test stub only, gated by test flag. |

The endpoint loads the check context from SQLite; it does not accept client
`high_risk`, app identity, decision, or safety evidence. It revalidates any
required grant, bounds the upload while reading, rejects corrupt/unsupported
images, and fails closed on checker exceptions, harmful results, or
indeterminate results. Only after storing the PNG output does it append a
ledger entry; a ledger write failure triggers output cleanup. A check can be
stamped only once.

Success response:

```json
{
  "check_id": "c_0123456789ab",
  "entry_id": "entry_<id>",
  "output_sha256": "<sha256 of downloaded stamped PNG>",
  "pre_stamp_sha256": "<sha256 of uploaded bytes>",
  "phash": "<16 lowercase hexadecimal characters>",
  "label": "AI-generated",
  "created_at": "<ISO-8601 timestamp>",
  "ledger_entry_hash": "<hash-chain entry hash>",
  "output_ref": "out_<uuid>"
}
```

Important errors include `check_not_found`, `check_not_eligible`,
`consent_required`, `consent_store_unavailable`, `output_already_stamped`,
`payload_too_large`, `invalid_image_format`, `harmful_content_detected`,
`result_check_failed`, `safety_check_indeterminate`, and
`output_persistence_failed`.

### `GET /v1/output/download/{output_ref}`

Requires `X-API-Key` for the same server-configured app. Success returns the
raw stamped PNG bytes with `Content-Type: image/png`. Unknown references,
references from another app, evicted outputs, or outputs lost on restart
return `404 output_not_found`. The output store is process-local and capped at
50 entries by default; it is not a durable or time-based guarantee.

## Public provenance endpoints

These endpoints intentionally do not require `X-API-Key` in the current
prototype. They expose limited ledger metadata and should not be treated as a
production public API without a separate threat-model review.

### `GET /v1/ledger/lookup?phash=<16-hex>&max_distance=0`

`phash` is required, 16 hexadecimal characters; `max_distance` is optional,
integer 0–64 (default 0). Exact lookup uses `exact_phash`; a positive distance
enables Hamming-near lookup (`hamming_phash`).

```json
{
  "match": true,
  "method": "exact_phash",
  "provenance": {
    "check_id": "c_0123456789ab",
    "label": "AI-generated",
    "created_at": "<ISO-8601 timestamp>",
    "output_sha256": "<sha256>"
  },
  "message": "Matching provenance ledger entry found.",
  "distance": 0
}
```

On no match, `match` is false and `provenance` and `distance` are null. A
no-match is not evidence of authenticity or falsity. For the future Rescue Kit,
compute the agreed perceptual hash in the browser and send only that hash to
this endpoint—never upload the original victim image for origin lookup.

### `GET /v1/ledger/verify`

Returns:

```json
{
  "valid": true,
  "error": null,
  "entries_count": 1,
  "head_hash": "<current chain head>"
}
```

The endpoint verifies the current process-local chain; it does not provide
durable transparency, a trusted timestamp, authorship proof, or a signed
manifest.

## Frontend integration boundary

Keep endpoint paths, snake_case conversion, multipart construction, API-key
handling, and error normalization behind a small typed API-client module.
Render the server decision and reason codes without converting a failure or
unknown state to allow. The current SDK (`sdk-ts/`) wraps check, stamp,
download, lookup, and consent verification, but not consent request/subject
actions or ledger verification.

Never bundle a shared partner API key or signing secret into a deployed
browser application. A local-only demo may call its local gateway directly;
a deployed frontend needs a trusted server-side boundary for partner
credentials. For Rescue Kit lookup, hash locally and transmit only the agreed
perceptual hash. Keep raw images, prompts, API keys, bearer tokens, action
codes, and subject identity data out of application logs.

## Prototype limitations to carry forward

- Request-risk scoring, face/age assessment, and output safety checking are
  stubs; they are not trustworthy production classifiers.
- Simulated subject approval is not real identity verification or proof that a
  target reference belongs to an approver.
- Consent state is SQLite-backed for a single host. Audit/enforcement,
  output storage, and the provenance ledger are process-local and may reset on
  restart; outputs may also be evicted.
- No production face matching, KMS/HSM, key rotation, signed C2PA guarantee,
  trusted timestamping, authorship proof, legal admissibility, or regulatory
  compliance claim is provided.
- No explicit-capable generation model, React/Vite frontend, evidence ZIP
  builder, complaint draft flow, or production takedown integration is part of
  this handoff.
