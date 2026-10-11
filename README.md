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
- No image upload, face detector, age classifier, explicit-capable generator,
  output scanner, C2PA verification, or provenance stamping is implemented.
  This is a prototype gateway, not a production safety system.
