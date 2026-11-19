/**
 * Two-locale message catalogue (English / Hindi).
 *
 * Coverage is deliberate and partial: the application shell, the challenge
 * browser chrome, the citizen submission flow and the account pages. Narrative
 * pages (home body copy, methodology, admin console) remain English-only until
 * a translator reviews them — see docs/MASTER_PLAN.md, Phase 6 status.
 */

export type Locale = "en" | "hi";

export const LOCALES: { code: Locale; label: string; short: string; htmlLang: string }[] = [
  { code: "en", label: "English", short: "EN", htmlLang: "en" },
  { code: "hi", label: "हिंदी", short: "हि", htmlLang: "hi" },
];

const en = {
  "brand.tag": "Jharkhand",

  "nav.challenges": "Challenges",
  "nav.partners": "Partners",
  "nav.admin": "Admin dashboard",
  "nav.methodology": "Methodology",
  "nav.reports": "My dashboard",
  "nav.partnerPortal": "Staff dashboard",
  "nav.accountHome": "My dashboard",
  "nav.signIn": "Sign in",
  "nav.report": "Report an issue",
  "nav.openMenu": "Open menu",
  "nav.closeMenu": "Close menu",
  "nav.home": "ChallengeMap home",

  "theme.toDark": "Switch to dark theme",
  "theme.toLight": "Switch to light theme",

  "locale.label": "Language",

  "challenges.eyebrow": "Challenge library",
  "challenges.title": "challenges, ranked and ready to be picked up",
  "challenges.lead":
    "Every cluster here is a group of similar citizen reports, not a manual category. Filter by what you can act on.",
  "challenges.search": "Search title, summary or tag…",
  "challenges.searchLabel": "Search challenges",
  "challenges.allDistricts": "All districts",
  "challenges.allDomains": "All domains",
  "challenges.districtLabel": "Filter by district",
  "challenges.sortLabel": "Sort challenges",
  "challenges.sortPriority": "Priority",
  "challenges.sortReports": "Most reported",
  "challenges.sortAffected": "Largest reach",
  "challenges.sortRecent": "Recently active",
  "challenges.sortPrefix": "Sort",
  "challenges.clear": "Clear",
  "challenges.showing": "Showing",
  "challenges.of": "of",
  "challenges.unit": "challenges",
  "challenges.empty": "No challenge matches those filters",
  "challenges.emptyHint": "Try a broader district, or clear the domain chips.",
  "challenges.reset": "Reset filters",
  "challenges.reports": "reports",
  "challenges.districts": "districts",
  "challenges.affected": "affected",
  "challenges.viewBrief": "View brief",
  "challenges.demoData": "Demo dataset (API unavailable or empty)",

  "submit.eyebrow": "Citizen report",
  "submit.title": "Tell us what is not working",
  "submit.lead":
    "Write in Hindi, English or Hinglish. Before your report becomes a new challenge, we check whether someone nearby already reported the same problem — that is how the map stays honest instead of noisy.",
  "submit.signInFirst": "Sign in to send a report",
  "submit.signInHint":
    "Reports are tied to an account so that duplicates can be merged and follow-ups delivered. Demo credentials are created with CHALLENGEMAP_BOOTSTRAP_ADMIN.",
  "submit.apiOffline":
    "The report service is unreachable, so nothing was sent. Start the API (see api/README.md) and try again.",

  "auth.signInTitle": "Sign in",
  "auth.signInLead": "Citizens, partner organisations and administrators share one login.",
  "auth.email": "Email address",
  "auth.emailAddress": "Email address",
  "auth.emailOnlyHint": "Sign in with the email address linked to your account.",
  "auth.signInAs": "Sign in as",
  "auth.accountMenu": "Account menu",
  "auth.loginApiOutdated":
    "The login service is out of date. Restart the API server from this project, then refresh this page.",
  "auth.roleStaff": "Staff",
  "auth.roleAdmin": "Admin",
  "auth.password": "Password",
  "auth.signInCta": "Sign in",
  "auth.signingIn": "Signing in…",
  "auth.noAccount": "No account?",
  "auth.createOne": "Create one",
  "auth.registerTitle": "Create an account",
  "auth.registerLead":
    "Citizens report issues. Partner organisations receive matched challenges.",
  "auth.signupType": "Account type",
  "auth.fullName": "Full name",
  "auth.district": "District",
  "auth.organizationName": "Organization name",
  "auth.jobTitle": "Your role/title",
  "auth.username": "Username",
  "auth.usernameHint": "3–32 characters. Letters, numbers, dots, underscores or hyphens.",
  "auth.confirmPassword": "Confirm password",
  "auth.passwordHint": "Minimum 12 characters. Stored as a salted hash, never in plain text.",
  "auth.partnerNote": "Partner requests are reviewed by an administrator before access is enabled.",
  "auth.partnerRequestSubmitted": "Your partner account request has been submitted. An administrator must approve it before you can sign in.",
  "auth.partnerRequestCta": "Request partner account",
  "auth.partnerRequesting": "Submitting request…",
  "auth.errorGeneric": "Could not reach the account service. Start the API and try again.",
  "auth.org": "Organisation",
  "auth.roleCitizen": "Citizen",
  "auth.rolePartner": "Partner",
  "auth.citizenHint": "report issues",
  "auth.partnerHint": "solve challenges",
  "auth.createCitizen": "Create citizen account",
  "auth.createPartner": "Create partner account",
  "auth.creating": "Creating…",
  "auth.alreadyRegistered": "Already registered?",
  "auth.welcomeBack": "Signed in",
  "auth.signOut": "Sign out",
} as const;

export type MessageKey = keyof typeof en;

const hi: Record<MessageKey, string> = {
  "brand.tag": "झारखंड",

  "nav.challenges": "चुनौतियाँ",
  "nav.partners": "साझेदार",
  "nav.admin": "प्रशासन डैशबोर्ड",
  "nav.methodology": "कार्यप्रणाली",
  "nav.reports": "मेरा डैशबोर्ड",
  "nav.partnerPortal": "स्टाफ़ डैशबोर्ड",
  "nav.accountHome": "मेरा डैशबोर्ड",
  "nav.signIn": "साइन इन",
  "nav.report": "समस्या दर्ज करें",
  "nav.openMenu": "मेन्यू खोलें",
  "nav.closeMenu": "मेन्यू बंद करें",
  "nav.home": "चैलेंजमैप मुखपृष्ठ",

  "theme.toDark": "गहरी थीम चुनें",
  "theme.toLight": "हल्की थीम चुनें",

  "locale.label": "भाषा",

  "challenges.eyebrow": "चुनौती संग्रह",
  "challenges.title": "चुनौतियाँ, प्राथमिकता के क्रम में — किसी के उठाने के लिए तैयार",
  "challenges.lead":
    "यहाँ हर समूह एक जैसी नागरिक शिकायतों का है, कोई मनमाना वर्ग नहीं। जो आप हल कर सकते हैं, उसी के अनुसार छाँटें।",
  "challenges.search": "शीर्षक, सार या टैग खोजें…",
  "challenges.searchLabel": "चुनौतियाँ खोजें",
  "challenges.allDistricts": "सभी ज़िले",
  "challenges.allDomains": "सभी क्षेत्र",
  "challenges.districtLabel": "ज़िले के अनुसार छाँटें",
  "challenges.sortLabel": "क्रम तय करें",
  "challenges.sortPriority": "प्राथमिकता",
  "challenges.sortReports": "सर्वाधिक शिकायतें",
  "challenges.sortAffected": "सबसे बड़ा दायरा",
  "challenges.sortRecent": "हाल में सक्रिय",
  "challenges.sortPrefix": "क्रम",
  "challenges.clear": "हटाएँ",
  "challenges.showing": "दिखा रहे हैं",
  "challenges.of": "में से",
  "challenges.unit": "चुनौतियाँ",
  "challenges.empty": "इन फ़िल्टरों से कोई चुनौती नहीं मिली",
  "challenges.emptyHint": "कोई बड़ा ज़िला चुनें या क्षेत्र के चिप हटाएँ।",
  "challenges.reset": "फ़िल्टर रीसेट करें",
  "challenges.reports": "शिकायतें",
  "challenges.districts": "ज़िले",
  "challenges.affected": "प्रभावित",
  "challenges.viewBrief": "विवरण देखें",
  "challenges.demoData": "डेमो डेटा (API उपलब्ध नहीं या खाली)",

  "submit.eyebrow": "नागरिक शिकायत",
  "submit.title": "बताइए क्या काम नहीं कर रहा",
  "submit.lead":
    "हिंदी, अंग्रेज़ी या हिंग्लिश में लिखें। आपकी शिकायत नई चुनौती बने, उससे पहले हम देखते हैं कि कहीं पास में किसी ने यही समस्या दर्ज नहीं की — इसी से नक्शा शोर नहीं, सच दिखाता है।",
  "submit.signInFirst": "शिकायत भेजने के लिए साइन इन करें",
  "submit.signInHint":
    "शिकायतें खाते से जुड़ी होती हैं ताकि दोहराव जोड़ा जा सके और आगे की सूचना पहुँचे। डेमो खाता CHALLENGEMAP_BOOTSTRAP_ADMIN से बनता है।",
  "submit.apiOffline":
    "शिकायत सेवा उपलब्ध नहीं है, इसलिए कुछ नहीं भेजा गया। API चालू करें (api/README.md देखें) और फिर कोशिश करें।",

  "auth.signInTitle": "साइन इन",
  "auth.signInLead": "नागरिक, साझेदार संस्थाएँ और प्रशासक — सबका एक ही लॉगिन।",
  "auth.email": "ईमेल पता",
  "auth.emailAddress": "ईमेल पता",
  "auth.emailOnlyHint": "अपने खाते से जुड़े ईमेल पते से साइन इन करें।",
  "auth.signInAs": "इस रूप में साइन इन करें",
  "auth.accountMenu": "खाता मेन्यू",
  "auth.loginApiOutdated":
    "लॉगिन सेवा का संस्करण पुराना है। इस प्रोजेक्ट का API सर्वर रीस्टार्ट करें, फिर यह पेज रिफ़्रेश करें।",
  "auth.roleStaff": "कर्मचारी",
  "auth.roleAdmin": "प्रशासक",
  "auth.password": "पासवर्ड",
  "auth.signInCta": "साइन इन",
  "auth.signingIn": "साइन इन हो रहा है…",
  "auth.noAccount": "खाता नहीं है?",
  "auth.createOne": "बनाइए",
  "auth.registerTitle": "खाता बनाएँ",
  "auth.registerLead": "नागरिक समस्याएँ दर्ज करते हैं। साझेदार संस्थाओं को मिलती-जुलती चुनौतियाँ मिलती हैं।",
  "auth.signupType": "खाते का प्रकार",
  "auth.fullName": "पूरा नाम",
  "auth.district": "ज़िला",
  "auth.organizationName": "संस्था का नाम",
  "auth.jobTitle": "आपकी भूमिका/पद",
  "auth.username": "उपयोगकर्ता नाम",
  "auth.usernameHint": "3–32 अक्षर। अक्षर, अंक, बिंदु, अंडरस्कोर या हाइफ़न।",
  "auth.confirmPassword": "पासवर्ड दोबारा",
  "auth.passwordHint": "कम से कम 12 अक्षर। नमक के साथ हैश में रखा जाता है, कभी सादे रूप में नहीं।",
  "auth.partnerNote": "साझेदार अनुरोध की समीक्षा प्रशासक करता है; अनुमति मिलने के बाद ही पहुँच सक्रिय होगी।",
  "auth.partnerRequestSubmitted": "आपका साझेदार खाता अनुरोध भेज दिया गया है। साइन इन करने से पहले प्रशासक की अनुमति आवश्यक है।",
  "auth.partnerRequestCta": "साझेदार खाते का अनुरोध करें",
  "auth.partnerRequesting": "अनुरोध भेजा जा रहा है…",
  "auth.errorGeneric": "खाता सेवा उपलब्ध नहीं है। API चालू करें और फिर कोशिश करें।",
  "auth.org": "संस्था",
  "auth.roleCitizen": "नागरिक",
  "auth.rolePartner": "साझेदार",
  "auth.citizenHint": "समस्याएँ दर्ज करें",
  "auth.partnerHint": "चुनौतियाँ हल करें",
  "auth.createCitizen": "नागरिक खाता बनाएँ",
  "auth.createPartner": "साझेदार खाता बनाएँ",
  "auth.creating": "बन रहा है…",
  "auth.alreadyRegistered": "पहले से पंजीकृत हैं?",
  "auth.welcomeBack": "साइन इन हो गया",
  "auth.signOut": "साइन आउट",
};

export const dictionaries: Record<Locale, Record<MessageKey, string>> = { en, hi };

export function isLocale(value: unknown): value is Locale {
  return value === "en" || value === "hi";
}

export function translate(locale: Locale, key: MessageKey): string {
  return dictionaries[locale][key] ?? dictionaries.en[key];
}
