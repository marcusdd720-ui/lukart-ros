"""
Knowledge Operating System (KOS)

File: knowledge/models/render.py
Version: 1.0.1
Sprint: CASE-002

Render a Case + Decision into a formal procedural letter (plain text).
No generative AI — deterministic mapping from domain model only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from knowledge.models.case import Case, Decision, Party


@dataclass(slots=True)
class LetterContext:
    """Optional header fields not stored on Case."""

    sender_name: str = ""
    sender_address: str = ""
    sender_contact: str = ""
    recipient_lines: list[str] | None = None
    place: str = ""
    letter_date: date | None = None
    subject: str = ""


class CaseLetterRenderer:
    """
    Build a formal letter from Case.latest_decision() (or a given decision).
    """

    def render(
        self,
        case: Case,
        *,
        decision: Decision | None = None,
        context: LetterContext | None = None,
    ) -> str:
        ctx = context or LetterContext()
        dec = decision or case.latest_decision()
        if dec is None:
            raise ValueError("Case has no decision to render.")

        fact_map = {f.id: f for f in case.facts}
        law_map = {b.id: b for b in case.legal_bases}

        lines: list[str] = []

        if ctx.sender_name:
            lines.append(ctx.sender_name)
        if ctx.sender_address:
            lines.append(ctx.sender_address)
        if ctx.sender_contact:
            lines.append(ctx.sender_contact)

        place_date = self._place_date(ctx)
        if place_date:
            if lines:
                lines.append("")
            lines.append(place_date)

        recipient = ctx.recipient_lines or self._default_recipient(case)
        if recipient:
            lines.append("")
            lines.extend(recipient)

        lines.append("")
        if case.signature:
            lines.append(f"Sygn. akt: {case.signature}")
        subject = ctx.subject or case.title or dec.summary
        lines.append(f"Dotyczy: {subject}")
        lines.append("")
        lines.append(self._salutation(case))
        lines.append("")

        lines.append("I. Ustalenia faktyczne")
        lines.append("")
        if not dec.fact_ids:
            lines.append("(brak powiązanych faktów)")
        else:
            for i, fid in enumerate(dec.fact_ids, start=1):
                fact = fact_map.get(fid)
                if fact is None:
                    lines.append(f"{i}. [brak faktu id={fid}]")
                    continue
                sources = (
                    f" (źródła: {', '.join(fact.source_refs)})"
                    if fact.source_refs
                    else ""
                )
                lines.append(f"{i}. {fact.statement}{sources}")
        lines.append("")

        lines.append("II. Podstawa prawna")
        lines.append("")
        if not dec.legal_basis_ids:
            lines.append("(brak podstawy prawnej)")
        else:
            for i, lid in enumerate(dec.legal_basis_ids, start=1):
                basis = law_map.get(lid)
                if basis is None:
                    lines.append(f"{i}. [brak podstawy id={lid}]")
                    continue
                note = f" — {basis.note}" if basis.note else ""
                lines.append(f"{i}. {basis.reference}{note}")
        lines.append("")

        lines.append("III. Stanowisko")
        lines.append("")
        lines.append(dec.summary)
        lines.append("")

        lines.append("IV. Wnioski")
        lines.append("")
        if not dec.outcomes:
            lines.append("1. Przyjęcie niniejszego pisma do akt.")
        else:
            for i, item in enumerate(dec.outcomes, start=1):
                lines.append(f"{i}. {item}")
        lines.append("")

        lines.append("Z poważaniem")
        lines.append("")
        if ctx.sender_name:
            lines.append(ctx.sender_name)
        else:
            applicant = self._party_by_role(case, "applicant")
            lines.append(applicant.name if applicant else "")

        return "\n".join(lines).rstrip() + "\n"

    def _place_date(self, ctx: LetterContext) -> str:
        d = ctx.letter_date or datetime.now(UTC).date()
        place = ctx.place.strip()
        formatted = d.strftime("%d.%m.%Y")
        if place:
            return f"{place}, dnia {formatted} r."
        return f"dnia {formatted} r."

    def _salutation(self, case: Case) -> str:
        return "Szanowni Państwo,"

    def _default_recipient(self, case: Case) -> list[str]:
        authority = self._party_by_role(case, "authority")
        if authority is None:
            return []
        lines = [authority.name]
        addr = authority.metadata.get("address")
        if isinstance(addr, str) and addr.strip():
            lines.append(addr)
        elif isinstance(addr, list):
            lines.extend(str(x) for x in addr)
        return lines

    @staticmethod
    def _party_by_role(case: Case, role: str) -> Party | None:
        for party in case.parties:
            if party.role == role:
                return party
        return None