import re
import base64
from dataclasses import dataclass, field
from html import unescape
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from outreach.official_sources import get_sources


USER_AGENT = (
    "Immigration97EmployerScout/1.0 "
    "(job opportunity discovery; contact: contact@immigration97.com)"
)

COUNTRY_LABELS = {
    "CA": "Canada",
    "NZ": "New Zealand",
    "AU": "Australia",
    "EU": "Europe",
    "FR": "France",
    "DE": "Germany",
    "BE": "Belgium",
    "CH": "Switzerland",
    "GB": "United Kingdom",
    "IE": "Ireland",
    "NL": "Netherlands",
    "IT": "Italy",
    "ES": "Spain",
    "PT": "Portugal",
}

EU_COUNTRIES = ["FR", "DE", "BE", "CH", "GB", "IE", "NL", "IT", "ES", "PT"]

SECTOR_KEYWORDS = {
    "agriculture": ["farm", "agriculture", "harvest", "greenhouse", "dairy", "meat", "food production"],
    "construction": ["construction", "builder", "carpenter", "welder", "plumber", "electrician"],
    "tech": ["software", "developer", "engineer", "data", "IT", "cybersecurity", "cloud"],
    "sante": ["nurse", "caregiver", "healthcare", "medical", "aged care", "support worker"],
    "logistique": ["warehouse", "driver", "logistics", "transport", "forklift", "supply chain"],
    "hotellerie": ["hotel", "restaurant", "chef", "cook", "hospitality", "housekeeper"],
    "education": ["teacher", "trainer", "education", "school", "lecturer"],
    "finance": ["accountant", "finance", "bookkeeper", "audit", "payroll"],
    "industrie": ["manufacturing", "factory", "operator", "production", "machinist"],
    "commerce": ["sales", "retail", "customer service", "business development"],
    "services": ["cleaner", "facility", "maintenance", "security", "support services"],
}

POSITIVE_SIGNALS = {
    "visa sponsorship": 28,
    "sponsorship available": 28,
    "work permit": 20,
    "foreign worker": 22,
    "international applicants": 20,
    "overseas applicants": 20,
    "relocation support": 18,
    "relocation package": 18,
    "lmia": 30,
    "temporary foreign worker": 30,
    "seasonal worker": 14,
    "accredited employer": 32,
    "visa accredited": 30,
    "sponsor licence": 26,
    "skilled worker visa": 26,
    "certificate of sponsorship": 26,
    "african": 10,
    "international workers": 18,
}

NEGATIVE_SIGNALS = {
    "no sponsorship": 40,
    "not sponsor": 35,
    "cannot sponsor": 35,
    "must be a citizen": 30,
    "citizens only": 35,
    "permanent residents only": 25,
    "must already have the right to work": 20,
}


@dataclass
class EmployerLeadCandidate:
    title: str
    job_url: str
    country: str
    sector: str = "autre"
    company_name: str = ""
    location: str = ""
    source_url: str = ""
    website: str = ""
    contact_email: str = ""
    visa_signal: str = ""
    evidence_text: str = ""
    confidence_score: int = 0
    raw_data: dict = field(default_factory=dict)


def expand_country_codes(countries: Iterable[str]) -> list[str]:
    expanded: list[str] = []
    for code in countries:
        code = (code or "").strip().upper()
        if not code:
            continue
        if code == "EU":
            expanded.extend(EU_COUNTRIES)
        else:
            expanded.append(code)
    return list(dict.fromkeys(expanded))


def build_search_urls(country: str, sector: str = "autre", query: str = "") -> list[str]:
    country_label = COUNTRY_LABELS.get(country, country)
    sector_terms = " ".join(SECTOR_KEYWORDS.get(sector, [])) if sector != "autre" else "jobs"
    base_query = query or (
        f'{country_label} {sector_terms} "visa sponsorship" OR "foreign workers" OR '
        f'"international applicants" employer careers'
    )
    encoded = quote_plus(base_query)
    urls = [
        f"https://www.bing.com/search?q={encoded}",
        f"https://duckduckgo.com/html/?q={encoded}",
    ]
    urls.extend(source.url for source in get_sources(country=country, sector=sector))
    return list(dict.fromkeys(urls))


def fetch_html(url: str, timeout: int = 20) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en,fr;q=0.8"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text


def clean_text(value: str, limit: int = 1200) -> str:
    value = unescape(value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def extract_email(text: str) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text or "", re.I)
    return match.group(0).lower() if match else ""


def extract_page_title(soup: BeautifulSoup) -> str:
    if soup.find("h1"):
        return clean_text(soup.find("h1").get_text(" "), 240)
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return clean_text(og_title["content"], 240)
    if soup.title:
        return clean_text(soup.title.get_text(" "), 240)
    return "Opportunité employeur"


def extract_company_name(soup: BeautifulSoup, title: str) -> str:
    for selector in [
        '[data-testid*="company"]',
        ".company",
        ".employer",
        ".job-company",
        ".posting-company",
    ]:
        node = soup.select_one(selector)
        if node:
            return clean_text(node.get_text(" "), 220)

    separators = [" - ", " | ", " at ", " chez "]
    for sep in separators:
        if sep in title:
            parts = [p.strip() for p in title.split(sep) if p.strip()]
            if len(parts) >= 2:
                return clean_text(parts[-1], 220)
    return ""


def classify_sector(text: str, requested_sector: str = "autre") -> str:
    if requested_sector and requested_sector != "autre":
        return requested_sector
    lower = (text or "").lower()
    best_sector = "autre"
    best_hits = 0
    for sector, keywords in SECTOR_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword.lower() in lower)
        if hits > best_hits:
            best_hits = hits
            best_sector = sector
    return best_sector


def score_evidence(text: str) -> tuple[int, str]:
    lower = (text or "").lower()
    score = 10
    signals: list[str] = []
    for signal, weight in POSITIVE_SIGNALS.items():
        if signal in lower:
            score += weight
            signals.append(signal)
    for signal, weight in NEGATIVE_SIGNALS.items():
        if signal in lower:
            score -= weight
            signals.append(f"negative: {signal}")
    return max(0, min(score, 100)), ", ".join(signals[:5])


def extract_result_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    blocked_hosts = {"bing.com", "www.bing.com", "duckduckgo.com", "www.duckduckgo.com"}
    for anchor in soup.find_all("a", href=True):
        href = normalize_result_url(urljoin(base_url, anchor.get("href", "")))
        text = clean_text(anchor.get_text(" "), 220)
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.lower() in blocked_hosts:
            continue
        if not text or len(text) < 10:
            continue
        if href not in [item[1] for item in links]:
            links.append((text, href))
        if len(links) >= 25:
            break
    return links


def normalize_result_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])

    if "u" in query and query["u"]:
        raw = query["u"][0]
        if raw.startswith("a1"):
            encoded = raw[2:]
            padding = "=" * (-len(encoded) % 4)
            try:
                decoded = base64.urlsafe_b64decode((encoded + padding).encode("ascii")).decode("utf-8")
                if decoded.startswith(("http://", "https://")):
                    return decoded
            except Exception:
                pass
        if raw.startswith(("http://", "https://")):
            return raw

    return url


def parse_employer_page(url: str, country: str, sector: str = "autre", source_url: str = "") -> EmployerLeadCandidate | None:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = extract_page_title(soup)
    body_text = clean_text(soup.get_text(" "), 5000)
    score, signal = score_evidence(f"{title} {body_text}")
    if score < 25:
        return None

    company = extract_company_name(soup, title)
    email = extract_email(body_text)
    parsed = urlparse(url)
    evidence_start = 0
    lower_body = body_text.lower()
    for key in POSITIVE_SIGNALS:
        index = lower_body.find(key)
        if index >= 0:
            evidence_start = max(index - 140, 0)
            break
    evidence = clean_text(body_text[evidence_start:evidence_start + 700], 700)

    return EmployerLeadCandidate(
        title=title,
        company_name=company,
        country=country,
        sector=classify_sector(body_text, sector),
        job_url=url,
        source_url=source_url or url,
        website=f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else "",
        contact_email=email,
        visa_signal=signal,
        evidence_text=evidence,
        confidence_score=score,
        raw_data={"source_host": parsed.netloc, "parser": "generic_html"},
    )


def discover_employers(
    *,
    countries: Iterable[str],
    sector: str = "autre",
    query: str = "",
    source_urls: Iterable[str] = (),
    limit: int = 50,
) -> list[EmployerLeadCandidate]:
    candidates: list[EmployerLeadCandidate] = []
    country_codes = expand_country_codes(countries)

    for country in country_codes:
        search_urls = list(source_urls) or build_search_urls(country, sector=sector, query=query)
        for search_url in search_urls:
            if len(candidates) >= limit:
                return candidates
            try:
                search_html = fetch_html(search_url)
            except Exception:
                continue

            links = extract_result_links(search_html, search_url)
            if not links and search_url not in [item.job_url for item in candidates]:
                links = [(search_url, search_url)]

            for _, url in links:
                if len(candidates) >= limit:
                    return candidates
                try:
                    parsed = parse_employer_page(url, country=country, sector=sector, source_url=search_url)
                except Exception:
                    continue
                if parsed and parsed.job_url not in [item.job_url for item in candidates]:
                    candidates.append(parsed)

    return candidates
