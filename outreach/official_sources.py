from dataclasses import dataclass


@dataclass(frozen=True)
class OfficialSource:
    country: str
    label: str
    url: str
    source_type: str
    notes: str
    sectors: tuple[str, ...] = ("autre",)


OFFICIAL_SOURCES: tuple[OfficialSource, ...] = (
    OfficialSource(
        country="CA",
        label="Job Bank - Temporary Foreign Workers",
        url="https://www.jobbank.gc.ca/temporary-foreign-workers",
        source_type="job_board",
        notes="Offres canadiennes pour travailleurs étrangers temporaires, avec signaux LMIA.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services"),
    ),
    OfficialSource(
        country="CA",
        label="Canada.ca - Temporary Foreign Worker Program",
        url="https://www.canada.ca/en/employment-social-development/services/foreign-workers.html",
        source_type="visa_program",
        notes="Source officielle pour comprendre LMIA et obligations employeurs.",
    ),
    OfficialSource(
        country="NZ",
        label="Immigration New Zealand - Accredited employers",
        url="https://www.immigration.govt.nz/work/requirements-for-work-visas/approved-employers/",
        source_type="employer_register",
        notes="Liste officielle des employeurs approuvés/accrédités pour recruter à l'étranger.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services"),
    ),
    OfficialSource(
        country="NZ",
        label="Immigration New Zealand - AEWV",
        url="https://www.immigration.govt.nz/visas/accredited-employer-work-visa",
        source_type="visa_program",
        notes="Règles officielles de l'Accredited Employer Work Visa.",
    ),
    OfficialSource(
        country="AU",
        label="Australian Border Force - Visas and sponsorship",
        url="https://www.abf.gov.au/about-us/what-we-do/sponsor-sanctions/visas-and-sponsorship",
        source_type="sponsor_compliance",
        notes="Informations officielles sur sponsoring, obligations et sanctions.",
    ),
    OfficialSource(
        country="AU",
        label="Home Affairs - Skills in Demand / subclass 482",
        url="https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skills-in-demand-482",
        source_type="visa_program",
        notes="Programme officiel remplaçant le TSS 482 pour travailleurs qualifiés sponsorisés.",
        sectors=("construction", "sante", "tech", "industrie", "finance", "education"),
    ),
    OfficialSource(
        country="GB",
        label="GOV.UK - Register of licensed sponsors",
        url="https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers",
        source_type="employer_register",
        notes="Registre officiel des organisations autorisées à sponsoriser des travailleurs au Royaume-Uni.",
        sectors=("construction", "sante", "tech", "hotellerie", "finance", "education", "services"),
    ),
    OfficialSource(
        country="DE",
        label="Make it in Germany - Job listings",
        url="https://www.make-it-in-germany.com/en/working-in-germany/job-listings",
        source_type="job_board",
        notes="Portail officiel allemand pour travailleurs qualifiés étrangers.",
        sectors=("construction", "sante", "tech", "industrie", "education"),
    ),
    OfficialSource(
        country="BE",
        label="Belgium.be - Work permit",
        url="https://www.belgium.be/en/work/coming_to_work_in_belgium/work_permit",
        source_type="visa_program",
        notes="Informations officielles sur l'autorisation de travail en Belgique.",
    ),
    OfficialSource(
        country="BE",
        label="Working in Belgium",
        url="https://www.workinginbelgium.fgov.be/en/home.html",
        source_type="work_portal",
        notes="Portail officiel belge pour démarches liées au travail international.",
    ),
)


COUNTRY_GROUPS = {
    "EU": ("GB", "DE", "BE", "FR", "NL", "IE", "CH", "IT", "ES", "PT"),
}


def expand_country_filter(country: str) -> tuple[str, ...]:
    country = (country or "").upper().strip()
    if not country:
        return ()
    return COUNTRY_GROUPS.get(country, (country,))


def get_sources(country: str = "", sector: str = "") -> list[OfficialSource]:
    countries = set(expand_country_filter(country))
    sector = (sector or "").strip().lower()
    sources = []
    for source in OFFICIAL_SOURCES:
        if countries and source.country not in countries:
            continue
        if sector and "autre" not in source.sectors and sector not in source.sectors:
            continue
        sources.append(source)
    return sources
