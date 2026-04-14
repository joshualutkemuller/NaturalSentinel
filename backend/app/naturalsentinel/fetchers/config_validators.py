"""Startup completeness checks for sector/domain/state mappings.

Five hardcoded mapping dicts drive fetcher dispatch and filtering:

- ``DOMAIN_BUSINESS_LINES``       (``fetchers/base.py``)
- ``SECTOR_STATE_AGENCIES``       (``fetchers/state_domains.py``)
- ``SECTOR_TO_FEDERAL_DOMAINS``   (``fetchers/state_domains.py``)
- ``STATE_AGENCY_RSS_FEEDS``      (``fetchers/state_domains.py``)
- ``DOMAIN_TO_AGENCY``            (``fetchers/live/federal/federal_register.py``)

None of them are cross-checked against the source enums
(``RegulatoryDomain``, ``IndustrySector``, ``StateCode``). A typo like
``"sfdc"`` instead of ``"sec"`` silently filters that domain out of
every scan.

``validate_mappings()`` runs at app startup and raises
``ConfigurationError`` listing every gap, so a bad mapping crashes
boot loudly instead of degrading silently.

This will be replaced by the YAML loader's Pydantic validators in
Phase P1.2 — until then, a boot-time check is the safety net.
"""

from __future__ import annotations

from app.naturalsentinel.domain.enums import (
    IndustrySector,
    RegulatoryDomain,
    StateCode,
)


class ConfigurationError(RuntimeError):
    """Raised on boot when a mapping dict is incomplete or refers to
    enum values that do not exist."""


def _enum_values(enum_cls: type) -> set[str]:
    return {e.value for e in enum_cls}


def validate_mappings() -> None:
    """Validate every sector/domain/state mapping against the enums.

    Raises :class:`ConfigurationError` with a multi-line message listing
    every gap. The caller (FastAPI startup, CLI boot) should treat a
    raised error as fatal.
    """
    from app.naturalsentinel.fetchers.base import DOMAIN_BUSINESS_LINES
    from app.naturalsentinel.fetchers.live.federal.federal_register import (
        DOMAIN_TO_AGENCY,
    )
    from app.naturalsentinel.fetchers.state_domains import (
        SECTOR_STATE_AGENCIES,
        SECTOR_TO_FEDERAL_DOMAINS,
        STATE_AGENCY_RSS_FEEDS,
    )

    domain_values = _enum_values(RegulatoryDomain)
    sector_values = _enum_values(IndustrySector)
    state_values = _enum_values(StateCode)

    gaps: list[str] = []

    # DOMAIN_BUSINESS_LINES: every RegulatoryDomain must have business lines
    dbl_keys = set(DOMAIN_BUSINESS_LINES.keys())
    if missing := (domain_values - dbl_keys):
        gaps.append(
            f"DOMAIN_BUSINESS_LINES missing entries for RegulatoryDomain values: "
            f"{sorted(missing)}"
        )
    if extra := (dbl_keys - domain_values):
        gaps.append(
            f"DOMAIN_BUSINESS_LINES has keys that are not valid RegulatoryDomain "
            f"values: {sorted(extra)}"
        )

    # SECTOR_STATE_AGENCIES: every IndustrySector must have at least one agency type
    ssa_keys = set(SECTOR_STATE_AGENCIES.keys())
    if missing := (sector_values - ssa_keys):
        gaps.append(
            f"SECTOR_STATE_AGENCIES missing entries for IndustrySector values: "
            f"{sorted(missing)}"
        )
    if extra := (ssa_keys - sector_values):
        gaps.append(
            f"SECTOR_STATE_AGENCIES has keys that are not valid IndustrySector "
            f"values: {sorted(extra)}"
        )

    # SECTOR_TO_FEDERAL_DOMAINS: every IndustrySector maps to ≥1 valid RegulatoryDomain
    stfd_keys = set(SECTOR_TO_FEDERAL_DOMAINS.keys())
    if missing := (sector_values - stfd_keys):
        gaps.append(
            f"SECTOR_TO_FEDERAL_DOMAINS missing entries for IndustrySector values: "
            f"{sorted(missing)}"
        )
    if extra := (stfd_keys - sector_values):
        gaps.append(
            f"SECTOR_TO_FEDERAL_DOMAINS has keys that are not valid IndustrySector "
            f"values: {sorted(extra)}"
        )
    invalid_targets: set[str] = set()
    for sector, targets in SECTOR_TO_FEDERAL_DOMAINS.items():
        for target in targets:
            if target not in domain_values:
                invalid_targets.add(f"{sector}→{target}")
    if invalid_targets:
        gaps.append(
            f"SECTOR_TO_FEDERAL_DOMAINS contains values that are not valid "
            f"RegulatoryDomain members: {sorted(invalid_targets)}"
        )

    # STATE_AGENCY_RSS_FEEDS: every key is a valid StateCode, every feed.sector is valid
    sars_keys = set(STATE_AGENCY_RSS_FEEDS.keys())
    if extra := (sars_keys - state_values):
        gaps.append(
            f"STATE_AGENCY_RSS_FEEDS has keys that are not valid StateCode "
            f"values: {sorted(extra)}"
        )
    invalid_feed_sectors: set[str] = set()
    for state, feeds in STATE_AGENCY_RSS_FEEDS.items():
        for entry in feeds:
            sector = entry.get("sector")
            if sector is None or sector not in sector_values:
                invalid_feed_sectors.add(f"{state}→{sector!r}")
    if invalid_feed_sectors:
        gaps.append(
            f"STATE_AGENCY_RSS_FEEDS contains feed entries with invalid "
            f"IndustrySector values: {sorted(invalid_feed_sectors)}"
        )

    # DOMAIN_TO_AGENCY: keys must be valid RegulatoryDomain values
    dta_keys = set(DOMAIN_TO_AGENCY.keys())
    if extra := (dta_keys - domain_values):
        gaps.append(
            f"DOMAIN_TO_AGENCY (federal_register) has keys that are not valid "
            f"RegulatoryDomain values: {sorted(extra)}"
        )

    if gaps:
        raise ConfigurationError(
            "NaturalSentinel mapping validation failed:\n  - " + "\n  - ".join(gaps)
        )


__all__ = ["ConfigurationError", "validate_mappings"]
