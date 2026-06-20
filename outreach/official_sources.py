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
        label="Guichet-Emplois - Candidats étrangers de l'extérieur du Canada",
        url="https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?fglo=1&page=1&sort=M",
        source_type="job_board",
        notes="Offres publiées par des employeurs qui acceptent les candidats étrangers de l'extérieur du Canada.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services", "commerce"),
    ),
    OfficialSource(
        country="CA",
        label="Job Bank - Temporary Foreign Workers",
        url="https://www.jobbank.gc.ca/jobsearch/jobsearch?fsrc=32",
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
        country="CA",
        label="Place aux jeunes - Emplois en régions du Québec",
        url="https://placeauxjeunes.qc.ca/emplois",
        source_type="job_board",
        notes="Offres régionales québécoises. Publication automatique seulement avec signal étranger/permis.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services", "commerce", "finance", "education"),
    ),
    OfficialSource(
        country="CA",
        label="EmploisNB / NBJobs",
        url="https://www.emploisnb.ca/jobs",
        source_type="job_board",
        notes="Portail emploi Nouveau-Brunswick. Publication automatique seulement avec signal étranger/permis.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services", "commerce"),
    ),
    OfficialSource(
        country="CA",
        label="SaskJobs",
        url="https://www.saskjobs.ca/",
        source_type="job_board",
        notes="Portail emploi Saskatchewan. Publication automatique seulement avec signal étranger/permis.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services", "commerce", "finance"),
    ),
    OfficialSource(
        country="CA",
        label="WorkBC",
        url="https://www.workbc.ca/search-and-prepare-job/find-jobs",
        source_type="job_board",
        notes="Portail emploi Colombie-Britannique. Nécessite parfois exploration dynamique/API.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services", "commerce"),
    ),
    OfficialSource(
        country="CA",
        label="ALIS Alberta Job Postings",
        url="https://alis.alberta.ca/occinfo/alberta-job-postings/",
        source_type="job_board",
        notes="Portail Alberta; renvoie souvent vers Job Bank.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services", "commerce"),
    ),
    OfficialSource(
        country="CA",
        label="Emplois.ca / Jobs.ca",
        url="https://www.emplois.ca/jobs",
        source_type="job_board",
        notes="Réseau privé canadien. Publication automatique seulement avec signal étranger/permis.",
        sectors=("tech", "finance", "sante", "logistique", "hotellerie", "industrie", "services", "commerce"),
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
        country="DE",
        label="Bundesagentur für Arbeit - Ausbildung",
        url="https://www.arbeitsagentur.de/jobsuche/suche?angebotsart=4",
        source_type="training_board",
        notes="Annonces officielles Ausbildung / apprentissage professionnel en Allemagne.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services", "commerce", "finance", "education"),
    ),
    OfficialSource(
        country="DE",
        label="Ausbildung.de - Stellen",
        url="https://www.ausbildung.de/stellen/",
        source_type="training_board",
        notes="Contrats Ausbildung et duales Studium. Publication automatique avec badge Ausbildung à vérifier.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services", "commerce", "finance", "education"),
    ),
    OfficialSource(
        country="DE",
        label="Azubiyo - Stellenmarkt",
        url="https://www.azubiyo.de/stellenmarkt/",
        source_type="training_board",
        notes="Portail Ausbildung et duales Studium. Publication automatique prudente.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services", "commerce", "finance", "education"),
    ),
    OfficialSource(
        country="DE",
        label="Aubi-plus - Ausbildung",
        url="https://www.aubi-plus.de/ausbildung/",
        source_type="training_board",
        notes="Portail Ausbildung. Publication automatique prudente.",
        sectors=("agriculture", "construction", "sante", "logistique", "hotellerie", "tech", "industrie", "services", "commerce", "finance", "education"),
    ),
    OfficialSource(
        country="ES",
        label="EURES - Offres Espagne",
        url="https://eures.europa.eu/jobseekers/find-job_en?country=es",
        source_type="job_board",
        notes="Portail officiel européen. Priorité aux annonces directes et métiers en tension.",
        sectors=("agriculture", "construction", "hotellerie", "industrie", "logistique", "services"),
    ),
    OfficialSource(
        country="ES",
        label="SEPE / Empléate - Portail emploi Espagne",
        url="https://www.empleate.gob.es/empleo/#/ofertas",
        source_type="job_board",
        notes="Portail public espagnol. Publication automatique seulement avec signal étranger, permis ou rural.",
        sectors=("agriculture", "construction", "hotellerie", "industrie", "logistique", "services"),
    ),
    OfficialSource(
        country="ES",
        label="InfoJobs Espagne - Agriculture",
        url="https://www.infojobs.net/ofertas-trabajo/agricultura",
        source_type="job_board",
        notes="Portail privé espagnol; annonce publiée uniquement si lien direct et signaux suffisants.",
        sectors=("agriculture",),
    ),
    OfficialSource(
        country="ES",
        label="InfoJobs Espagne - Construcción",
        url="https://www.infojobs.net/ofertas-trabajo/construccion",
        source_type="job_board",
        notes="Bâtiment / travaux. Publication automatique prudente.",
        sectors=("construction",),
    ),
    OfficialSource(
        country="ES",
        label="Turijobs - Hostelería Espagne",
        url="https://www.turijobs.com/ofertas-trabajo/espana",
        source_type="job_board",
        notes="Hôtellerie, restauration et tourisme. Publication automatique avec filtre de pertinence.",
        sectors=("hotellerie",),
    ),
    OfficialSource(
        country="ES",
        label="Hosteleo - Restauración Espagne",
        url="https://www.hosteleo.com/ofertas-trabajo/",
        source_type="job_board",
        notes="Restauration et cuisine. Publication automatique prudente.",
        sectors=("hotellerie",),
    ),
    OfficialSource(
        country="ES",
        label="Hosteleo - Camarero",
        url="https://www.hosteleo.com/es/camarero",
        source_type="job_board",
        notes="Offres serveur/bar en Espagne avec ville et salaire.",
        sectors=("hotellerie",),
    ),
    OfficialSource(
        country="ES",
        label="Hosteleo - Cocinero",
        url="https://www.hosteleo.com/es/cocinero",
        source_type="job_board",
        notes="Offres cuisine en Espagne.",
        sectors=("hotellerie",),
    ),
    OfficialSource(
        country="ES",
        label="Hosteleo - Ayudante de cocina",
        url="https://www.hosteleo.com/es/ayudante-de-cocina",
        source_type="job_board",
        notes="Offres aide-cuisine et restauration.",
        sectors=("hotellerie",),
    ),
    OfficialSource(
        country="ES",
        label="Hosteleo - Limpieza",
        url="https://www.hosteleo.com/es/limpieza",
        source_type="job_board",
        notes="Offres nettoyage hôtellerie/restauration.",
        sectors=("hotellerie", "services"),
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
