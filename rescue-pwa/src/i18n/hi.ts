/**
 * hi.ts — Hindi UI strings for the Rescue Kit.
 * Mirrors en.ts structure exactly to make completeness checking easy.
 * Translation note: This is a prototype translation; please have a
 * Hindi speaker review before production use.
 */
import type { Strings } from './en';

export const hi: Strings = {
  app: {
    title: 'रेस्क्यू किट',
    tagline: 'दस्तावेज़ीकरण और रिपोर्टिंग के लिए निजी, ऑन-डिवाइस टूल।',
  },
  landing: {
    notAtFault: 'इसमें आपकी कोई गलती नहीं है।',
    notAtFaultDetail:
      'जो आपके साथ हुआ वह गलत है। यह टूल आपकी चुपचाप और निजी तरीके से मदद करने के लिए यहाँ है।',
    privacyHeading: 'आपके डिवाइस पर क्या रहता है',
    privacyDetail:
      'हैशिंग और साक्ष्य निर्माण पूरी तरह आपके ब्राउज़र में होता है। ' +
      'कोई फ़ाइल किसी सर्वर पर अपलोड नहीं की जाती। ' +
      'केवल एक perceptual hash (फ़ाइल नहीं, एक छोटा फिंगरप्रिंट) भेजा जा सकता है ' +
      'यह जाँचने के लिए कि छवि ज्ञात है या नहीं — और केवल तब जब आप जाँच करना चाहें।',
    quickExitLabel: 'त्वरित बाहर निकलें',
    quickExitWarning:
      'यह पेज से बाहर ले जाएगा। यह आपका ब्राउज़र इतिहास या नेटवर्क लॉग नहीं मिटा सकता।',
    helplines: 'हेल्पलाइन',
    helplinesDetail:
      'राष्ट्रीय साइबर हेल्पलाइन: 1930  |  मेरी ट्रस्टलाइन: 6363176363  |  iCall: 9152987821',
    cybercrimePortal: 'cybercrime.gov.in',
    startButton: 'शुरू करें — मैं समझता/समझती हूँ कि यह टूल दस्तावेज़ीकरण के लिए है',
  },
  fileHasher: {
    heading: 'चरण 1 — फ़ाइल चुनें',
    instruction:
      'छवि या वीडियो फ़ाइल चुनें। यह स्थानीय रूप से हैश की जाएगी और अपलोड नहीं होगी।',
    chooseFile: 'फ़ाइल चुनें',
    hashing: 'हैश कंप्यूट हो रहा है…',
    sha256Label: 'SHA-256 (टूल-कंप्यूटेड, ब्राउज़र-साइड)',
    dhashLabel: 'Perceptual hash / dHash (टूल-कंप्यूटेड, ब्राउज़र-साइड)',
    dhashUnavailable:
      'Perceptual hash उपलब्ध नहीं — Canvas API छवि लोड नहीं कर सका। ' +
      'इस फ़ाइल के लिए ऑरिजिन लुकअप अक्षम होगा।',
    notAnImage: 'चुनी हुई फ़ाइल एक छवि नहीं है। Perceptual hashing उपलब्ध नहीं है।',
    privacy: 'यह फ़ाइल अपलोड नहीं हुई। हैश आपके ब्राउज़र में कंप्यूट किए गए थे।',
  },
  originLookup: {
    heading: 'चरण 2 — वैकल्पिक: मूल जाँचें (केवल perceptual hash)',
    explanation:
      'यह केवल perceptual fingerprint (dHash) को ConsentGuard लेजर को भेजेगा। ' +
      'फ़ाइल स्वयं अपलोड नहीं होगी।',
    confirmButton: 'हाँ, केवल hash भेजें मूल जाँचने के लिए',
    cancelButton: 'यह चरण छोड़ें',
    checking: 'लेजर जाँच रहा है…',
    resultMatch: 'मिलान मिला — यह छवि किसी ConsentGuard-जुड़े ऐप से संसाधित हो सकती है।',
    resultNoMatch:
      'वर्तमान लेजर में कोई मिलान नहीं। ' +
      'इससे यह साबित नहीं होता कि छवि असली है या अन्य टूल से नहीं बनाई गई।',
    resultError: 'लुकअप विफल',
    mockBadge: '⚠ MOCK मोड — लेजर लुकअप कनेक्ट नहीं है। परिणाम सिमुलेटेड है।',
    disabled: 'Perceptual hash उपलब्ध नहीं — ऑरिजिन लुकअप अक्षम।',
    notConfirmed: 'Perceptual hash प्रारूप अभी Member 3 से पुष्टि नहीं हुई (dHash placeholder के रूप में उपयोग)।',
  },
  evidenceForm: {
    heading: 'चरण 3 — साक्ष्य विवरण',
    addItem: 'साक्ष्य आइटम जोड़ें',
    removeItem: 'हटाएँ',
    urlLabel: 'जहाँ सामग्री मिली वह URL',
    urlPlaceholder: 'https://…',
    platformLabel: 'प्लेटफ़ॉर्म / सेवा',
    platformPlaceholder: 'जैसे Instagram, Telegram',
    observedAtLabel: 'देखे जाने की तारीख/समय',
    notesLabel: 'नोट्स',
    notesPlaceholder: 'आपने क्या देखा, यह कैसे मिला…',
    userProvidedNote: 'सभी फ़ील्ड उपयोगकर्ता द्वारा प्रदान की गई हैं और स्वतंत्र रूप से सत्यापित नहीं हैं।',
  },
  manifestPreview: {
    heading: 'चरण 4 — निर्यात से पहले manifest की समीक्षा करें',
    description: 'यह manifest.json है जो आपके साक्ष्य ZIP में शामिल होगा।',
    disclaimer:
      'यह साक्ष्य पैक केवल एक संग्रह सहायता है। यह अपने आप में कानूनी रूप से स्वीकार्य नहीं है ' +
      'और किसी वकील द्वारा समीक्षा नहीं की गई है।',
  },
  zipExport: {
    heading: 'चरण 5 — साक्ष्य पैक डाउनलोड करें',
    downloadButton: 'evidence-pack.zip डाउनलोड करें',
    includeFile: 'ZIP में चुनी हुई फ़ाइल शामिल करें (इसे evidence/ फ़ोल्डर में जोड़ता है)',
    fileWarning:
      'फ़ाइल शामिल करने से यह ZIP में जुड़ जाएगी। केवल तभी करें जब आप साक्ष्य फ़ाइल की स्थानीय प्रति रखना चाहते हों।',
    clearSession: 'सत्र साफ़ करें और फिर से शुरू करें',
    clearWarning:
      'इससे सभी साक्ष्य डेटा मेमोरी से साफ़ हो जाएगा। ' +
      'डाउनलोड किए गए ZIP आपके डिवाइस पर रहेंगे।',
  },
  complaints: {
    heading: 'चरण 6 — शिकायत मसौदे',
    disclaimer:
      'मसौदा — कानूनी सलाह नहीं। सबमिट करने से पहले सभी विवरण जाँचें। ' +
      'किसी कानूनी पेशेवर से परामर्श करें और संपर्क जानकारी स्वतंत्र रूप से सत्यापित करें।',
    takedownTab: 'प्लेटफ़ॉर्म टेकडाउन अनुरोध',
    cybercrimeTab: 'साइबर अपराध शिकायत',
    editNote: 'भेजने से पहले नीचे दिए मसौदे को संपादित करें।',
    copyButton: 'मसौदा कॉपी करें',
    copied: 'कॉपी हो गया!',
    yourNameLabel: 'आपका नाम (वैकल्पिक — मसौदे को व्यक्तिगत बनाने के लिए)',
    yourNamePlaceholder: 'placeholder उपयोग करने के लिए खाली छोड़ें',
  },
  common: {
    loading: 'लोड हो रहा है…',
    error: 'एक त्रुटि हुई।',
    retry: 'पुनः प्रयास करें',
    close: 'बंद करें',
    back: 'वापस',
    next: 'अगला',
    optional: 'वैकल्पिक',
  },
};
