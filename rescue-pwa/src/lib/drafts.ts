/**
 * drafts.ts — Complaint draft template generator.
 *
 * Generates editable draft text for:
 *   1. A platform grievance officer / takedown request.
 *   2. A cybercrime portal complaint suitable for cybercrime.gov.in.
 *
 * Strict rules:
 *  - Uses placeholders for any missing facts.
 *  - Does not invent URLs, persons, dates, or legal assertions.
 *  - Marks all user-provided data as such.
 *  - Every draft starts with the visible disclaimer.
 *  - Does NOT auto-submit; drafts are text for the user to review and adapt.
 */

export const DRAFT_DISCLAIMER =
  'DRAFT — NOT LEGAL ADVICE. Review all details before submitting. ' +
  'Consult a legal professional and verify all contact information independently.';

export interface DraftInputs {
  /** Platform name where content was found (user-provided) */
  platform?: string;
  /** URL where content was found (user-provided) */
  contentUrl?: string;
  /** Date/time content was first observed (user-provided) */
  observedAt?: string;
  /** Free-text description of the incident (user-provided) */
  incidentDescription?: string;
  /** SHA-256 hex of the evidence file (tool-computed) */
  fileSha256?: string;
  /** Filename (browser-reported) */
  filename?: string;
  /** Complainant name (user-provided) */
  yourName?: string;
}

const PH = (label: string) => `[${label} — please fill in]`;

export function buildTakedownDraft(inputs: DraftInputs): string {
  const {
    platform = PH('Platform name'),
    contentUrl = PH('URL of the content'),
    observedAt = PH('Date/time first observed with timezone'),
    incidentDescription = PH('Brief description of the harmful content'),
    fileSha256,
    filename,
    yourName = PH('Your name'),
  } = inputs;

  const hashLine = fileSha256
    ? `File SHA-256 (tool-computed, browser-side): ${fileSha256}${filename ? ` (${filename})` : ''}`
    : `File SHA-256: ${PH('attach file and compute hash')}`;

  return `${DRAFT_DISCLAIMER}

────────────────────────────────────────────────────────────────

To: Grievance Officer / Trust & Safety Team
Platform: ${platform}
Subject: Takedown Request — Non-Consensual Intimate / Deepfake Image

Dear Grievance Officer,

I am writing to formally request the urgent removal of content that I believe
violates your platform's policies on non-consensual intimate imagery and
deepfake/morphed content.

Content URL:       ${contentUrl}
First observed:    ${observedAt}
Description:       ${incidentDescription}
${hashLine}

The content was reportedly created without the consent of the person depicted.
I am the ${PH('victim / authorised representative')}.

I request that you:
1. Remove the content immediately.
2. Preserve server-side logs and metadata related to this content for at least
   90 days in case they are needed for a legal investigation.
3. Prevent re-upload or sharing of this content.
4. Respond to this request within the timeframe required under applicable law.

Signed,
${yourName}
Date: ${new Date().toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })}

────────────────────────────────────────────────────────────────
Note: This is a draft prepared using the ConsentGuard Rescue Kit. Edit and
verify all details before sending. Contact information for platform grievance
officers must be independently verified at the platform's current website.
`;
}

export function buildCybercrimeComplaintDraft(inputs: DraftInputs): string {
  const {
    platform = PH('Platform name'),
    contentUrl = PH('URL of the content'),
    observedAt = PH('Date/time first observed with timezone'),
    incidentDescription = PH('Brief description of the harmful content'),
    fileSha256,
    filename,
    yourName = PH('Your name'),
  } = inputs;

  const hashLine = fileSha256
    ? `File SHA-256 (browser-computed): ${fileSha256}${filename ? ` (${filename})` : ''}`
    : `File SHA-256: ${PH('attach file and compute hash')}`;

  return `${DRAFT_DISCLAIMER}

────────────────────────────────────────────────────────────────

CYBERCRIME COMPLAINT DRAFT
Portal: cybercrime.gov.in | Helpline: 1930
Meri Trustline (emotional support): 6363176363

Date of complaint: ${new Date().toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })}
Complainant name: ${yourName}
Complainant address: ${PH('Your address')}
Complainant phone: ${PH('Your phone number')}
Complainant email: ${PH('Your email address')}

─── Incident Details ───────────────────────────────────────────

Type of cybercrime: Non-Consensual Intimate Image / Morphed / Deepfake Image

Platform where found: ${platform}
Content URL:          ${contentUrl}
Date/time observed:   ${observedAt}

Description of incident:
${incidentDescription}

Evidence:
- ${hashLine}
- Screenshot(s): ${PH('attach screenshots')}
- Any other evidence: ${PH('list other evidence')}

Suspect details (if known):
- Name: ${PH('Suspect name or "Unknown"')}
- Account/username: ${PH('Suspect account URL or handle')}
- Any other details: ${PH('e.g. phone number, email')}

─── Supporting Laws (for reference only — verify with a lawyer) ─

- Section 67 / 67A of the Information Technology Act 2000 (obscene material)
- Section 354C of the Indian Penal Code (voyeurism, as applicable)
- Relevant provisions of the DPDP Act 2023 / IT Rules 2021 (as applicable)

─── Declaration ────────────────────────────────────────────────

I declare that the information given in this complaint is true and correct to
the best of my knowledge and belief. I understand that a false complaint is
punishable under law.

Signature: ${PH('Sign here')}
Name: ${yourName}
Date: ${new Date().toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })}

────────────────────────────────────────────────────────────────
IMPORTANT: Before filing, visit cybercrime.gov.in and use the official online
reporting portal. This draft does not constitute a filed complaint. Consult a
legal professional, or contact iCall (9152987821) or Meri Trustline (6363176363)
for guidance.
`;
}
