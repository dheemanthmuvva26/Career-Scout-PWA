"""
Generate human-readable short IDs for jobs.
Format: {COMPANY}-{ROLE}-{LOC}-{SEQ}
Example: HSBC-DA-40-01

  COMPANY  first 1-4 uppercase letters of the company's main word
  ROLE     2-4 letter abbreviation from the role map
  LOC      2-digit pincode prefix for the city (40=Mumbai, 56=Bangalore, …)
  SEQ      01-99, increments per (company, role, loc) triple
"""

import re
import sqlite3
from typing import Optional

# ── Location map ──────────────────────────────────────────────────────────────
# city keyword (lowercase) → 2-digit code
_LOC: dict[str, str] = {
    "mumbai": "40", "bombay": "40", "thane": "40", "navi mumbai": "40",
    "pune": "41", "pimpri": "41",
    "nagpur": "44",
    "aurangabad": "43",
    "delhi": "11", "new delhi": "11", "ncr": "11",
    "gurgaon": "12", "gurugram": "12", "faridabad": "12",
    "noida": "20", "greater noida": "20",
    "hyderabad": "50", "secunderabad": "50", "cyberabad": "50",
    "bangalore": "56", "bengaluru": "56",
    "mysore": "57", "mysuru": "57",
    "chennai": "60", "madras": "60",
    "coimbatore": "64",
    "kochi": "68", "cochin": "68", "ernakulam": "68",
    "kolkata": "70", "calcutta": "70",
    "ahmedabad": "38", "surat": "39",
    "lucknow": "22", "kanpur": "20",
    "jaipur": "30",
    "bhopal": "46", "indore": "45",
    "chandigarh": "16",
    "remote": "00", "pan-india": "00", "pan india": "00",
    "work from home": "00", "wfh": "00", "anywhere": "00",
}

# ── Role map ──────────────────────────────────────────────────────────────────
# ordered list of (patterns, code) — first match wins
_ROLES: list[tuple[list[str], str]] = [
    (["data analyst", "data analysis"],                          "DA"),
    (["business analyst", "business analysis"],                  "BA"),
    (["data engineer", "data engineering"],                      "DE"),
    (["data scientist", "data science"],                         "DS"),
    (["machine learning engineer", "ml engineer", "mle"],        "MLE"),
    (["ai engineer", "artificial intelligence engineer"],        "AIE"),
    (["applied scientist"],                                      "AS"),
    (["research scientist"],                                     "RS"),
    (["analytics engineer"],                                     "AE"),
    (["bi developer", "bi analyst", "business intelligence"],    "BI"),
    (["product analyst"],                                        "PA"),
    (["product manager"],                                        "PM"),
    (["software engineer", "software developer", " sde ", " swe "], "SE"),
    (["backend engineer", "backend developer", "back-end"],      "BE"),
    (["frontend engineer", "frontend developer", "front-end"],   "FE"),
    (["full stack", "fullstack"],                                "FS"),
    (["data architect"],                                         "DAR"),
    (["data platform"],                                          "DP"),
    (["quantitative analyst", "quant analyst"],                  "QA"),
    (["operations analyst", "operations research"],              "OA"),
    (["risk analyst"],                                           "RA"),
    (["financial analyst", "finance analyst"],                   "FA"),
    (["apprentice", "intern", "trainee", "graduate"],           "INT"),
    (["analyst"],                                                "AN"),  # generic fallback
]

_STRIP_COMPANY = re.compile(r"[^a-zA-Z0-9 ]")
_STOP_WORDS = {
    "india", "pvt", "ltd", "private", "limited", "technologies", "technology",
    "solutions", "services", "consulting", "group", "global", "systems",
    "software", "digital", "tech", "analytics", "and", "the", "of", "for",
    "llp", "inc", "corp", "co", "bank", "financial", "capital",
}
_SKIP_ROLE = {
    "senior", "junior", "lead", "principal", "associate", "intern", "head",
    "manager", "director", "specialist", "consultant", "officer", "executive",
    "staff", "sr", "jr", "ii", "iii", "iv", "i",
}

# ── Well-known company abbreviations ─────────────────────────────────────────
# Substring match (lowercase) → ticker/brand code
# Longer/more specific strings must come before shorter ones to avoid wrong matches.
_KNOWN_COMPANIES: list[tuple[str, str]] = [
    # Finance / Banking
    ("american express",        "AMEX"),
    ("jp morgan",               "JPM"),
    ("jpmorgan",                "JPM"),
    ("bank of america",         "BOFA"),
    ("wells fargo",             "WFC"),
    ("goldman sachs",           "GS"),
    ("morgan stanley",          "MS"),
    ("standard chartered",      "SCB"),
    ("deutsche bank",           "DB"),
    ("bny mellon",              "BNY"),
    ("state street",            "STT"),
    ("credit suisse",           "CS"),
    ("barclays",                "BARC"),
    ("citibank",                "CITI"),
    ("citigroup",               "CITI"),
    ("hsbc",                    "HSBC"),
    ("ubs",                     "UBS"),
    ("hdfc",                    "HDFC"),
    ("icici",                   "ICICI"),
    ("axis bank",               "AXIS"),
    ("kotak",                   "KOTA"),
    ("sbi",                     "SBI"),
    ("rbi",                     "RBI"),
    # Consulting / Big 4
    ("pricewaterhousecoopers",  "PWC"),
    ("pwc",                     "PWC"),
    ("ernst & young",           "EY"),
    ("ernst and young",         "EY"),
    ("kpmg",                    "KPMG"),
    ("deloitte",                "DELT"),
    ("mckinsey",                "MCK"),
    ("boston consulting",       "BCG"),
    ("bain",                    "BAIN"),
    ("accenture",               "ACCT"),
    ("capgemini",               "CAPG"),
    ("cognizant",               "COGN"),
    # IT / Indian IT
    ("tata consultancy",        "TCS"),
    (" tcs ",                   "TCS"),
    ("infosys",                 "INFY"),
    ("wipro",                   "WIPR"),
    ("hcl",                     "HCL"),
    ("tech mahindra",           "TECM"),
    ("mphasis",                 "MPH"),
    ("hexaware",                "HEXA"),
    ("ltimindtree",             "LTI"),
    ("l&t",                     "LT"),
    # Big Tech
    ("amazon",                  "AMZN"),
    ("google",                  "GOOG"),
    ("microsoft",               "MSFT"),
    ("apple",                   "AAPL"),
    ("meta",                    "META"),
    ("netflix",                 "NFLX"),
    ("salesforce",              "SFDC"),
    ("oracle",                  "ORCL"),
    ("ibm",                     "IBM"),
    ("sap",                     "SAP"),
    ("adobe",                   "ADBE"),
    ("snowflake",               "SNOW"),
    ("databricks",              "DBRX"),
    ("thoughtworks",            "TWTX"),
    ("nvidia",                  "NVDA"),
    # Indian startups / unicorns
    ("flipkart",                "FLIP"),
    ("meesho",                  "MEES"),
    ("swiggy",                  "SWIG"),
    ("zomato",                  "ZOMA"),
    ("paytm",                   "PAYT"),
    ("phonepe",                 "PHPE"),
    ("razorpay",                "RAZR"),
    ("zerodha",                 "ZERO"),
    ("cred",                    "CRED"),
    ("byju",                    "BYJU"),
    ("nykaa",                   "NYKA"),
    ("freshworks",              "FRES"),
    ("ola",                     "OLA"),
    ("mu sigma",                "MUSI"),
    ("fractal",                 "FRAC"),
    ("latentview",              "LATV"),
    # Analytics / Data firms
    ("tiger analytics",         "TIGR"),
    ("absolutdata",             "ABSD"),
    ("bridgei2i",               "BI2I"),
    ("ankura",                  "ANKR"),
]


def _company_code(name: str) -> str:
    """'American Express' → 'AMEX',  'HSBC Bank India' → 'HSBC', 'Deloitte Consulting' → 'DELT'"""
    lower = name.lower()
    for keyword, code in _KNOWN_COMPANIES:
        if keyword in lower:
            return code
    # Auto-generate from first significant word
    clean = _STRIP_COMPANY.sub(" ", name).strip()
    words = [
        w.upper() for w in clean.split()
        if w.lower() not in _STOP_WORDS and len(w) > 1
    ]
    if not words:
        words = [clean.upper().replace(" ", "")]
    return words[0][:4] or "XX"


def _role_code(title: str) -> str:
    """'Senior Data Analyst' → 'DA',  'ML Platform Engineer' → 'MLE'"""
    t = " " + title.lower() + " "
    for patterns, code in _ROLES:
        if any(p in t for p in patterns):
            return code
    # Fallback: first 3 uppercase chars of the first non-trivial word
    words = [w for w in title.lower().split() if w not in _SKIP_ROLE and len(w) > 2]
    if words:
        code = "".join(w[0].upper() for w in words[:3])
        return code if len(code) >= 2 else words[0][:3].upper()
    return "XX"


def _location_code(location: str) -> str:
    """'Mumbai, Maharashtra, India' → '40',  'Bengaluru' → '56'"""
    loc = location.lower()
    for keyword, code in _LOC.items():
        if keyword in loc:
            return code
    # Fallback for anything India-ish
    if "india" in loc or not loc.strip():
        return "IN"
    return "IN"


def _next_seq(prefix: str, conn: sqlite3.Connection) -> str:
    """Count existing short_ids with same prefix and return next 2-digit seq."""
    rows = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE short_id LIKE ?",
        (prefix + "-%",)
    ).fetchone()
    return f"{(rows[0] or 0) + 1:02d}"


def generate(job: dict, conn: sqlite3.Connection) -> str:
    """
    Generate a unique short ID for this job dict.
    conn: open sqlite3 connection used to determine the SEQ number.
    """
    company = _company_code(job.get("company") or "XX")
    role    = _role_code(job.get("title") or "XX")
    loc     = _location_code(job.get("location") or "")
    prefix  = f"{company}-{role}-{loc}"
    seq     = _next_seq(prefix, conn)
    return f"{prefix}-{seq}"
