import re
import unicodedata
from dataclasses import dataclass, field
from html import unescape
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Immigration97ScholarshipScout/1.0 "
    "(scholarship discovery; contact: contact@immigration97.com)"
)

TRUSTED_SOURCE_URLS = (
    "https://www.daad.de/en/studying-in-germany/scholarships/daad-scholarships/",
    "https://www.campusfrance.org/en/eiffel-scholarship-program-of-excellence",
    "https://www.studyin-uk.com/study-guide/scholarships-funding-international-students/",
    "https://www.chevening.org/scholarships/",
    "https://www.commonwealthscholarships.org/",
    "https://www.studyinaustralia.gov.au/en/plan-your-studies/scholarships",
    "https://www.educanada.ca/scholarships-bourses/index.aspx?lang=eng",
    "https://www.studyinjapan.go.jp/en/planning/scholarships/",
    "https://www.turkiyeburslari.gov.tr/",
    "https://www.studyinnl.org/finances",
    "https://commission.europa.eu/education/study-or-teach-abroad/scholarships-and-student-finance_en",
)

COUNTRY_LABELS = {
    "CA": "Canada",
    "FR": "France",
    "DE": "Germany",
    "GB": "United Kingdom",
    "AU": "Australia",
    "JP": "Japan",
    "TR": "Turkey",
    "NL": "Netherlands",
    "EU": "Europe",
    "US": "United States",
    "CN": "China",
}

SOURCE_COUNTRIES = {
    "daad.de": "Allemagne",
    "campusfrance.org": "France",
    "chevening.org": "Royaume-Uni",
    "commonwealthscholarships.org": "Royaume-Uni",
    "studyinaustralia.gov.au": "Australie",
    "educanada.ca": "Canada",
    "studyinjapan.go.jp": "Japon",
    "turkiyeburslari.gov.tr": "Turquie",
    "studyinnl.org": "Pays-Bas",
    "europa.eu": "Europe",
}

OFFICIAL_HOST_HINTS = (
    ".edu",
    ".ac.",
    ".gov",
    ".gc.ca",
    ".gouv.",
    ".go.jp",
    ".gov.au",
    ".gov.tr",
    "daad.de",
    "campusfrance.org",
    "chevening.org",
    "commonwealthscholarships.org",
    "studyinaustralia.gov.au",
    "educanada.ca",
    "studyinjapan.go.jp",
    "turkiyeburslari.gov.tr",
    "studyinnl.org",
    "europa.eu",
)

BLOCKED_CONTENT_HOSTS = {
    "scholarshiproar.com",
    "opportunitiescorners.com",
    "youthop.com",
    "scholarships365.info",
    "after-schoolafrica.com",
    "opportunitydesk.org",
}

BLOCKED_PATH_TERMS = (
    "/blog/",
    "/news/",
    "/article/",
    "/articles/",
    "/top-",
    "/list-of-",
    "/fully-funded-scholarships",
    "/why-study",
    "/find-a-course",
    "/application-timeline",
    "/host-a-fellowship",
)

POSITIVE_SIGNALS = {
    "apply": 10,
    "application": 10,
    "scholarship": 14,
    "bourse": 14,
    "financial aid": 12,
    "funding": 10,
    "fully funded": 22,
    "tuition fee": 12,
    "stipend": 14,
    "deadline": 16,
    "eligibility": 12,
    "international students": 16,
    "developing countries": 14,
    "africa": 10,
    "african": 10,
    "master": 8,
    "phd": 8,
    "doctorat": 8,
    "undergraduate": 8,
}

NEGATIVE_SIGNALS = {
    "expired": 28,
    "closed": 22,
    "list of": 12,
    "top scholarships": 18,
    "advertisement": 8,
    "sponsored post": 10,
}


@dataclass
class ScholarshipCandidate:
    title: str
    url: str
    organization: str = ""
    country: str = ""
    region: str = ""
    study_level: str = "unknown"
    funding_type: str = "unknown"
    amount: str = ""
    eligible_countries: str = ""
    deadline: str = ""
    requirements: str = ""
    description_text: str = ""
    confidence_score: int = 0
    verification_label: str = ""
    source: str = ""
    raw_data: dict = field(default_factory=dict)


def clean_text(value: str, limit: int = 1200) -> str:
    value = unescape(value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def fold_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in value if not unicodedata.combining(ch)).lower()


def fetch_html(url: str, timeout: int = 22) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en,fr;q=0.8"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


def normalize_result_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])
    if "url" in query and query["url"]:
        return unquote(query["url"][0])
    return parsed._replace(fragment="").geturl()


def is_direct_scholarship_url(url: str) -> bool:
    parsed = urlparse(url or "")
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    if not host:
        return False
    if host in BLOCKED_CONTENT_HOSTS or any(blocked in host for blocked in BLOCKED_CONTENT_HOSTS):
        return False
    if any(term in path for term in BLOCKED_PATH_TERMS):
        return False
    if path.rstrip("/") in ("", "/scholarships", "/funding", "/financial-aid"):
        return any(hint in host for hint in OFFICIAL_HOST_HINTS)
    if "chevening.org" in host:
        allowed = (
            path.rstrip("/") == "/scholarships",
            path.rstrip("/") == "/apply",
            "scholarship" in path and "who-can-apply" not in path,
            "/fellowships/find-a-programme" in path,
        )
        if any(allowed):
            return True
        return False
    scholarship_terms = (
        "scholarship",
        "scholarships",
        "bourse",
        "bourses",
        "funding",
        "financial-aid",
        "grants",
        "fellowship",
        "fellowships",
        "daad-scholarships",
        "chevening",
        "eiffel",
    )
    return any(term in path for term in scholarship_terms) or any(hint in host for hint in OFFICIAL_HOST_HINTS)


def build_search_urls(country: str = "", level: str = "", query: str = "") -> list[str]:
    country_label = COUNTRY_LABELS.get((country or "").upper().strip(), country or "international")
    terms = query or (
        f'{country_label} scholarship international students Africa application deadline '
        f'"fully funded" {level or "master phd undergraduate"} official'
    )
    encoded = quote_plus(terms)
    urls = [
        f"https://www.bing.com/search?q={encoded}",
        f"https://duckduckgo.com/html/?q={encoded}",
    ]
    urls.extend(TRUSTED_SOURCE_URLS)
    return list(dict.fromkeys(urls))


def extract_result_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    blocked_hosts = {"bing.com", "www.bing.com", "duckduckgo.com", "www.duckduckgo.com"}
    for anchor in soup.find_all("a", href=True):
        href = normalize_result_url(urljoin(base_url, anchor.get("href", "")))
        text = clean_text(anchor.get_text(" "), 220)
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.lower() in blocked_hosts:
            continue
        folded = fold_text(f"{text} {href}")
        if not text or len(text) < 8:
            continue
        if not any(term in folded for term in ("scholarship", "bourse", "funding", "grant", "fellowship", "apply")):
            continue
        if href not in links:
            links.append(href)
    useful = [url for url in links if is_direct_scholarship_url(url)]
    return (useful or links)[:35]


def extract_title(soup: BeautifulSoup) -> str:
    if soup.find("h1"):
        return clean_text(soup.find("h1").get_text(" "), 260)
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return clean_text(og_title["content"], 260)
    if soup.title:
        return clean_text(soup.title.get_text(" "), 260)
    return "Bourse d'études"


def infer_organization(soup: BeautifulSoup, title: str, url: str) -> str:
    for selector in [
        '[class*="organization"]',
        '[class*="provider"]',
        '[class*="institution"]',
        '[class*="university"]',
        ".organization",
        ".provider",
        ".institution",
    ]:
        node = soup.select_one(selector)
        if node:
            value = clean_text(node.get_text(" "), 220)
            if value:
                return value
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if " - " in title:
        parts = [part.strip() for part in title.split(" - ") if part.strip()]
        if len(parts) > 1 and len(parts[-1]) < 120:
            return parts[-1]
    host_labels = {
        "daad.de": "DAAD",
        "campusfrance.org": "Campus France",
        "chevening.org": "Chevening",
        "commonwealthscholarships.org": "Commonwealth Scholarship Commission",
        "studyinaustralia.gov.au": "Study Australia",
        "educanada.ca": "EduCanada",
        "studyinjapan.go.jp": "Study in Japan",
        "turkiyeburslari.gov.tr": "Türkiye Scholarships",
        "studyinnl.org": "Study in NL",
        "europa.eu": "Commission européenne",
    }
    for hint, label in host_labels.items():
        if hint in host:
            return label
    return host


def infer_country(text: str, url: str) -> str:
    host = urlparse(url).netloc.lower()
    for hint, country in SOURCE_COUNTRIES.items():
        if hint in host:
            return country
    folded = fold_text(text)
    for country in [
        "Canada",
        "France",
        "Allemagne",
        "Royaume-Uni",
        "Australie",
        "Japon",
        "Turquie",
        "Pays-Bas",
        "Etats-Unis",
        "Chine",
        "Europe",
    ]:
        if fold_text(country) in folded:
            return country
    return "International"


def infer_level(text: str) -> str:
    folded = fold_text(text)
    if any(term in folded for term in ("postdoctoral", "postdoctorat", "postdoc")):
        return "postdoc"
    if any(term in folded for term in ("phd", "doctoral", "doctorat")):
        return "doctorat"
    if any(term in folded for term in ("master", "msc", "maîtrise", "maitrise")):
        return "master"
    if any(term in folded for term in ("bachelor", "undergraduate", "licence")):
        return "licence"
    if any(term in folded for term in ("short course", "formation courte", "certificate")):
        return "short"
    if any(term in folded for term in ("all levels", "tous niveaux")):
        return "all"
    return "unknown"


def infer_funding(text: str) -> str:
    folded = fold_text(text)
    if any(term in folded for term in ("fully funded", "full scholarship", "bourse complete", "entierement finance")):
        return "full"
    if any(term in folded for term in ("tuition", "frais de scolarite", "fee waiver")):
        return "tuition"
    if any(term in folded for term in ("stipend", "living allowance", "allocation")):
        return "stipend"
    if any(term in folded for term in ("partial", "partielle")):
        return "partial"
    return "unknown"


def extract_deadline(text: str) -> str:
    patterns = [
        r"(?:deadline|closing date|date limite|apply by)\s*:?\s*([A-Za-zÀ-ÿ0-9 ,./-]{4,80})",
        r"([0-9]{1,2}\s+[A-Za-zÀ-ÿ]+\s+20[0-9]{2})",
        r"(20[0-9]{2}-[0-9]{2}-[0-9]{2})",
        r"([0-9]{1,2}/[0-9]{1,2}/20[0-9]{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return clean_text(match.group(1), 100)
    return ""


def extract_amount(text: str) -> str:
    patterns = [
        r"((?:€|\$|£|CAD|AUD|JPY)\s?[0-9][0-9,.\s]+)",
        r"([0-9][0-9,.\s]+\s?(?:EUR|USD|CAD|AUD|GBP|JPY))",
        r"(tuition fees?[^.]{0,80})",
        r"(living allowance[^.]{0,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return clean_text(match.group(1), 180)
    return ""


def score_candidate(text: str, url: str, organization: str) -> tuple[int, str]:
    folded = fold_text(text)
    score = 12
    signals: list[str] = []
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if any(hint in host for hint in OFFICIAL_HOST_HINTS):
        score += 28
        signals.append("source officielle")
    if organization:
        score += 8
        signals.append("organisme détecté")
    if is_direct_scholarship_url(url):
        score += 18
        signals.append("lien direct bourse")
    for term, weight in POSITIVE_SIGNALS.items():
        if term in folded:
            score += weight
            signals.append(term)
    for term, weight in NEGATIVE_SIGNALS.items():
        if term in folded:
            score -= weight
            signals.append(f"faible: {term}")
    score = max(0, min(score, 100))
    if score >= 75:
        label = "Bourse vérifiée"
    elif score >= 55:
        label = "Source sérieuse"
    else:
        label = "À vérifier"
    return score, label


def parse_scholarship_page(url: str, source_url: str = "") -> ScholarshipCandidate | None:
    if not is_direct_scholarship_url(url):
        return None
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = extract_title(soup)
    body_text = clean_text(soup.get_text(" "), 7000)
    full_text = f"{title} {body_text}"
    organization = infer_organization(soup, title, url)
    score, label = score_candidate(full_text, url, organization)
    if score < 45:
        return None
    return ScholarshipCandidate(
        title=title,
        url=url,
        organization=organization,
        country=infer_country(full_text, url),
        study_level=infer_level(full_text),
        funding_type=infer_funding(full_text),
        amount=extract_amount(body_text),
        eligible_countries="Afrique / International" if any(term in fold_text(full_text) for term in ("africa", "african", "developing countries")) else "International",
        deadline=extract_deadline(body_text),
        requirements=clean_text(body_text[:900], 900),
        description_text=clean_text(body_text[:1300], 1300),
        confidence_score=score,
        verification_label=label,
        source=urlparse(source_url or url).netloc.lower().removeprefix("www."),
        raw_data={"source_url": source_url, "source_host": urlparse(url).netloc},
    )


def discover_scholarships(
    *,
    country: str = "",
    level: str = "",
    query: str = "",
    source_urls: Iterable[str] = (),
    limit: int = 80,
) -> list[ScholarshipCandidate]:
    candidates: list[ScholarshipCandidate] = []
    search_urls = list(source_urls) or build_search_urls(country=country, level=level, query=query)
    for search_url in search_urls:
        if len(candidates) >= limit:
            return candidates
        try:
            html = fetch_html(search_url)
        except Exception:
            continue
        links = extract_result_links(html, search_url)
        if not links and is_direct_scholarship_url(search_url):
            links = [search_url]
        for url in links:
            if len(candidates) >= limit:
                return candidates
            if url in [item.url for item in candidates]:
                continue
            try:
                parsed = parse_scholarship_page(url, source_url=search_url)
            except Exception:
                continue
            if parsed:
                candidates.append(parsed)
    return candidates
