"""Medical document structure extractor.

Parses clinical notes and discharge summaries into their SOAP-style
sections (Chief Complaint, HPI, PMH, Assessment, Plan, etc.) and
extracts ICD / CPT code metadata per section.

Split out of ``extractors.py`` in Phase R.
"""

from __future__ import annotations

import re

from app.naturalsentinel.documents.extractors._common import (
    line_numbers,
    make_node,
    slugify,
)
from app.naturalsentinel.domain.document import DocumentNode

_MEDICAL_SECTIONS = [
    "CHIEF COMPLAINT",
    "HISTORY OF PRESENT ILLNESS",
    "HPI",
    "PAST MEDICAL HISTORY",
    "PMH",
    "MEDICATIONS",
    "ALLERGIES",
    "REVIEW OF SYSTEMS",
    "ROS",
    "PHYSICAL EXAMINATION",
    "VITAL SIGNS",
    "ASSESSMENT",
    "DIAGNOSIS",
    "PLAN",
    "ORDERS",
    "LABS",
    "RADIOLOGY",
    "PROCEDURES",
    "DISCHARGE SUMMARY",
    "FOLLOW-UP",
    "NOTES",
]
_MEDICAL_PATTERN = re.compile(
    r"(?mi)^(" + "|".join(re.escape(s) for s in _MEDICAL_SECTIONS) + r")[:\s]*$",
)


def extract_medical(raw_text: str, doc_id: str) -> list[DocumentNode]:
    """Extract medical document structure: SOAP + standard sections."""
    matches = list(_MEDICAL_PATTERN.finditer(raw_text))
    if not matches:
        return []

    nodes: list[DocumentNode] = []
    for idx, m in enumerate(matches):
        pos = m.start()
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_text)
        heading = m.group(0).strip().upper().rstrip(":")
        text = raw_text[pos:end_pos]
        slug = slugify(heading)
        uri_path = f"section-{idx + 1}--{slug}"
        ls, le = line_numbers(raw_text, pos)

        # Extract ICD/CPT codes
        meta: dict = {}
        icd_codes = re.findall(r"\b[A-Z]\d{2}(?:\.\d+)?\b", text)
        if icd_codes:
            meta["icd_codes"] = list(set(icd_codes[:20]))
        cpt_codes = re.findall(r"\b\d{5}[A-Z]?\b", text)
        if cpt_codes:
            meta["cpt_codes"] = list(set(cpt_codes[:20]))

        nodes.append(
            make_node(
                doc_id,
                idx,
                heading,
                text,
                "medical_section",
                heading,
                uri_path,
                pos,
                end_pos,
                ls,
                le,
                meta,
            )
        )
    return nodes
