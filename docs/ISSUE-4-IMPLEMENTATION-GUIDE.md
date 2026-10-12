# ConsentGuard Issue 4 — Implementation Guide

**Issue:** Build Victim Rescue Kit PWA and End-to-End Demo UI  
**Repository:** https://github.com/ShreyaJ-27/ConsentGuard  
**Suggested branch:** `feature/issue-4-rescue-kit-demo-ui`  
**Goal:** A usable Rescue Kit PWA and integrated harmless PhotoMagic demo. Ignore the timeline in `IMPLEMENTATION-PLAN.md`.

---

## 1. What success looks like

A user can open the Rescue Kit, choose a file, compute its SHA-256 locally, optionally submit only the supported perceptual hash for origin lookup, add URLs/platforms/dates/notes, and download an evidence manifest/ZIP plus editable complaint drafts. Separately, the PhotoMagic demo can submit a harmless edit request to ConsentGuard, show `allow`, `needs_consent`, or `block`, connect to the Consent Passport flow, and show a safely labelled demo output after approval.

The selected evidence file must not be uploaded during local hashing or origin lookup. The app must not promise legal admissibility, guaranteed takedown, anonymity, or safety beyond what it actually implements. Complaint drafts must say **Draft — not legal advice**. Never connect an explicit-capable image-generation model.

## 2. Before giving the task to a coding agent

### Step 1 — Inspect the repository
1. Open `https://github.com/ShreyaJ-27/ConsentGuard`.
2. Read `IMPLEMENTATION-PLAN.md`, `README.md`, current folder structure, dependencies, and existing tests.
3. Check whether `rescue-pwa/`, `demo-app/`, `passport-pwa/`, or similar folders already exist. Extend existing apps rather than generating duplicates.
4. Inspect the endpoint schemas from Member 1 (`POST /v1/check`), Member 2 (consent flow), and Member 3 (`GET /v1/ledger/lookup?phash=...`).

### Step 2 — Create your own branch
From the repo root:

```bash
git status
git checkout main
git pull origin main
git checkout -b feature/issue-4-rescue-kit-demo-ui
```

If there are uncommitted changes, inspect and save them first. Use your team's naming convention if different.

### Step 3 — Coordinate API contracts
Ask the other members for their current schemas, not just proposed schemas. Confirm:
- Member 1: base URL, auth mechanism, `/v1/check` request/response, error shape.
- Member 2: how the UI creates and opens a consent request, status polling/updates, and how a subject approves or denies. Do not implement token signing in the frontend.
- Member 3: exact perceptual-hash algorithm/format, lookup endpoint response, and whether lookup needs authentication.
- Agree whether PhotoMagic belongs in `demo-app/` and the Rescue Kit in `rescue-pwa/`, matching existing repo structure.

### Step 4 — Decide privacy and offline behaviour
- Hash files in the browser using `crypto.subtle.digest("SHA-256", ...)`.
- Never upload the selected file to the origin-lookup endpoint.
- Only send a perceptual hash after an explicit user action and explain what will be sent.
- If a browser API or perceptual hash library is unavailable, show a clear limitation; do not silently upload the file as a fallback.
- Do not claim the whole app works offline unless assets and required flows have been tested offline.
- Do not store sensitive case information in localStorage by default. Provide a clear reset/clear-session action. Use a session-only model for sensitive evidence metadata where practical.

### Step 5 — Set a strict prototype boundary
Must-have:
1. Responsive safety-first Rescue Kit.
2. Client-side SHA-256 and clear privacy copy.
3. Optional origin lookup.
4. Evidence metadata form and `manifest.json`.
5. Downloadable ZIP and readable summary.
6. Editable platform takedown and cybercrime complaint drafts.
7. PhotoMagic flow showing all three gateway decisions.
8. Real API integration with configurable base URL, plus clearly labelled mock mode for local demos.

Stretch only after the core flow works:
- Full offline PWA caching.
- Helper mode with PIN-protected session.
- PDF generation if it adds complexity.
- RFC 3161 timestamping.
- Real screenshot OCR or AI-origin discovery.
- Kannada translation if not already available; English and Hindi first.

### Step 6 — Prepare the coding agent
Use a repository-aware agent that can inspect and edit the repo. Give it the prompt in `ConsentGuard-Issue-4-Coding-Agent-Prompt.md`. Ask it to implement both interfaces, run available tests/build/typecheck, and report actual results. Do not give it secrets or private case material.

### Step 7 — Review privacy and functionality
Run:

```bash
git status
git diff --check
git diff
```

Manually verify in browser devtools/network tab that selecting a file and computing hashes does not send the file to the server. Only an explicit origin-check action should send the supported hash. Confirm that mock mode is visibly labelled and cannot be confused with live backend responses.

### Step 8 — Test, commit, and open PR
Run the app's documented test/build commands, fix failures, and test the main flows manually. Then:

```bash
git add <reviewed-files>
git commit -m "feat: add rescue kit and PhotoMagic demo UI"
git push -u origin feature/issue-4-rescue-kit-demo-ui
```

Open a PR to `main`. Ask Member 1 to review `/v1/check` integration, Member 2 to review the consent hand-off, and Member 3 to review hash lookup behaviour.

---

## 3. Implementation steps

### Step A — Inspect and scaffold carefully
- Reuse the current React/Vite/TypeScript/Tailwind conventions.
- If the repository has no app, create `rescue-pwa/` and `demo-app/` as directed by the implementation plan.
- Keep the apps separate if that avoids coupling the victim-support tool to the demo generator.
- Use a shared API client only if it makes integration simpler; avoid adding a monorepo framework solely for this issue.

### Step B — Build the Rescue Kit safety-first shell
Include:
- A calm landing screen that says the user is not at fault.
- A clear explanation of what stays on the device and what may be sent.
- A quick-exit control with an honest warning that it cannot erase browser/network history.
- English and Hindi strings organised for translation; add Kannada if time allows.
- Accessible forms, visible focus, labels, keyboard navigation, responsive layout, and no graphic/explicit sample content.
- Clear empty, loading, error, success, and offline states.

### Step C — Local file hashing and optional lookup
- Use the browser File API and `crypto.subtle.digest` to compute SHA-256 locally.
- Implement the exact perceptual hash algorithm agreed with Member 3. SHA-256 is not a substitute for perceptual hashing.
- Do not send the original file or its base64 representation to origin lookup.
- Before lookup, show a confirmation such as: “This will send only the perceptual hash to ConsentGuard. The selected file itself will not be uploaded for this check.”
- Send the hash only after the user chooses to check.
- Explain `match`, `no match`, and errors accurately. No match means the current ledger found no supported match; it does not prove the image is genuine or fake.
- If the selected hash algorithm is unavailable, disable lookup and explain why instead of inventing a hash.

### Step D — Evidence metadata and manifest
Let the user add evidence items with fields such as:
- URL or source link.
- Platform/service name.
- Date/time observed (with timezone if known).
- User notes.
- Hashes of files the user deliberately chooses to include, computed locally.

Generate a JSON manifest with a schema/version, creation timestamp, evidence items, available hashes, and an explicit list of fields included. Never fabricate timestamps, device details, or evidence. Label user-entered data as user-provided. Let the user review the manifest before export.

### Step E — Downloadable evidence ZIP and summary
- Create the ZIP client-side where practical (for example, using a maintained ZIP library).
- Include `manifest.json`, a readable summary, and complaint drafts. Include copies of screenshots/files only when the user explicitly selects them for export and understands they will be inside the ZIP.
- If PDF generation is too heavy, ship a clean HTML/Markdown/text summary first and list PDF as a limitation.
- Do not call the pack legally admissible or timestamp-certified unless that specific functionality has actually been implemented and reviewed.
- Provide a clear “clear session” action that clears in-memory case data and generated object URLs where possible.

### Step F — Complaint drafter
Provide editable drafts for:
1. A platform grievance officer / takedown request.
2. A cybercrime complaint draft suitable for the user to review and adapt.

Include only facts the user entered or verified. Use placeholders for missing facts; do not invent a person, URL, date, legal claim, or incident detail. Include a visible disclaimer: **Draft — not legal advice. Review all details before submitting.** Do not auto-submit complaints or upload evidence. Link to official resources and verify contact details rather than hard-coding unverified information.

### Step G — Build PhotoMagic demo UI
- Simple interface: select a harmless image/fixture, choose a structured edit scope, submit request, and display the gateway result.
- Call Member 1's `/v1/check` through the agreed API client.
- Demonstrate Tier 0 allowed, Tier 1 requiring consent, and Tier 2 hard-blocked. Use safe, non-explicit descriptions for the demo.
- If `needs_consent`, hand off to Member 2's Consent Passport request flow and refresh the status using the agreed mechanism.
- Only run a harmless style/cartoon transformation or return a safe placeholder. Do not connect an explicit-capable model.
- If allowed, call Member 3's output-stamping endpoint and show the returned AI label and provenance receipt.
- Show whether the API is in mock mode or connected to the live backend. Do not fabricate live API success in the UI.

### Step H — Integration, tests, and docs
- Centralise API base URL configuration (for example, environment variables).
- Handle loading states, API errors, timeouts, and backend-unavailable state.
- Never expose API secrets in client-side production bundles. If the prototype API key must be supplied by a browser, use only a restricted demo key and document that production apps need a backend proxy.
- Add unit tests for hashing, manifest generation, complaint draft templating, and API client response handling.
- Add tests or manual verification for ZIP contents, lookup payload, and the three PhotoMagic outcomes.
- Add setup commands, `.env.example` if required, and a clear list of mock features and limitations.

---

## 4. Definition of done

- [ ] Rescue Kit runs locally and has a responsive, accessible safety-first UI.
- [ ] SHA-256 is computed client-side.
- [ ] Original file is never sent during origin lookup.
- [ ] Only the agreed perceptual hash is sent after explicit user action.
- [ ] Evidence manifest and downloadable ZIP work.
- [ ] Complaint drafts are editable, use placeholders for missing facts, and display the disclaimer.
- [ ] No automatic reporting or submission occurs.
- [ ] PhotoMagic demonstrates allow, needs-consent, and block.
- [ ] Consent hand-off integrates with Member 2's flow or is clearly labelled mock mode.
- [ ] Allowed harmless outputs call Member 3's stamping endpoint or clearly show mock mode.
- [ ] Errors and unavailable backend are handled honestly.
- [ ] Tests/build pass and setup instructions work.
- [ ] No sensitive user content or secrets are committed.
- [ ] Known limitations are documented.

---

## 5. Coding-agent prompt

Copy the contents of `ConsentGuard-Issue-4-Coding-Agent-Prompt.md` into your repository-aware coding agent.
