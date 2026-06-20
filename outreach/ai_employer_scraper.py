import re
import base64
import json
import unicodedata
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
    "agriculture": ["farm", "agriculture", "harvest", "greenhouse", "dairy", "meat", "food production", "ferme", "ouvrier agricole", "serre", "récolte", "légumes"],
    "construction": ["construction", "builder", "carpenter", "welder", "plumber", "electrician", "charpentier", "soudeur", "plombier", "électricien", "manoeuvre"],
    "tech": ["software", "developer", "engineer", "data", "IT", "cybersecurity", "cloud", "développeur", "informatique", "logiciel", "réseau"],
    "sante": ["nurse", "caregiver", "healthcare", "medical", "aged care", "support worker", "infirmier", "aide-soignant", "préposé", "soins", "santé"],
    "logistique": ["warehouse", "driver", "logistics", "transport", "forklift", "supply chain", "entrepôt", "chauffeur", "cariste", "livreur"],
    "hotellerie": ["hotel", "restaurant", "chef", "cook", "hospitality", "housekeeper", "hôtel", "cuisinier", "serveur", "sandwich", "ménage", "réceptionniste"],
    "education": ["teacher", "trainer", "education", "school", "lecturer", "enseignant", "formateur", "école"],
    "finance": ["accountant", "finance", "bookkeeper", "audit", "payroll", "comptable", "paie", "tenue de livres"],
    "industrie": ["manufacturing", "factory", "operator", "production", "machinist", "usine", "fabrication", "opérateur"],
    "commerce": ["sales", "retail", "customer service", "business development", "vente", "commerce", "service à la clientèle", "caissier"],
    "services": ["cleaner", "facility", "maintenance", "security", "support services", "nettoyeur", "entretien", "sécurité"],
}

SECTOR_KEYWORDS["agriculture"] += [
    "agricultura", "campo", "cosecha", "recoleccion", "invernadero",
    "temporero", "peon agricola", "fruta", "hortalizas", "zona rural",
]
SECTOR_KEYWORDS["construction"] += [
    "construccion", "albanil", "peon", "obra", "encofrador", "pintor", "soldador",
]
SECTOR_KEYWORDS["hotellerie"] += [
    "hosteleria", "restaurante", "cocinero", "camarero", "ayudante de cocina",
    "limpieza", "recepcionista",
]
SECTOR_KEYWORDS["industrie"] += [
    "fabrica", "operario", "produccion", "manipulador", "envasado", "almacen",
    "peon industrial",
]

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
    "candidats étrangers": 34,
    "extérieur du canada": 30,
    "permis de travail canadien": 28,
    "avec ou sans un permis de travail canadien valide": 42,
    "autres candidats, avec ou sans": 42,
    "travailleurs étrangers temporaires": 32,
    "eimt": 30,
    "candidature directe": 12,
    "ausbildung": 24,
    "duale berufsausbildung": 30,
    "vocational training": 28,
    "training contract": 24,
    "apprenticeship": 22,
    "b1": 12,
    "b2": 16,
    "deutschkenntnisse": 16,
    "german language": 14,
    "foreign applicants": 22,
    "international applicants": 22,
    "visa for vocational training": 32,
    "skilled worker visa": 26,
}

POSITIVE_SIGNALS.update({
    "contratacion en origen": 34,
    "permiso de trabajo": 24,
    "autorizacion de trabajo": 24,
    "trabajadores extranjeros": 24,
    "candidatos extranjeros": 24,
    "personas extranjeras": 20,
    "seasonal workers": 18,
    "trabajo de temporada": 18,
    "temporeros": 18,
    "alojamiento incluido": 16,
    "rural": 10,
    "zona rural": 12,
    "pueblo": 8,
    "despoblacion": 12,
    "reto demografico": 14,
})

BLOCKED_CONTENT_HOSTS = {
    "business-people.es",
    "schengenvisa.news",
    "careerical.com",
    "visaguide.world",
    "scholarshiproar.com",
    "opportunitiescorners.com",
}

BLOCKED_PATH_TERMS = (
    "/api/",
    "/blog/",
    "/news/",
    "/article/",
    "/articles/",
    "/visa-news/",
    "/schengen-visa-news/",
    "/list-of-",
    "/lists/",
)

TRUSTED_DIRECT_HOST_HINTS = (
    "greenhouse.io",
    "lever.co",
    "workdayjobs.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "successfactors",
    "bamboohr.com",
    "recruitee.com",
    "workable.com",
    "governmentjobs.com",
    "jobs.gc.ca",
    "seek.com.au",
    "seek.co.nz",
)

OFFICIAL_DIRECT_PATH_HOSTS = (
    "jobbank.gc.ca",
    "guichetemplois.gc.ca",
    "placeauxjeunes.qc.ca",
    "saskjobs.ca",
    "emploisnb.ca",
    "nbjobs.ca",
    "workbc.ca",
    "emplois.ca",
    "arbeitsagentur.de",
    "make-it-in-germany.com",
    "ausbildung.de",
    "azubiyo.de",
    "aubi-plus.de",
    "ihk-lehrstellenboerse.de",
    "make-it-in-germany.com",
    "eures.europa.eu",
    "sepe.es",
    "empleate.gob.es",
    "sistemanacionalempleo.es",
    "infojobs.net",
    "turijobs.com",
    "hosteleo.com",
)

DIRECT_APPLICATION_PATH_TERMS = (
    "/rechercheemplois/offredemploi/",
    "/jobsearch/jobpostingtfw/",
    "/jobsearch/jobposting/",
    "/jsp/joborder/detail.jsp",
    "/jobsuche/jobdetail/",
    "/emplois/",
    "/stellen/",
    "/stellenmarkt/",
    "/ausbildung/",
    "/jobs/",
    "/job/",
    "/careers/",
    "/career/",
    "/vacancy/",
    "/vacancies/",
    "/recruitment/",
    "/opportunities/",
    "/apply/",
    "/jobseekers/job/",
    "/oferta/",
    "/ofertas/",
    "/ofertas-empleo/",
    "/trabajo/",
    "/empleo/",
)


def is_direct_application_url(url: str) -> bool:
    parsed = urlparse(url or "")
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    if not host:
        return False
    if host in BLOCKED_CONTENT_HOSTS or any(blocked in host for blocked in BLOCKED_CONTENT_HOSTS):
        return False
    if any(term in path for term in BLOCKED_PATH_TERMS):
        return False
    if path.rstrip("/") in ("", "/jobs", "/job", "/careers", "/career", "/vacancies", "/opportunities"):
        return False
    if any(hint in host for hint in TRUSTED_DIRECT_HOST_HINTS):
        return True
    if "linkedin.com" in host:
        return "/jobs/view/" in path
    if "hosteleo.com" in host:
        if "/empresa/" in path:
            return False
        return bool(re.search(r"/[0-9]{4,}/", f"{path}/"))
    if "infojobs.net" in host:
        return bool(re.search(r"/ofertas-trabajo/.+?/[a-f0-9-]{8,}", path)) or "/oferta/" in path
    if "turijobs.com" in host:
        return bool(re.search(r"/ofertas-trabajo/.+?/[0-9]+", path)) or "/empleo/" in path
    if any(hint in host for hint in OFFICIAL_DIRECT_PATH_HOSTS):
        return any(term in path for term in DIRECT_APPLICATION_PATH_TERMS)
    return any(term in path for term in DIRECT_APPLICATION_PATH_TERMS)

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
    if country == "ES" and not query:
        base_query = (
            f'Espana Spain {sector_terms} "contratacion en origen" OR "permiso de trabajo" OR '
            f'"trabajadores extranjeros" OR temporeros OR "zona rural" oferta empleo'
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


def fold_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in value if not unicodedata.combining(ch)).lower()


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
        '[class*="company"]',
        '[class*="empresa"]',
        '[class*="employer"]',
        '[class*="recruiter"]',
        ".company",
        ".empresa",
        ".employer",
        ".job-company",
        ".posting-company",
        ".offer-company",
        ".job-ad-company",
    ]:
        node = soup.select_one(selector)
        if node:
            company = clean_text(node.get_text(" "), 220)
            if company and company.lower() not in {"empresa", "company", "empleador"}:
                return company

    separators = [" - ", " | ", " at ", " chez "]
    for sep in separators:
        if sep in title:
            parts = [p.strip() for p in title.split(sep) if p.strip()]
            if len(parts) >= 2:
                return clean_text(parts[-1], 220)
    body_text = clean_text(soup.get_text(" "), 5000)
    patterns = [
        r"Renseignements sur l[’']employeur\s+(.+?)\s+Candidature directe",
        r"Employer details\s+(.+?)\s+Direct Apply",
        r"Employer Name:\s*(.+?)\s+Posted Date:",
        r"Employeur\s+(.+?)\s+Ville\s+",
        r"Arbeitgeber:\s*(.+?)\s+Besondere Merkmale",
        r"bei\s+(.+?)\s+in\s+",
        r"Arbeitgeber\s+(.+?)\s+",
        r"Empresa\s+(.+?)\s+(?:Ubicaci[oó]n|Localidad|Provincia|Salario|Contrato|Jornada)",
        r"Compa[nñ][ií]a\s+(.+?)\s+(?:Ubicaci[oó]n|Localidad|Provincia|Salario|Contrato|Jornada)",
        r"Publicado por\s+(.+?)\s+(?:en|Ubicaci[oó]n|Localidad|Provincia)",
    ]
    for pattern in patterns:
        match = re.search(pattern, body_text, re.I)
        if match:
            company = clean_text(match.group(1), 220)
            if company:
                return company
    return ""


def extract_structured_jobposting(soup: BeautifulSoup) -> dict[str, str]:
    details: dict[str, str] = {}
    for script in soup.find_all("script", type=lambda value: value and "ld+json" in value):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            graph = item.get("@graph") if isinstance(item, dict) else None
            if isinstance(graph, list):
                items.extend(graph)
                continue
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type")
            if isinstance(item_type, list):
                is_job = any(str(value).lower() == "jobposting" for value in item_type)
            else:
                is_job = str(item_type).lower() == "jobposting"
            if not is_job:
                continue
            org = item.get("hiringOrganization") or item.get("organization") or {}
            if isinstance(org, dict):
                details["company_name"] = clean_text(org.get("name") or "", 220)
            details["title"] = clean_text(item.get("title") or "", 240)
            details["application_deadline"] = clean_text(item.get("validThrough") or "", 80)
            locations = item.get("jobLocation") or []
            locations = locations if isinstance(locations, list) else [locations]
            location_parts: list[str] = []
            for location in locations:
                if not isinstance(location, dict):
                    continue
                address = location.get("address") or {}
                if isinstance(address, dict):
                    location_parts.extend(
                        clean_text(address.get(key) or "", 120)
                        for key in ["addressLocality", "addressRegion", "addressCountry"]
                    )
            details["location"] = clean_text(", ".join(part for part in location_parts if part), 220)
            salary = item.get("baseSalary") or {}
            if isinstance(salary, dict):
                value = salary.get("value") or {}
                if isinstance(value, dict):
                    amount = value.get("value") or value.get("minValue") or ""
                    unit = value.get("unitText") or ""
                    currency = salary.get("currency") or ""
                    details["salary"] = clean_text(" ".join(str(part) for part in [amount, currency, unit] if part), 180)
            return {key: value for key, value in details.items() if value}
    return {}


def classify_sector(text: str, requested_sector: str = "autre") -> str:
    if requested_sector and requested_sector != "autre":
        return requested_sector
    lower = fold_text(text)
    best_sector = "autre"
    best_hits = 0
    for sector, keywords in SECTOR_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword.lower() in lower)
        if hits > best_hits:
            best_hits = hits
            best_sector = sector
    return best_sector


def score_evidence(text: str) -> tuple[int, str]:
    lower = fold_text(text)
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


def extract_jobbank_details(text: str) -> dict[str, str | int]:
    text = clean_text(text, 12000)

    def find(pattern: str, limit: int = 260) -> str:
        match = re.search(pattern, text, re.I)
        return clean_text(match.group(1), limit) if match else ""

    salary = find(r"Salaire\s+(.+?)\s+Conditions d[’']emploi", 180)
    if not salary:
        salary = find(r"Wage/Salary Info:\s*(.+?)\s+Posted Date:", 180)
    if not salary:
        salary = find(r"Salario\s+(.+?)(?:\s+Jornada|\s+Contrato|\s+Vacantes|\s+Fecha)", 180)
    location = ""
    worksite_index = text.lower().find("lieu de travail")
    if worksite_index > 0:
        location_index = text.lower().rfind("emplacement", 0, worksite_index)
        if location_index >= 0:
            location = clean_text(text[location_index + len("emplacement"):worksite_index], 220)
    if not location:
        location_matches = re.findall(r"Emplacement\s+(.+?)\s+Lieu de travail", text, re.I)
        for candidate in reversed(location_matches):
            candidate = clean_text(candidate, 220)
            if candidate and "emplacement actuel" not in candidate.lower() and "recherche" not in candidate.lower():
                location = candidate
                break
    if not location:
        location = find(r"Location:\s*(.+?)\s+Map it", 220)
    if not location:
        location = find(r"Ville\s+(.+?)\s+Horaire", 180)
    if not location:
        location = find(r"(?:UbicaciÃ³n|Ubicaci[oó]n|Localidad|Provincia|Lugar de trabajo)\s+(.+?)(?:\s+Salario|\s+Contrato|\s+Jornada|\s+Vacantes|\s+Fecha)", 220)
    vacancies = find(r"postes vacants\s+(.+?)\s+Source", 80)
    if not vacancies:
        vacancies = find(r"# of Positions:\s*(.+?)\s+Employment Terms:", 80)
    if not vacancies:
        vacancies = find(r"(?:Vacantes|NÃºmero de puestos|Numero de puestos)\s+(.+?)(?:\s+Salario|\s+Contrato|\s+Jornada|\s+Fecha)", 80)
    deadline = find(r"Publiée jusqu[’']au\s+([0-9]{4}-[0-9]{2}-[0-9]{2})", 80)
    if not deadline:
        deadline = find(r"Apply By Date:\s*(.+?)\s+How To Apply", 80)
    if not deadline:
        deadline = find(r"Date limite\s+(.+?)(?:\s+Postuler|\s+Retour|\s+Résumé)", 80)
    if not deadline:
        deadline = find(r"Bewerbungsfrist\s+(.+?)\s+", 80)
    if not deadline:
        deadline = find(r"(?:Fecha lÃ­mite|Fecha l[ií]mite|Fin de plazo|Plazo)\s+(.+?)(?:\s+Postular|\s+Inscribirse|\s+Solicitar|\s+Enviar|\s+Volver)", 80)
    start_date = find(r"Beginn ab\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4})", 80)
    if not start_date:
        start_date = find(r"Frühester Beginn\s+(.+?)\s+", 80)
    degree_required = find(r"Schulabschluss\s+(.+?)\s+", 120)
    training_type = ""
    if re.search(r"\bAusbildung\b|duale Berufsausbildung|Klassische duale Berufsausbildung", text, re.I):
        training_type = "Ausbildung"
    elif re.search(r"\bDuales Studium\b", text, re.I):
        training_type = "Duales Studium"
    language_level = ""
    lang_match = re.search(r"\b(B1|B2|C1|C2)\b", text, re.I)
    if lang_match and re.search(r"deutsch|german|sprache|language", text, re.I):
        language_level = lang_match.group(1).upper()
    who_can_apply = find(
        r"Qui peut postuler pour cette offre d[’']emploi\s*\?\s*(.+?)\s+Voir comment postuler",
        700,
    )
    if not who_can_apply:
        who_can_apply = find(r"Who can apply to this job\?\s*(.+?)\s+How to apply", 700)
    if not who_can_apply:
        who_can_apply = find(r"(?:QuiÃ©n puede postular|Qui[eé]n puede postular|Requisitos para postular|Requisitos)\s+(.+?)(?:\s+Inscribirse|\s+Postular|\s+Solicitar|\s+Enviar)", 700)

    province = ""
    province_match = re.search(r",\s*([A-Z]{2})\b", location)
    if province_match:
        province = province_match.group(1)
    elif location:
        province = location

    lower = fold_text(text)
    score = 35
    label = "À vérifier"
    if "avec ou sans un permis de travail canadien valide" in lower or "autres candidats, avec ou sans" in lower:
        score = 95
        label = "Accessible étranger"
    elif "candidats étrangers" in lower or "extérieur du canada" in lower:
        score = 90
        label = "Candidats étrangers"
    elif "eimt" in lower or "lmia" in lower or "travailleurs étrangers temporaires" in lower or "temporary foreign worker" in lower:
        score = 80
        label = "LMIA / EIMT"
    elif "candidature directe" in lower or "direct apply" in lower:
        score = 55
        label = "Candidature directe"
    if "ausbildung" in lower or "duale berufsausbildung" in lower or "vocational training" in lower:
        score = max(score, 78)
        label = "Ausbildung"
    if "visa for vocational training" in lower or "foreign applicants" in lower or "international applicants" in lower:
        score = max(score, 90)
        label = "Visa formation possible"
    if "citoyens canadiens et résidents permanents seulement" in lower or "canadian citizens and permanent residents only" in lower:
        score = min(score, 20)
        label = "Non prioritaire"
    if "contratacion en origen" in lower or "trabajadores extranjeros" in lower or "candidatos extranjeros" in lower:
        score = max(score, 88)
        label = "Accessible étranger"
    elif "permiso de trabajo" in lower or "autorizacion de trabajo" in lower:
        score = max(score, 76)
        label = "Permis de travail"
    elif "temporero" in lower or "trabajo de temporada" in lower or "alojamiento incluido" in lower:
        score = max(score, 70)
        label = "Saisonnier rural"
    if "zona rural" in lower or "despoblacion" in lower or "reto demografico" in lower:
        score = max(score, 68)
        if label in {"À vérifier", "Ã€ vÃ©rifier"}:
            label = "Zone rurale"

    return {
        "salary": salary,
        "location": location,
        "province": province,
        "application_deadline": deadline,
        "vacancies": vacancies,
        "who_can_apply": who_can_apply,
        "start_date": start_date,
        "degree_required": degree_required,
        "training_type": training_type,
        "language_level": language_level,
        "foreign_access_score": score,
        "foreign_access_label": label,
    }


def extract_result_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    blocked_hosts = {"bing.com", "www.bing.com", "duckduckgo.com", "www.duckduckgo.com"}
    blocked_text = {
        "alta empresa", "alta candidato", "login", "iniciar sesion", "registrate",
        "registro", "contacto", "aviso legal", "politica de privacidad",
        "cookies", "feedback", "images", "videos", "maps", "news", "shopping",
    }
    for anchor in soup.find_all("a", href=True):
        href = normalize_result_url(urljoin(base_url, anchor.get("href", "")))
        text = clean_text(anchor.get_text(" "), 220)
        folded_text = fold_text(text)
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.lower() in blocked_hosts:
            continue
        if folded_text in blocked_text:
            continue
        if not text or len(text) < 10:
            continue
        if href not in [item[1] for item in links]:
            links.append((text, href))
    useful_links = [
        item for item in links
        if is_direct_application_url(item[1])
        or any(term in fold_text(" ".join(item)) for term in [
            "oferta", "empleo", "trabajo", "job", "vacante", "camarero",
            "cocinero", "agricola", "peon", "operario", "construccion",
        ])
    ]
    return (useful_links or links)[:35]


def normalize_result_url(url: str) -> str:
    url = re.sub(r";jsessionid=[^?]+", "", url)
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
    if not is_direct_application_url(url):
        return None

    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    structured = extract_structured_jobposting(soup)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = extract_page_title(soup)
    body_text = clean_text(soup.get_text(" "), 5000)
    if structured.get("title") and title == "Opportunité employeur":
        title = structured["title"]
    score, signal = score_evidence(f"{title} {body_text}")
    details = extract_jobbank_details(body_text)
    for key in ["location", "salary", "application_deadline"]:
        if structured.get(key) and not details.get(key):
            details[key] = structured[key]
    if "fglo=1" in (source_url or "") and int(details.get("foreign_access_score") or 0) < 90:
        details["foreign_access_score"] = 90
        details["foreign_access_label"] = "Accessible étranger"
    source_lower = f"{source_url} {url}".lower()
    if country == "DE":
        if "angebotsart=4" in source_lower or "/jobsuche/jobdetail/" in source_lower:
            if int(details.get("foreign_access_score") or 0) < 82:
                details["foreign_access_score"] = 82
                details["foreign_access_label"] = "Ausbildung officielle"
        elif "ausbildung.de" in source_lower or "azubiyo.de" in source_lower or "aubi-plus.de" in source_lower:
            if int(details.get("foreign_access_score") or 0) < 70:
                details["foreign_access_score"] = 70
                details["foreign_access_label"] = "Ausbildung à vérifier"
    if country == "ES":
        rural_terms = ("agricultura", "campo", "temporero", "zona rural", "hosteleria", "construccion", "fabrica", "operario")
        if any(host in source_lower for host in ("eures.europa.eu", "sepe.es", "empleate.gob.es", "sistemanacionalempleo.es")):
            if int(details.get("foreign_access_score") or 0) < 72:
                details["foreign_access_score"] = 72
                details["foreign_access_label"] = "Espagne officielle"
        if any(term in fold_text(f"{title} {body_text}") for term in rural_terms):
            if int(details.get("foreign_access_score") or 0) < 68:
                details["foreign_access_score"] = 68
                details["foreign_access_label"] = "Zone rurale / métier tension"
    if int(details.get("foreign_access_score") or 0) > score:
        score = int(details["foreign_access_score"])
    if score < 25:
        return None

    company = structured.get("company_name") or extract_company_name(soup, title)
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
        location=(details.get("location") or details.get("province") or "").strip(),
        job_url=url,
        source_url=source_url or url,
        website=f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else "",
        contact_email=email,
        visa_signal=signal,
        evidence_text=evidence,
        confidence_score=score,
        raw_data={"source_host": parsed.netloc, "parser": "generic_html", "job_details": details},
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
