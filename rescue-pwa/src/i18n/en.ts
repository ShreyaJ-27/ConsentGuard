/**
 * en.ts — English UI strings for the Rescue Kit.
 * Structured so that hi.ts (Hindi) and future Kannada translations can mirror exactly.
 */

/**
 * The shape of the string table — used by all locales.
 * Defined as an interface so Hindi/Kannada translations can satisfy it
 * without being constrained to literal string values.
 */
export interface Strings {
  app: { title: string; tagline: string };
  landing: {
    notAtFault: string; notAtFaultDetail: string; privacyHeading: string; privacyDetail: string;
    quickExitLabel: string; quickExitWarning: string; helplines: string; helplinesDetail: string;
    cybercrimePortal: string; startButton: string;
  };
  fileHasher: {
    heading: string; instruction: string; chooseFile: string; hashing: string;
    sha256Label: string; dhashLabel: string; dhashUnavailable: string;
    notAnImage: string; privacy: string;
  };
  originLookup: {
    heading: string; explanation: string; confirmButton: string; cancelButton: string;
    checking: string; resultMatch: string; resultNoMatch: string; resultError: string;
    mockBadge: string; disabled: string; notConfirmed: string;
  };
  evidenceForm: {
    heading: string; addItem: string; removeItem: string; urlLabel: string; urlPlaceholder: string;
    platformLabel: string; platformPlaceholder: string; observedAtLabel: string;
    notesLabel: string; notesPlaceholder: string; userProvidedNote: string;
  };
  manifestPreview: { heading: string; description: string; disclaimer: string };
  zipExport: {
    heading: string; downloadButton: string; includeFile: string; fileWarning: string;
    clearSession: string; clearWarning: string;
  };
  complaints: {
    heading: string; disclaimer: string; takedownTab: string; cybercrimeTab: string;
    editNote: string; copyButton: string; copied: string; yourNameLabel: string; yourNamePlaceholder: string;
  };
  common: { loading: string; error: string; retry: string; close: string; back: string; next: string; optional: string };
}

export const en: Strings = {
  app: {
    title: 'Rescue Kit',
    tagline: 'Private, on-device tools to help you document and report.',
  },
  landing: {
    notAtFault: 'You are not at fault.',
    notAtFaultDetail:
      'What happened to you is wrong. This tool is here to help you quietly and privately.',
    privacyHeading: 'What stays on your device',
    privacyDetail:
      'Hashing and evidence building happen entirely in your browser. ' +
      'No files are uploaded to any server. ' +
      'Only a perceptual hash (a small fingerprint, not the file itself) may be sent ' +
      'to check if the image is known — and only if you choose to check.',
    quickExitLabel: 'Quick Exit',
    quickExitWarning:
      'This will navigate away from the page. It cannot erase your browser history or network logs.',
    helplines: 'Helplines',
    helplinesDetail:
      'National Cyber Helpline: 1930  |  Meri Trustline: 6363176363  |  iCall: 9152987821',
    cybercrimePortal: 'cybercrime.gov.in',
    startButton: 'Start — I understand this tool is for documentation',
  },
  fileHasher: {
    heading: 'Step 1 — Select a file',
    instruction:
      'Select the image or video file. It will be hashed locally and will not be uploaded.',
    chooseFile: 'Choose file',
    hashing: 'Computing hash…',
    sha256Label: 'SHA-256 (tool-computed, browser-side)',
    dhashLabel: 'Perceptual hash / dHash (tool-computed, browser-side)',
    dhashUnavailable:
      'Perceptual hash unavailable — the Canvas API could not load the image. ' +
      'Origin lookup will be disabled for this file.',
    notAnImage: 'Selected file is not an image. Perceptual hashing is not available.',
    privacy: 'This file has not been uploaded. Hashes were computed in your browser.',
  },
  originLookup: {
    heading: 'Step 2 — Optional: Check origin (perceptual hash only)',
    explanation:
      'This will send only the perceptual fingerprint (dHash) to the ConsentGuard ledger. ' +
      'The file itself will not be uploaded.',
    confirmButton: 'Yes, send only the hash to check origin',
    cancelButton: 'Skip this step',
    checking: 'Checking ledger…',
    resultMatch: 'Match found — this image may have been processed through a ConsentGuard-connected app.',
    resultNoMatch:
      'No match found in the current ledger. ' +
      'This does not prove the image is genuine or that it was not created by other tools.',
    resultError: 'Lookup failed',
    mockBadge: '⚠ MOCK MODE — ledger lookup not connected. Result is simulated.',
    disabled: 'Perceptual hash unavailable — origin lookup disabled.',
    notConfirmed: 'Perceptual hash format not yet confirmed with Member 3 (dHash used as placeholder).',
  },
  evidenceForm: {
    heading: 'Step 3 — Evidence details',
    addItem: 'Add evidence item',
    removeItem: 'Remove',
    urlLabel: 'URL where content was found',
    urlPlaceholder: 'https://…',
    platformLabel: 'Platform / service',
    platformPlaceholder: 'e.g. Instagram, Telegram',
    observedAtLabel: 'Date/time observed',
    notesLabel: 'Notes',
    notesPlaceholder: 'What you saw, how you found it…',
    userProvidedNote: 'All fields are user-provided and have not been independently verified.',
  },
  manifestPreview: {
    heading: 'Step 4 — Review manifest before export',
    description: 'This is the manifest.json that will be included in your evidence ZIP.',
    disclaimer:
      'This evidence pack is a collection aid only. It is not legally admissible ' +
      'on its own and has not been reviewed by a lawyer.',
  },
  zipExport: {
    heading: 'Step 5 — Download evidence pack',
    downloadButton: 'Download evidence-pack.zip',
    includeFile: 'Include the selected file in the ZIP (adds it to the evidence/ folder)',
    fileWarning:
      'Including the file will add it to the ZIP. Only do this if you intend to keep ' +
      'a local copy of the evidence file.',
    clearSession: 'Clear session and start over',
    clearWarning:
      'This will clear all evidence data from memory. ' +
      'Downloaded ZIPs will remain on your device.',
  },
  complaints: {
    heading: 'Step 6 — Complaint drafts',
    disclaimer:
      'DRAFT — NOT LEGAL ADVICE. Review all details before submitting. ' +
      'Consult a legal professional and verify contact information independently.',
    takedownTab: 'Platform takedown request',
    cybercrimeTab: 'Cybercrime complaint',
    editNote: 'Edit the draft below before sending.',
    copyButton: 'Copy draft',
    copied: 'Copied!',
    yourNameLabel: 'Your name (optional — for personalising drafts)',
    yourNamePlaceholder: 'Leave blank to use placeholder',
  },
  common: {
    loading: 'Loading…',
    error: 'An error occurred.',
    retry: 'Retry',
    close: 'Close',
    back: 'Back',
    next: 'Next',
    optional: 'optional',
  },
};

