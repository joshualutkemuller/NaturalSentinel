"""State-level regulatory domain mappings and RSS feed registry.

Maps industry sectors to state agency types, provides per-state RSS feed URLs
for priority states, and links sectors to relevant federal RegulatoryDomains.
"""

# ---------------------------------------------------------------------------
# Sector → state agency type mappings
# ---------------------------------------------------------------------------

SECTOR_STATE_AGENCIES: dict[str, list[str]] = {
    "financial_services": ["state_banking", "state_securities"],
    "insurance": ["state_insurance"],
    "healthcare": ["state_health", "state_pharmacy"],
    "energy_utilities": ["state_puc"],
    "real_estate": ["state_real_estate", "state_banking"],
    "technology": ["state_securities", "state_ag"],
    "manufacturing": ["state_environmental", "state_labor"],
    "transportation": ["state_dot", "state_puc"],
}

# ---------------------------------------------------------------------------
# Per-state RSS / Atom feed registry (priority states for MVP)
# Keys are StateCode values (two-letter strings).
# Each entry: {"url": str, "sector": str, "agency": str}
# ---------------------------------------------------------------------------

STATE_AGENCY_RSS_FEEDS: dict[str, list[dict]] = {
    "CA": [
        {
            "url": "https://dfpi.ca.gov/news/feed/",
            "sector": "financial_services",
            "agency": "CA DFPI",
        },
        {
            "url": "https://www.insurance.ca.gov/0500-about-us/0300-press-releases/feed/",
            "sector": "insurance",
            "agency": "CA DOI",
        },
        {
            "url": "https://www.cdph.ca.gov/Programs/OPA/Pages/rssfeed.aspx",
            "sector": "healthcare",
            "agency": "CA CDPH",
        },
        {
            "url": "https://www.cpuc.ca.gov/news-and-outreach/all-news-and-updates/rss",
            "sector": "energy_utilities",
            "agency": "CA CPUC",
        },
        {
            "url": "https://www.dre.ca.gov/news/feed/",
            "sector": "real_estate",
            "agency": "CA DRE",
        },
    ],
    "NY": [
        {
            "url": "https://www.dfs.ny.gov/reports_and_publications/press_releases/rss",
            "sector": "financial_services",
            "agency": "NY DFS",
        },
        {
            "url": "https://www.dfs.ny.gov/reports_and_publications/press_releases/rss",
            "sector": "insurance",
            "agency": "NY DFS",
        },
        {
            "url": "https://www.health.ny.gov/press/releases/rss/feed.rss",
            "sector": "healthcare",
            "agency": "NY DOH",
        },
        {
            "url": "https://www.dps.ny.gov/press-releases.rss",
            "sector": "energy_utilities",
            "agency": "NY PSC",
        },
    ],
    "TX": [
        {
            "url": "https://www.dob.texas.gov/news/feed",
            "sector": "financial_services",
            "agency": "TX DOB",
        },
        {
            "url": "https://www.tdi.texas.gov/news/feed.xml",
            "sector": "insurance",
            "agency": "TX TDI",
        },
        {
            "url": "https://www.dshs.texas.gov/news/feed",
            "sector": "healthcare",
            "agency": "TX DSHS",
        },
        {
            "url": "https://www.puc.texas.gov/about/newsroom/rss.aspx",
            "sector": "energy_utilities",
            "agency": "TX PUC",
        },
    ],
    "FL": [
        {
            "url": "https://www.flofr.gov/sitemap/pressReleases-rss.htm",
            "sector": "financial_services",
            "agency": "FL OFR",
        },
        {
            "url": "https://www.floir.com/Sections/PandC/PressReleases.aspx?rss=true",
            "sector": "insurance",
            "agency": "FL OIR",
        },
        {
            "url": "https://www.floridahealth.gov/newsroom/feed",
            "sector": "healthcare",
            "agency": "FL DOH",
        },
    ],
    "IL": [
        {
            "url": "https://idfpr.illinois.gov/news/rss.xml",
            "sector": "financial_services",
            "agency": "IL IDFPR",
        },
        {
            "url": "https://idph.illinois.gov/news/rss",
            "sector": "healthcare",
            "agency": "IL IDPH",
        },
        {
            "url": "https://www.icc.illinois.gov/about/pressreleases/rss.aspx",
            "sector": "energy_utilities",
            "agency": "IL ICC",
        },
    ],
    "MA": [
        {
            "url": "https://www.mass.gov/orgs/division-of-banks/news.rss",
            "sector": "financial_services",
            "agency": "MA DOB",
        },
        {
            "url": "https://www.mass.gov/orgs/division-of-insurance/news.rss",
            "sector": "insurance",
            "agency": "MA DOI",
        },
        {
            "url": "https://www.mass.gov/orgs/department-of-public-health/news.rss",
            "sector": "healthcare",
            "agency": "MA DPH",
        },
        {
            "url": "https://www.mass.gov/orgs/department-of-public-utilities/news.rss",
            "sector": "energy_utilities",
            "agency": "MA DPU",
        },
    ],
}

# ---------------------------------------------------------------------------
# Sector → relevant federal RegulatoryDomain values
# Used to auto-expand a sector query to include the right federal domains.
# ---------------------------------------------------------------------------

SECTOR_TO_FEDERAL_DOMAINS: dict[str, list[str]] = {
    "financial_services": ["sec", "cfpb", "fed", "fdic", "occ", "finra", "cftc"],
    "healthcare": ["fda"],
    "insurance": ["cfpb", "fhfa"],
    "energy_utilities": ["epa"],
    "real_estate": ["cfpb", "fhfa", "sec"],
    "technology": ["sec", "cfpb"],
    "manufacturing": ["epa", "ustr"],
    "transportation": ["epa", "ustr"],
}
