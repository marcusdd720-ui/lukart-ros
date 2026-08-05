"""
Render legal authorities block for pleadings.

Delegates structure to AuthoritySection; this module stays a thin text adapter.
"""

from __future__ import annotations

from knowledge.legal_query import LegalQuery
from knowledge.models.authority_section import (
    AuthoritySection,
    build_authority_section,
)


def build_section(
    legal_query: LegalQuery,
    case_id: str,
    *,
    statute_focus_id: str | None = "statute:kk:284:2",
) -> AuthoritySection:
    """Return structured authorities (preferred API)."""
    return build_authority_section(
        legal_query,
        case_id,
        focus_statute_id=statute_focus_id,
    )


def render_authorities_block(
    legal_query: LegalQuery,
    case_id: str,
    *,
    statute_focus_id: str | None = "statute:kk:284:2",
) -> str:
    """
    Plain-text authorities block (backward compatible).

    Prefer build_section() when feeding DOCX or tests.
    """
    section = build_section(
        legal_query,
        case_id,
        statute_focus_id=statute_focus_id,
    )
    return section.to_plain_text()