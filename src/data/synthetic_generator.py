"""Deterministic synthetic complaint corpus for ChallengeMap.

Why this exists
---------------
No openly downloadable bulk corpus of Jharkhand citizen complaints is available.
The official portals (PGMS, DFCA PGMS, Jharkhand MyGov) expose single-complaint
lodgement or tiny comment threads, and CPGRAMS raw records are gated behind a
hackathon registration. See docs/MASTER_PLAN.md section 4.

So the development corpus is generated here, deliberately, and every row is
labelled ``source_type="synthetic"``. ``prepare_complaints`` refuses to mark a
synthetic row as verified, and the interface surfaces the same label.

Design goals
------------
* Reproducible: same seed -> byte-identical output.
* Realistic shape: 24 districts weighted by population, 12 domains, ~70
  sub-issues, Hindi/English/Hinglish phrasing, monsoon seasonality, month-end
  entitlement spikes.
* Measurable: duplicates are injected at known rates, and every row carries
  ground-truth domain/sub-issue/duplicate group so clustering and deduplication
  can be scored (ARI/NMI/purity, precision/recall/F1) instead of eyeballed.

The generator is imported by ``scripts/generate_corpus.py``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Sequence

import pandas as pd

from src.data.complaints import COMPLAINT_COLUMNS, prepare_complaints

GENERATOR_VERSION = "1.1.0"

# Approximate 2011 census population shares, used ONLY as sampling weights.
# They are not presented as current official statistics anywhere in the project.
DISTRICT_WEIGHTS: dict[str, int] = {
    "Bokaro": 2062,
    "Chatra": 1042,
    "Deoghar": 1492,
    "Dhanbad": 2684,
    "Dumka": 1321,
    "East Singhbhum": 2293,
    "Garhwa": 1322,
    "Giridih": 2445,
    "Godda": 1313,
    "Gumla": 1025,
    "Hazaribagh": 1734,
    "Jamtara": 791,
    "Khunti": 531,
    "Koderma": 716,
    "Latehar": 726,
    "Lohardaga": 461,
    "Pakur": 900,
    "Palamu": 1939,
    "Ramgarh": 949,
    "Ranchi": 2914,
    "Sahibganj": 1150,
    "Seraikela-Kharsawan": 1065,
    "Simdega": 599,
    "West Singhbhum": 1502,
}

DOMAINS: dict[str, str] = {
    "water": "Water Supply",
    "sanitation": "Sanitation & Waste",
    "roads": "Roads & Connectivity",
    "electricity": "Electricity",
    "health": "Healthcare",
    "education": "Education",
    "food": "Food & PDS",
    "welfare": "Welfare & Pensions",
    "land": "Land & Revenue",
    "employment": "Employment & Livelihoods",
    "agriculture": "Agriculture & Irrigation",
    "safety": "Safety & Environment",
}

# Monthly reporting propensity by domain (Jan..Dec). Monsoon drives water,
# sanitation, roads and agriculture; summer drives power and water.
SEASONALITY: dict[str, tuple[float, ...]] = {
    "water": (0.7, 0.7, 0.8, 1.0, 1.4, 2.2, 2.6, 2.4, 1.6, 1.0, 0.7, 0.6),
    "sanitation": (0.8, 0.8, 0.9, 1.0, 1.1, 1.6, 2.0, 1.8, 1.4, 1.0, 0.8, 0.8),
    "roads": (1.0, 0.9, 0.9, 1.0, 1.1, 1.5, 2.4, 2.2, 1.3, 1.0, 0.9, 0.9),
    "electricity": (1.0, 1.0, 1.1, 1.3, 1.6, 1.7, 1.5, 1.4, 1.2, 1.0, 0.9, 0.9),
    "health": (1.0, 0.9, 1.0, 1.1, 1.2, 1.5, 1.9, 1.8, 1.4, 1.1, 1.0, 1.0),
    "education": (1.0, 1.0, 1.0, 1.2, 1.2, 1.5, 1.6, 1.2, 1.0, 1.0, 1.0, 0.9),
    "food": (1.1, 1.0, 1.0, 1.1, 1.1, 1.1, 1.2, 1.1, 1.1, 1.1, 1.0, 1.1),
    "welfare": (1.0, 1.0, 1.1, 1.1, 1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.1, 1.0),
    "land": (1.0, 1.0, 1.0, 1.1, 1.1, 1.0, 1.0, 1.0, 1.0, 1.1, 1.1, 1.0),
    "employment": (1.0, 1.0, 1.1, 1.2, 1.1, 1.0, 0.9, 1.0, 1.1, 1.2, 1.1, 1.0),
    "agriculture": (0.8, 0.9, 1.0, 1.1, 1.2, 1.8, 2.2, 2.0, 1.3, 1.0, 0.8, 0.7),
    "safety": (1.0, 1.0, 1.0, 1.1, 1.1, 1.2, 1.2, 1.1, 1.1, 1.1, 1.0, 1.0),
}

LanguageMix = tuple[tuple[str, float], ...]
LANGUAGE_MIX: LanguageMix = (("hi", 0.45), ("en", 0.35), ("hinglish", 0.20))


@dataclass(frozen=True)
class SubIssue:
    slug: str
    domain: str
    en: str
    hi: str
    severity_weights: tuple[float, float, float, float]  # low, medium, high, critical


# fmt: off
SUB_ISSUES: tuple[SubIssue, ...] = (
    # water
    SubIssue("handpump_dry", "water", "community handpump", "हैंडपंप", (0.05, 0.20, 0.35, 0.40)),
    SubIssue("tap_no_supply", "water", "piped water connection", "पाइप से पानी", (0.10, 0.30, 0.35, 0.25)),
    SubIssue("water_quality", "water", "drinking water quality", "पीने के पानी की गुणवत्ता", (0.05, 0.25, 0.40, 0.30)),
    SubIssue("tanker_delay", "water", "water tanker service", "पानी का टैंकर", (0.15, 0.35, 0.35, 0.15)),
    SubIssue("public_well", "water", "public well", "सार्वजनिक कुआँ", (0.20, 0.35, 0.30, 0.15)),
    SubIssue("water_testing", "water", "water testing facility", "पानी की जाँच", (0.25, 0.35, 0.30, 0.10)),
    # sanitation
    SubIssue("open_drain", "sanitation", "open drain near the school", "खुली नाली", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("toilet_blocked", "sanitation", "community toilet block", "सामुदायिक शौचालय", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("garbage_collection", "sanitation", "garbage collection", "कचरा उठान", (0.25, 0.40, 0.25, 0.10)),
    SubIssue("drain_overflow", "sanitation", "storm water drain", "बरसाती नाली", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("public_toilet_water", "sanitation", "water supply at the public toilet", "सार्वजनिक शौचालय में पानी", (0.15, 0.35, 0.35, 0.15)),
    # roads
    SubIssue("culvert_damage", "roads", "culvert on the link road", "संपर्क मार्ग का पुलिया", (0.05, 0.20, 0.35, 0.40)),
    SubIssue("road_potholes", "roads", "village road", "गाँव की सड़क", (0.15, 0.40, 0.35, 0.10)),
    SubIssue("bridge_damage", "roads", "bridge over the river", "नदी का पुल", (0.05, 0.15, 0.35, 0.45)),
    SubIssue("bus_service", "roads", "bus service to the block town", "ब्लॉक तक बस सेवा", (0.30, 0.40, 0.25, 0.05)),
    SubIssue("streetlight_road", "roads", "street lighting on the main road", "मुख्य सड़क पर स्ट्रीट लाइट", (0.20, 0.40, 0.30, 0.10)),
    SubIssue("roadside_drain", "roads", "roadside drainage", "सड़क किनारे नाली", (0.20, 0.40, 0.30, 0.10)),
    # electricity
    SubIssue("feeder_outage", "electricity", "rural feeder supply", "ग्रामीण फीडर", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("transformer_burnt", "electricity", "distribution transformer", "ट्रांसफार्मर", (0.05, 0.20, 0.40, 0.35)),
    SubIssue("meter_pending", "electricity", "new electricity meter", "नया बिजली मीटर", (0.30, 0.40, 0.25, 0.05)),
    SubIssue("low_voltage", "electricity", "voltage supply", "वोल्टेज", (0.20, 0.40, 0.30, 0.10)),
    SubIssue("bill_error", "electricity", "electricity bill", "बिजली बिल", (0.35, 0.40, 0.20, 0.05)),
    SubIssue("solar_streetlight", "electricity", "solar street light", "सोलर स्ट्रीट लाइट", (0.25, 0.40, 0.30, 0.05)),
    # health
    SubIssue("phc_no_doctor", "health", "primary health centre", "प्राथमिक स्वास्थ्य केंद्र", (0.05, 0.15, 0.35, 0.45)),
    SubIssue("medicine_stock", "health", "medicine stock at the health centre", "स्वास्थ्य केंद्र में दवा", (0.05, 0.25, 0.40, 0.30)),
    SubIssue("anganwadi_supply", "health", "anganwadi nutrition supply", "आंगनबाड़ी पोषण", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("ambulance_delay", "health", "ambulance service", "एम्बुलेंस सेवा", (0.05, 0.15, 0.35, 0.45)),
    SubIssue("anm_vacancy", "health", "ANM posting at the sub-centre", "उपकेंद्र पर एएनएम", (0.05, 0.25, 0.40, 0.30)),
    SubIssue("cold_chain", "health", "vaccine cold chain", "वैक्सीन कोल्ड चेन", (0.05, 0.20, 0.40, 0.35)),
    SubIssue("health_camp", "health", "monthly health camp", "मासिक स्वास्थ्य शिविर", (0.25, 0.40, 0.25, 0.10)),
    # education
    SubIssue("school_toilet", "education", "girls' toilet in the school", "स्कूल का शौचालय", (0.10, 0.25, 0.40, 0.25)),
    SubIssue("teacher_vacancy", "education", "teacher posting", "शिक्षक की नियुक्ति", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("school_roof", "education", "school building roof", "स्कूल भवन की छत", (0.15, 0.30, 0.40, 0.15)),
    SubIssue("midday_meal", "education", "mid-day meal", "मध्याह्न भोजन", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("school_electricity", "education", "electricity connection in the school", "स्कूल में बिजली", (0.30, 0.40, 0.25, 0.05)),
    SubIssue("textbooks_delay", "education", "free textbook distribution", "निःशुल्क पुस्तकें", (0.30, 0.40, 0.25, 0.05)),
    SubIssue("boundary_wall", "education", "school boundary wall", "स्कूल की चारदीवारी", (0.25, 0.40, 0.30, 0.05)),
    # food & PDS
    SubIssue("ration_shortweight", "food", "ration shop weighing", "राशन दुकान का वजन", (0.05, 0.25, 0.45, 0.25)),
    SubIssue("dealer_closed", "food", "ration shop opening hours", "राशन दुकान", (0.20, 0.40, 0.30, 0.10)),
    SubIssue("aadhaar_seeding", "food", "Aadhaar seeding for the ration card", "राशन कार्ड में आधार", (0.25, 0.40, 0.25, 0.10)),
    SubIssue("new_ration_card", "food", "new ration card application", "नया राशन कार्ड", (0.30, 0.40, 0.25, 0.05)),
    SubIssue("grain_quality", "food", "quality of grain supplied", "राशन का अनाज", (0.15, 0.35, 0.35, 0.15)),
    SubIssue("pds_portability", "food", "ration portability between districts", "राशन पोर्टेबिलिटी", (0.30, 0.40, 0.25, 0.05)),
    # welfare
    SubIssue("pension_delay", "welfare", "old-age pension", "वृद्धावस्था पेंशन", (0.05, 0.25, 0.45, 0.25)),
    SubIssue("widow_pension", "welfare", "widow pension", "विधवा पेंशन", (0.05, 0.25, 0.45, 0.25)),
    SubIssue("disability_certificate", "welfare", "disability certificate", "विकलांगता प्रमाण पत्र", (0.20, 0.40, 0.30, 0.10)),
    SubIssue("scholarship_delay", "welfare", "post-matric scholarship", "पोस्ट-मैट्रिक छात्रवृत्ति", (0.15, 0.35, 0.40, 0.10)),
    SubIssue("mgnrega_wages", "welfare", "MGNREGA wage payment", "मनरेगा मजदूरी", (0.05, 0.25, 0.45, 0.25)),
    SubIssue("ration_card_cancel", "welfare", "ration card cancellation notice", "राशन कार्ड रद्द", (0.15, 0.35, 0.35, 0.15)),
    # land
    SubIssue("mutation_delay", "land", "land mutation file", "दाखिल-खारिज की फाइल", (0.15, 0.40, 0.35, 0.10)),
    SubIssue("land_record_error", "land", "land record entry", "भूमि रिकॉर्ड", (0.20, 0.40, 0.30, 0.10)),
    SubIssue("boundary_demarcation", "land", "boundary demarcation", "सीमांकन", (0.20, 0.45, 0.30, 0.05)),
    SubIssue("registry_appointment", "land", "registration appointment", "रजिस्ट्री की तारीख", (0.30, 0.40, 0.25, 0.05)),
    SubIssue("parcha_copy", "land", "parcha copy", "परचा की प्रति", (0.35, 0.40, 0.20, 0.05)),
    SubIssue("public_land_encroachment", "land", "public land encroachment", "सार्वजनिक भूमि पर अतिक्रमण", (0.20, 0.40, 0.30, 0.10)),
    # employment
    SubIssue("job_card", "employment", "job card under the employment scheme", "जॉब कार्ड", (0.30, 0.40, 0.25, 0.05)),
    SubIssue("wage_delay_contract", "employment", "contract labour payment", "अनुबंध मजदूरी भुगतान", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("skill_training", "employment", "skill training centre", "कौशल प्रशिक्षण केंद्र", (0.35, 0.40, 0.20, 0.05)),
    SubIssue("migration_support", "employment", "migrant worker support desk", "प्रवासी श्रमिक सहायता", (0.30, 0.40, 0.25, 0.05)),
    # agriculture
    SubIssue("canal_irrigation", "agriculture", "canal irrigation supply", "नहर सिंचाई", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("seed_supply", "agriculture", "certified seed supply", "प्रमाणित बीज", (0.20, 0.40, 0.30, 0.10)),
    SubIssue("crop_insurance", "agriculture", "crop insurance claim", "फसल बीमा", (0.10, 0.35, 0.40, 0.15)),
    SubIssue("fertiliser_shop", "agriculture", "fertiliser availability", "उर्वरक की उपलब्धता", (0.20, 0.40, 0.30, 0.10)),
    SubIssue("mandi_procurement", "agriculture", "mandi procurement centre", "मंडी खरीद केंद्र", (0.15, 0.35, 0.40, 0.10)),
    SubIssue("borewell_irrigation", "agriculture", "borewell irrigation", "बोरवेल सिंचाई", (0.15, 0.35, 0.35, 0.15)),
    # safety & environment
    SubIssue("police_response", "safety", "police response time", "पुलिस की प्रतिक्रिया", (0.05, 0.20, 0.40, 0.35)),
    SubIssue("illegal_liquor", "safety", "illegal liquor sale", "अवैध शराब बिक्री", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("womens_safety", "safety", "women's safety at the bus stand", "बस स्टैंड पर महिला सुरक्षा", (0.05, 0.20, 0.40, 0.35)),
    SubIssue("cyber_fraud", "safety", "cyber fraud complaint", "साइबर धोखाधड़ी", (0.10, 0.30, 0.40, 0.20)),
    SubIssue("industrial_dust", "safety", "industrial dust pollution", "औद्योगिक धूल प्रदूषण", (0.15, 0.35, 0.35, 0.15)),
    SubIssue("flood_drainage", "safety", "flood water drainage", "बाढ़ का पानी निकासी", (0.05, 0.20, 0.40, 0.35)),
)
# fmt: on

EN_TEMPLATES: tuple[str, ...] = (
    "The {issue} in {district} has not been working for {duration}. Families are managing without it.",
    "The {issue} in our area broke {duration} ago and has not been repaired.",
    "There is no working {issue} here. The problem started {duration} ago and nobody has inspected it.",
    "We want to report that the {issue} is not functioning. It has been like this for {duration}.",
    "The {issue} needs urgent repair. It has been broken for {duration} and children are affected the most.",
    "Every family in the ward is facing the same problem with the {issue}. It has been {duration} since we complained.",
    "For {duration} the {issue} has been in a bad condition. We are forced to pay for alternatives.",
    "The {issue}: repeated complaints, no action for {duration}.",
    "Our village has reported the {issue} several times. Nothing has changed in {duration}.",
    "The {issue} is unusable and the responsible office does not respond. This is {duration} old.",
    "I am writing about the {issue}. It has been {duration} since it last worked.",
    "The situation with the {issue} is getting worse. This is the third time we are reporting it in {duration}.",
)

HI_TEMPLATES: tuple[str, ...] = (
    "{issue} {duration} से ठीक नहीं है। गाँव के लोग परेशान हैं।",
    "{district} में {issue} की स्थिति खराब है, {duration} से कोई कार्रवाई नहीं हुई।",
    "हमारे मोहल्ले में {issue} {duration} से बंद पड़ा है। बच्चों को सबसे ज्यादा दिक्कत हो रही है।",
    "{issue} को ठीक कराने के लिए {duration} से शिकायत कर रहे हैं, सुनवाई नहीं हुई।",
    "{duration} से {issue} की समस्या बनी हुई है, विभाग को सूचित करने पर भी कोई बदलाव नहीं।",
    "कृपया {issue} पर ध्यान दें। {duration} से लोगों को भारी परेशानी का सामना करना पड़ रहा है।",
    "{issue} {duration} से खराब है और मरम्मत नहीं हुई।",
    "यह तीसरी बार लिख रहे हैं कि {issue} {duration} से ठीक नहीं है।",
    "गाँव में {issue} का कोई इंतजाम नहीं है। {duration} से यही हाल है।",
    "{issue} की शिकायत {duration} से दर्ज है, फिर भी कोई अधिकारी नहीं आया।",
    "{issue} से जुड़ी समस्या {duration} पुरानी है, अब हद से ज्यादा हो गई है।",
    "{district} के इस इलाके में {issue} {duration} से बंद है, लोग दूसरे गाँव जाते हैं।",
)

HINGLISH_TEMPLATES: tuple[str, ...] = (
    "{issue} {duration} se kharab hai, koi sunwai nahi ho rahi.",
    "hamare yahan {issue} {duration} se band hai, log pareshan hain",
    "{issue} theek karwane ke liye {duration} se complaint kar rahe hain",
    "{district} mein {issue} ka problem {duration} se hai, department kuch nahi kar raha",
    "sir please {issue} par dhyan dijiye, {duration} se dikkat ho rahi hai",
    "{issue} {duration} se repair nahi hua, bachchon ko takleef ho rahi hai",
    "{issue} ki problem {duration} purani hai aur ab bahut zyada badh gayi hai",
    "baar baar complaint karne ke baad bhi {issue} {duration} se same condition mein hai",
)

EN_DURATIONS: tuple[str, ...] = (
    "two months",
    "three months",
    "four weeks",
    "six months",
    "eight months",
    "a year",
    "since the last monsoon",
)

HI_DURATIONS: tuple[str, ...] = (
    "दो महीने",
    "तीन महीने",
    "चार हफ्ते",
    "छह महीने",
    "आठ महीने",
    "एक साल",
    "पिछले मानसून",
)

HINGLISH_DURATIONS: tuple[str, ...] = (
    "do mahine",
    "teen mahine",
    "chaar hafte",
    "chhah mahine",
    "aath mahine",
    "ek saal",
)

# A complaint sentence alone says almost nothing about which service failed: the
# {issue} slot is two or three words inside twelve words of shared boilerplate.
# Real complaints add the domain detail ("the pipeline pressure has dropped"),
# so each domain carries its own detail clauses. Without them the strongest
# lexical signal in the corpus is the template, not the topic, and any topic
# model is measured against a corpus that cannot express topics.
DOMAIN_DETAILS: dict[str, dict[str, tuple[str, ...]]] = {
    "water": {
        "en": (
            " The supply line pressure has dropped and the tank stays dry.",
            " The water smells and leaves sediment at the bottom of the bucket.",
            " The motor at the pump house has burnt and no repair estimate is given.",
        ),
        "hi": (
            " सप्लाई लाइन का प्रेशर गिर गया है और टंकी सूखी रहती है।",
            " पानी से बदबू आती है और बाल्टी में गाद बैठ जाती है।",
            " पंप हाउस की मोटर जल गई है और मरम्मत का अनुमान नहीं दिया गया।",
        ),
        "hinglish": (
            " supply line ka pressure gir gaya hai aur tanki sookhi rehti hai",
            " paani se badbu aati hai aur balti mein gaad baith jati hai",
            " pump house ki motor jal gayi hai aur repair ka estimate nahi diya",
        ),
    },
    "sanitation": {
        "en": (
            " The drain is choked and sewage is standing on the lane.",
            " The garbage van has not reached the ward and waste is piling up.",
            " The community toilet has no water and the septic tank is full.",
        ),
        "hi": (
            " नाली चोक हो गई है और गली में गंदा पानी जमा है।",
            " कचरा गाड़ी वार्ड तक नहीं आई और कूड़ा जमा हो रहा है।",
            " सामुदायिक शौचालय में पानी नहीं है और सेप्टिक टैंक भर गया है।",
        ),
        "hinglish": (
            " naali choke hai aur gali mein ganda paani jama hai",
            " kachra gaadi ward tak nahi aayi aur kooda jama ho raha hai",
            " community toilet mein paani nahi hai aur septic tank bhar gaya hai",
        ),
    },
    "roads": {
        "en": (
            " The bitumen has washed away and the shoulder has collapsed.",
            " The culvert is blocked and water floods the link road.",
            " Bus services to the block town have stopped since the road caved in.",
        ),
        "hi": (
            " डामर बह गया है और सड़क का किनारा धँस गया है।",
            " पुलिया बंद है और पानी संपर्क मार्ग पर भर जाता है।",
            " सड़क धँसने के बाद से ब्लॉक तक बस सेवा बंद है।",
        ),
        "hinglish": (
            " bitumen beh gaya hai aur sadak ka kinara dhans gaya hai",
            " puliya block hai aur paani link road par bhar jata hai",
            " sadak dhansne ke baad block tak bus service band hai",
        ),
    },
    "electricity": {
        "en": (
            " The feeder trips every evening and the transformer oil has leaked.",
            " The voltage is so low that the water pump cannot start.",
            " The meter application is pending at the subdivision office.",
        ),
        "hi": (
            " फीडर हर शाम ट्रिप करता है और ट्रांसफार्मर का तेल लीक है।",
            " वोल्टेज इतना कम है कि पानी का पंप नहीं चलता।",
            " मीटर का आवेदन उपमंडल कार्यालय में लंबित है।",
        ),
        "hinglish": (
            " feeder har shaam trip karta hai aur transformer ka tel leak hai",
            " voltage itna kam hai ki paani ka pump start nahi hota",
            " meter ka application subdivision office mein pending hai",
        ),
    },
    "health": {
        "en": (
            " The health centre has no doctor on duty and patients are sent to Sadar.",
            " The medicine rack is empty and the cold chain box is not working.",
            " The ambulance takes over an hour to reach the village.",
        ),
        "hi": (
            " स्वास्थ्य केंद्र पर ड्यूटी में डॉक्टर नहीं है और मरीज सदर भेजे जाते हैं।",
            " दवा का रैक खाली है और कोल्ड चेन बॉक्स काम नहीं कर रहा।",
            " एम्बुलेंस गाँव पहुँचने में एक घंटे से ज्यादा लेती है।",
        ),
        "hinglish": (
            " health centre par duty mein doctor nahi hai aur patient sadar bheje jate hain",
            " dawa ka rack khaali hai aur cold chain box kaam nahi kar raha",
            " ambulance gaon pahunchne mein ek ghante se zyada leti hai",
        ),
    },
    "education": {
        "en": (
            " The school has no teacher for the science section and classes sit idle.",
            " The mid-day meal grain has not reached the kitchen.",
            " The boundary wall has collapsed and the girls' toilet is locked.",
        ),
        "hi": (
            " स्कूल में विज्ञान वर्ग के लिए शिक्षक नहीं है और कक्षाएँ खाली बैठी हैं।",
            " मध्याह्न भोजन का अनाज रसोई तक नहीं पहुँचा।",
            " चारदीवारी गिर गई है और छात्राओं का शौचालय बंद है।",
        ),
        "hinglish": (
            " school mein science section ke liye teacher nahi hai aur classes khaali baithi hain",
            " mid day meal ka anaj rasoi tak nahi pahuncha",
            " boundary wall gir gayi hai aur girls toilet locked hai",
        ),
    },
    "food": {
        "en": (
            " The ration dealer gives short weight and closes the shop early.",
            " The grain supplied is damp and full of stones.",
            " Aadhaar seeding for the ration card has been pending for months.",
        ),
        "hi": (
            " राशन डीलर कम तौलता है और दुकान जल्दी बंद कर देता है।",
            " दिया गया अनाज नम है और उसमें कंकड़ हैं।",
            " राशन कार्ड में आधार सीडिंग महीनों से लंबित है।",
        ),
        "hinglish": (
            " ration dealer kam taulta hai aur dukaan jaldi band kar deta hai",
            " diya gaya anaj nam hai aur usme kankar hain",
            " ration card mein aadhaar seeding mahino se pending hai",
        ),
    },
    "welfare": {
        "en": (
            " The pension has not reached the bank account for three cycles.",
            " The widow pension application is stuck for want of a certificate.",
            " MGNREGA wages are shown as paid but the account has no credit.",
        ),
        "hi": (
            " तीन किस्तों से पेंशन बैंक खाते में नहीं आई।",
            " विधवा पेंशन का आवेदन प्रमाण पत्र के अभाव में अटका है।",
            " मनरेगा मजदूरी भुगतान दिख रही है पर खाते में पैसा नहीं आया।",
        ),
        "hinglish": (
            " teen kiston se pension bank account mein nahi aayi",
            " widow pension ka application certificate ke abhav mein atka hai",
            " MGNREGA mazduri payment dikh rahi hai par account mein paisa nahi aaya",
        ),
    },
    "land": {
        "en": (
            " The mutation file is pending at the circle office and no registry date is given.",
            " The land record still shows the old owner and the parcha copy was refused.",
            " A boundary pillar has been removed and the demarcation is disputed.",
        ),
        "hi": (
            " दाखिल-खारिज की फाइल अंचल कार्यालय में लंबित है और रजिस्ट्री की तारीख नहीं दी गई।",
            " भूमि रिकॉर्ड में पुराना मालिक दर्ज है और परचा की प्रति नहीं दी गई।",
            " सीमा का खंभा हटा दिया गया है और सीमांकन पर विवाद है।",
        ),
        "hinglish": (
            " dakhal kharij ki file anchal office mein pending hai aur registry ki date nahi di gayi",
            " land record mein purana malik darj hai aur parcha ki copy nahi di gayi",
            " boundary ka khamba hata diya gaya hai aur demarcation par vivad hai",
        ),
    },
    "employment": {
        "en": (
            " The job card has no entry for the work done last season.",
            " Contract labour wages are held up with the contractor.",
            " The skill training centre has no trainer and the batch is delayed.",
        ),
        "hi": (
            " जॉब कार्ड में पिछले सीजन के काम की प्रविष्टि नहीं है।",
            " ठेकेदार के पास अनुबंध मजदूरी रुकी हुई है।",
            " कौशल प्रशिक्षण केंद्र में प्रशिक्षक नहीं है और बैच विलंबित है।",
        ),
        "hinglish": (
            " job card mein pichhle season ke kaam ki entry nahi hai",
            " thekedar ke paas contract mazduri ruki hui hai",
            " skill training centre mein trainer nahi hai aur batch delayed hai",
        ),
    },
    "agriculture": {
        "en": (
            " The canal has not received water this season and the borewell is dry.",
            " Certified seed was not issued and the crop insurance claim is pending.",
            " The fertiliser shop has no stock and the mandi centre is closed.",
        ),
        "hi": (
            " इस सीजन नहर में पानी नहीं आया और बोरवेल सूख गया है।",
            " प्रमाणित बीज नहीं मिला और फसल बीमा का दावा लंबित है।",
            " उर्वरक की दुकान में स्टॉक नहीं है और मंडी केंद्र बंद है।",
        ),
        "hinglish": (
            " is season nahar mein paani nahi aaya aur borewell sookh gaya hai",
            " certified seed nahi mila aur crop insurance ka claim pending hai",
            " fertiliser ki dukaan mein stock nahi hai aur mandi centre band hai",
        ),
    },
    "safety": {
        "en": (
            " The police beat is not patrolled at night and the response is slow.",
            " Illegal liquor is sold openly near the bus stand.",
            " Industrial dust covers the houses and the drain water has turned black.",
        ),
        "hi": (
            " रात में पुलिस गश्त नहीं होती और प्रतिक्रिया धीमी है।",
            " बस स्टैंड के पास खुलेआम अवैध शराब बिक रही है।",
            " औद्योगिक धूल घरों पर जमा है और नाली का पानी काला हो गया है।",
        ),
        "hinglish": (
            " raat mein police gashth nahi hoti aur response slow hai",
            " bus stand ke paas khule aam illegal sharab bik rahi hai",
            " industrial dust gharo par jama hai aur naali ka paani kaala ho gaya",
        ),
    },
}

# Share of complaints that carry a domain detail sentence.
DETAIL_PROBABILITY = 0.75

# Near-duplicate rewording. A near-duplicate must be the *same* complaint said
# differently: swapping the template produces a different complaint that only
# shares the issue phrase, which no duplicator could honestly call a duplicate.
PARAPHRASE_SWAPS: dict[str, tuple[tuple[str, str], ...]] = {
    "en": (
        ("has not been working", "has stopped working"),
        ("has not been repaired", "is still not repaired"),
        ("nobody has inspected", "no one has inspected"),
        ("urgent repair", "immediate repair"),
        ("Families are managing without it", "Families are coping without it"),
        ("We want to report that", "We wish to report that"),
        ("repeated complaints, no action", "many complaints, still no action"),
        ("Our village has reported", "Our village has complained about"),
        ("We are forced to pay", "We have to pay"),
        ("This is the third time", "For the third time"),
        ("The situation with", "The condition of"),
        ("the responsible office does not respond", "the department does not respond"),
    ),
    "hi": (
        ("ठीक नहीं है", "सही नहीं है"),
        ("कोई कार्रवाई नहीं हुई", "कोई सुनवाई नहीं हुई"),
        ("कोई बदलाव नहीं", "कोई सुधार नहीं"),
        ("परेशान हैं", "दिक्कत में हैं"),
        ("कोई इंतजाम नहीं है", "कोई व्यवस्था नहीं है"),
        ("सुनवाई नहीं हुई", "कोई जवाब नहीं मिला"),
        ("मरम्मत नहीं हुई", "ठीक नहीं हुआ"),
        ("शिकायत कर रहे हैं", "अर्जी दे रहे हैं"),
    ),
    "hinglish": (
        ("kharab hai", "theek nahi hai"),
        ("koi sunwai nahi ho rahi", "koi jawab nahi aa raha"),
        ("log pareshan hain", "log dikkat mein hain"),
        ("band hai", "chalu nahi hai"),
        ("complaint kar rahe hain", "shikayat kar rahe hain"),
        ("department kuch nahi kar raha", "department dhyan nahi de raha"),
        ("repair nahi hua", "theek nahi hua"),
        ("problem", "dikkat"),
    ),
}

# Used only when a near-duplicate render collides with its source text. Real
# complainants do write "reporting again", so this stays plausible.
_REPEAT_PREFIX = {
    "en": "Reporting again: ",
    "hi": "फिर से शिकायत: ",
    "hinglish": "phir se complaint: ",
}

# Last-resort detail clauses when both the template and duration pools are
# exhausted for one (issue, district, language) cell. Complainants do add such
# lines, so the fallback stays in register rather than looking machine-made.
_EXTRA_CLAUSES = {
    "en": (
        " The ward member has been informed.",
        " This was raised at the panchayat meeting.",
        " We have submitted a written application.",
        " The damage is visible from the main road.",
    ),
    "hi": (
        " वार्ड सदस्य को सूचित किया गया है।",
        " पंचायत बैठक में यह बात रखी गई।",
        " हमने लिखित आवेदन दिया है।",
        " नुकसान मुख्य सड़क से दिखाई देता है।",
    ),
    "hinglish": (
        " ward member ko bata diya hai",
        " panchayat meeting mein baat rakhi hai",
        " likhit application de di hai",
        " nuksan main road se dikhta hai",
    ),
}

START_DATE = date(2025, 5, 1)
END_DATE = date(2026, 10, 31)

EXACT_DUPLICATE_RATE = 0.02
NEAR_DUPLICATE_RATE = 0.08

CANONICAL_OUTPUT_COLUMNS = list(COMPLAINT_COLUMNS)
TRUTH_OUTPUT_COLUMNS = [
    "complaint_id",
    "domain",
    "sub_issue",
    "true_severity",
    "duplicate_group_id",
    "is_duplicate",
    "duplicate_kind",
    "duplicate_of",
    "language",
    "district",
]


def _months_between(start: date, end: date) -> list[date]:
    months: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(date(year, month, 1))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return months


_MONTHS = _months_between(START_DATE, END_DATE)


def _pick_language(rng: random.Random) -> str:
    languages = [language for language, _ in LANGUAGE_MIX]
    weights = [weight for _, weight in LANGUAGE_MIX]
    return rng.choices(languages, weights=weights, k=1)[0]


def _render_text(
    rng: random.Random,
    sub_issue: SubIssue,
    district: str,
    language: str,
    avoid: str | None = None,
    used: set[str] | None = None,
    attempts: int = 60,
) -> str:
    """Render complaint text, excluding one string and any already-used string.

    Independent complaints must never share byte-identical text. A duplicate
    detector that flags two identical complaints is *correct*, so the generator
    must not manufacture identical pairs that it then labels as distinct.
    """
    candidate = ""
    for _ in range(attempts):
        if language == "hi":
            template = rng.choice(HI_TEMPLATES)
            issue, duration = sub_issue.hi, rng.choice(HI_DURATIONS)
        elif language == "hinglish":
            template = rng.choice(HINGLISH_TEMPLATES)
            issue, duration = sub_issue.en, rng.choice(HINGLISH_DURATIONS)
        else:
            template = rng.choice(EN_TEMPLATES)
            issue, duration = sub_issue.en, rng.choice(EN_DURATIONS)

        rendered = template.format(issue=issue, district=district, duration=duration)
        candidate = _add_noise(
            rng, _add_detail(rng, rendered, sub_issue, language), language
        )
        if candidate == avoid:
            continue
        if used is not None and candidate in used:
            continue
        return candidate

    if avoid is not None:
        candidate = _REPEAT_PREFIX[language] + candidate
        if used is None or candidate not in used:
            return candidate

    for clause in _EXTRA_CLAUSES[language]:
        expanded = candidate.rstrip() + clause
        if used is None or expanded not in used:
            return expanded

    raise RuntimeError(
        f"Could not render unique text for {sub_issue.slug}/{district}/{language}; "
        "widen the template or clause pool."
    )


def _add_detail(
    rng: random.Random, text: str, sub_issue: SubIssue, language: str
) -> str:
    """Attach a domain detail clause so the text describes the actual problem."""
    if rng.random() >= DETAIL_PROBABILITY:
        return text
    detail = rng.choice(DOMAIN_DETAILS[sub_issue.domain][language])
    # Leading sentence or trailing justification: both orders occur in real
    # complaints, and alternating them stops one template from becoming a
    # uniquely identifying fingerprint.
    if rng.random() < 0.25:
        return detail.strip() + " " + text
    return text.rstrip() + detail


def _paraphrase(
    rng: random.Random,
    text: str,
    language: str,
    *,
    used: set[str] | None = None,
) -> str:
    """Reword a complaint while keeping its content, for injected near-duplicates."""
    swaps = [pair for pair in PARAPHRASE_SWAPS[language] if pair[0] in text]
    rng.shuffle(swaps)
    candidate = text
    for old, new in swaps[:2]:
        candidate = candidate.replace(old, new, 1)
    if candidate == text:
        candidate = _REPEAT_PREFIX[language] + text

    if used is None or candidate not in used:
        return candidate
    for clause in _EXTRA_CLAUSES[language]:
        expanded = candidate.rstrip() + clause
        if used is None or expanded not in used:
            return expanded
    raise RuntimeError(
        f"Could not paraphrase {language} complaint text without colliding with an "
        "existing row; widen PARAPHRASE_SWAPS or the clause pool."
    )


def _add_noise(rng: random.Random, text: str, language: str) -> str:
    """Light, realistic degradation: dropped punctuation, informal tail."""
    if language == "hinglish":
        if text.endswith(".") and rng.random() < 0.6:
            text = text[:-1]
    elif rng.random() < 0.12:
        text = text.rstrip(".।")
    if rng.random() < 0.08:
        tail = {
            "en": " Please look into it.",
            "hi": " कृपया ध्यान दें।",
            "hinglish": " please dekhiye",
        }[language]
        text = text.rstrip() + tail
    return text.strip()


def _pick_date(rng: random.Random, domain: str) -> date:
    weights = SEASONALITY[domain]
    month = rng.choices(_MONTHS, weights=[weights[m.month - 1] for m in _MONTHS], k=1)[0]
    day = rng.randrange(1, 28)
    return month + timedelta(days=day - 1)


def _pick_severity(rng: random.Random, sub_issue: SubIssue) -> str:
    return rng.choices(
        ["low", "medium", "high", "critical"],
        weights=list(sub_issue.severity_weights),
        k=1,
    )[0]


def _pick_population(rng: random.Random, district: str, severity: str) -> int:
    base = rng.lognormvariate(mu=5.4, sigma=0.9)
    scale = DISTRICT_WEIGHTS[district] / 2400
    multiplier = {"low": 0.55, "medium": 1.0, "high": 1.6, "critical": 2.2}[severity]
    value = max(5, min(250_000, base * scale * multiplier))
    return int(round(value / 10) * 10)


def _build_row(
    rng: random.Random,
    complaint_id: str,
    sub_issue: SubIssue,
    district: str,
    language: str,
    *,
    text: str | None = None,
    severity: str | None = None,
    population: int | None = None,
    reported_on: date | None = None,
    used: set[str] | None = None,
) -> dict[str, object]:
    severity = severity or _pick_severity(rng, sub_issue)
    return {
        "complaint_id": complaint_id,
        "complaint_text": text
        or _render_text(rng, sub_issue, district, language, used=used),
        "district": district,
        "block": pd.NA,
        "complaint_date": (reported_on or _pick_date(rng, sub_issue.domain)).isoformat(),
        "language": language,
        "severity": severity,
        "affected_population": population
        if population is not None
        else _pick_population(rng, district, severity),
        "source_type": "synthetic",
        "verification_status": "synthetic_not_verified",
        # internal, stripped before writing the canonical file
        "_domain": DOMAINS[sub_issue.domain],
        "_sub_issue": sub_issue.slug,
    }


def generate_corpus(
    n_records: int = 15_000,
    seed: int = 42,
    id_prefix: str = "SYN",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (canonical complaints, ground truth) for ``n_records`` rows."""
    if n_records <= 0:
        raise ValueError("n_records must be positive")

    rng = random.Random(seed)
    districts = list(DISTRICT_WEIGHTS)
    district_weights = [DISTRICT_WEIGHTS[name] for name in districts]

    # ``n_records`` is the size of the delivered corpus, duplicates included.
    n_exact = int(round(n_records * EXACT_DUPLICATE_RATE))
    n_near = int(round(n_records * NEAR_DUPLICATE_RATE))
    n_base = n_records - n_exact - n_near
    if n_base < 10:
        raise ValueError("n_records is too small to carry the declared duplicate rate")

    base: list[dict[str, object]] = []
    used_texts: set[str] = set()
    for index in range(n_base):
        district = rng.choices(districts, weights=district_weights, k=1)[0]
        sub_issue = rng.choice(SUB_ISSUES)
        language = _pick_language(rng)
        row = _build_row(
            rng,
            f"{id_prefix}-{index + 1:06d}",
            sub_issue,
            district,
            language,
            used=used_texts,
        )
        base.append(row)
        used_texts.add(str(row["complaint_text"]))

    rows = list(base)
    next_id = n_base + 1
    duplicate_links: dict[str, str] = {}
    duplicate_kind: dict[str, str] = {}
    sources = rng.sample(base, n_exact + n_near)

    for source in sources[:n_exact]:
        new_id = f"{id_prefix}-{next_id:06d}"
        next_id += 1
        rows.append({**source, "complaint_id": new_id})
        duplicate_links[new_id] = str(source["complaint_id"])
        duplicate_kind[new_id] = "exact"

    for source in sources[n_exact:]:
        new_id = f"{id_prefix}-{next_id:06d}"
        next_id += 1
        sub_issue = next(item for item in SUB_ISSUES if item.slug == source["_sub_issue"])
        district = str(source["district"])
        language = str(source["language"])
        text = _paraphrase(
            rng,
            str(source["complaint_text"]),
            language,
            used=used_texts,
        )
        used_texts.add(text)
        population = int(source["affected_population"])  # type: ignore[arg-type]
        jittered = max(5, int(round(population * rng.uniform(0.85, 1.15) / 10) * 10))
        reported_on = date.fromisoformat(str(source["complaint_date"])) + timedelta(
            days=rng.randrange(0, 21)
        )
        rows.append(
            _build_row(
                rng,
                new_id,
                sub_issue,
                district,
                language,
                text=text,
                severity=str(source["severity"]),
                population=jittered,
                reported_on=min(reported_on, END_DATE),
            )
        )
        duplicate_links[new_id] = str(source["complaint_id"])
        duplicate_kind[new_id] = "near"

    rng.shuffle(rows)

    canonical = pd.DataFrame(rows)
    # Group id is the first report id in the duplicate family, so a group of
    # four near-identical complaints collapses to one label.
    group_for: dict[str, str] = {}
    for row in rows:
        complaint_id = str(row["complaint_id"])
        if complaint_id in duplicate_links:
            group_for[complaint_id] = duplicate_links[complaint_id]
        else:
            group_for[complaint_id] = complaint_id

    canonical["duplicate_group_id"] = canonical["complaint_id"].map(group_for)
    # Only rows inside one duplicate family may share text. Anything else is a
    # generator collision that would poison duplicate-detection precision.
    shared = canonical.groupby("complaint_text")["duplicate_group_id"].nunique()
    if (shared > 1).any():
        offending = int(shared[shared > 1].shape[0])
        raise RuntimeError(
            f"{offending} texts are shared across duplicate groups; "
            "independent complaints must not be textually identical"
        )
    canonical["is_duplicate"] = canonical["complaint_id"].isin(duplicate_links).astype(int)
    canonical["duplicate_kind"] = (
        canonical["complaint_id"].map(duplicate_kind).fillna("")
    )
    canonical["duplicate_of"] = canonical["complaint_id"].map(duplicate_links)

    truth = canonical[
        [
            "complaint_id",
            "_domain",
            "_sub_issue",
            "severity",
            "duplicate_group_id",
            "is_duplicate",
            "duplicate_kind",
            "duplicate_of",
            "language",
            "district",
        ]
    ].rename(columns={"_domain": "domain", "_sub_issue": "sub_issue", "severity": "true_severity"})

    complaints = prepare_complaints(canonical.loc[:, CANONICAL_OUTPUT_COLUMNS])
    truth = truth.loc[:, TRUTH_OUTPUT_COLUMNS].reset_index(drop=True)

    if len(complaints) != len(rows) or len(complaints) != n_records:
        raise RuntimeError(
            f"Generator produced {len(complaints)} usable rows for a {n_records}-row request"
        )

    return complaints, truth


def write_corpus(
    output_dir,
    n_records: int = 15_000,
    n_eval: int = 2_000,
    seed: int = 42,
) -> dict[str, object]:
    """Generate the training and evaluation corpora and return a summary."""
    from pathlib import Path

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    complaints, truth = generate_corpus(n_records, seed=seed, id_prefix="SYN")
    eval_complaints, eval_truth = generate_corpus(n_eval, seed=seed + 1, id_prefix="EVAL")

    paths = {
        "complaints": directory / "complaints_15k.csv",
        "truth": directory / "ground_truth_15k.csv",
        "eval_complaints": directory / "complaints_2k_eval.csv",
        "eval_truth": directory / "ground_truth_2k_eval.csv",
    }

    complaints.to_csv(paths["complaints"], index=False, encoding="utf-8")
    truth.to_csv(paths["truth"], index=False, encoding="utf-8")
    eval_complaints.to_csv(paths["eval_complaints"], index=False, encoding="utf-8")
    eval_truth.to_csv(paths["eval_truth"], index=False, encoding="utf-8")

    return {
        "paths": {key: str(path) for key, path in paths.items()},
        "records": len(complaints),
        "eval_records": len(eval_complaints),
        "duplicates": int(truth["is_duplicate"].sum()),
        "duplicate_groups": int(truth["duplicate_group_id"].nunique()),
        "districts": int(complaints["district"].nunique()),
        "domains": int(truth["domain"].nunique()),
        "sub_issues": int(truth["sub_issue"].nunique()),
        "languages": complaints["language"].value_counts().to_dict(),
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
    }


def manifest_rows(summary: dict[str, object]) -> list[dict[str, object]]:
    """Provenance rows for data/source_manifest.csv."""
    generated_at = date.today().isoformat()
    base = {
        "publisher": "ChallengeMap synthetic generator",
        "source_url": f"src/data/synthetic_generator.py v{summary['generator_version']}",
        "license_or_consent_basis": "generated content, no third-party text",
        "acquired_at": generated_at,
        "transformations": "seeded template generation, canonical validation",
    }
    return [
        {
            **base,
            "dataset_file": "data/synthetic/complaints_15k.csv",
            "records_imported": summary["records"],
            "notes": (
                f"synthetic development corpus; seed {summary['seed']}; "
                f"{summary['duplicates']} injected duplicates; "
                "not evidence about real communities"
            ),
        },
        {
            **base,
            "dataset_file": "data/synthetic/complaints_2k_eval.csv",
            "records_imported": summary["eval_records"],
            "notes": f"held-out synthetic evaluation set; seed {summary['seed'] + 1}",
        },
        {
            **base,
            "dataset_file": "data/synthetic/ground_truth_15k.csv",
            "records_imported": summary["records"],
            "notes": "domain, sub-issue and duplicate-group labels for evaluation only",
        },
        {
            **base,
            "dataset_file": "data/synthetic/ground_truth_2k_eval.csv",
            "records_imported": summary["eval_records"],
            "notes": "held-out labels; never used for tuning",
        },
    ]


def iter_districts() -> Iterable[str]:
    return DISTRICT_WEIGHTS.keys()
