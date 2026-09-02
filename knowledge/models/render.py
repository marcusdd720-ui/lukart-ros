"""
Knowledge Operating System (KOS)

File: knowledge/models/render.py
Version: 2.3
Sprint: CASE-007

Render Case + Decision. Timeline + evidence analysis sections.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from knowledge.models.case import Case, Decision, Party


@dataclass(slots=True)
class LetterContext:
    sender_name: str = ""
    sender_address: str = ""
    sender_contact: str = ""
    recipient_lines: list[str] | None = None
    place: str = ""
    letter_date: date | None = None
    subject: str = ""
    prosecutor_ref: str = ""


class CaseLetterRenderer:
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
        signature = case.signature
        sig = signature.strip() if signature is not None and case.has_signature() else ""
        pros = (
            ctx.prosecutor_ref.strip()
            if ctx.prosecutor_ref and ctx.prosecutor_ref.strip()
            else str(case.metadata.get("prosecutor_ref", "") or "").strip()
        )
        if sig and pros and sig == pros:
            lines.append(f"Sygn. prokuratorska: {sig}")
        else:
            if sig:
                lines.append(f"Sygn. akt: {sig}")
            elif not pros:
                lines.append(f"Sprawa: {case.display_title()}")
            if pros and pros != sig:
                lines.append(f"Sygn. prokuratorska: {pros}")

        subject = ctx.subject or case.display_title() or dec.summary
        lines.append(f"Dotyczy: {subject}")
        lines.append("")
        lines.append("Szanowni Państwo,")
        lines.append("")

        lines.append("I. Przedmiot sprawy")
        lines.append("")
        if dec.scope_not_challenged:
            lines.append("Nie jest kwestionowane:")
            for i, scope_item in enumerate(dec.scope_not_challenged, start=1):
                lines.append(f"{i}. {scope_item}")
            lines.append("")
        if dec.issues:
            lines.append("Przedmiotem stanowiska jest:")
            for i, issue_item in enumerate(dec.issues, start=1):
                lines.append(f"{i}. {issue_item}")
            lines.append("")
        if not dec.scope_not_challenged and not dec.issues:
            lines.append(dec.summary)
            lines.append("")

        lines.append("II. Ustalenia faktyczne")
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

        if case.timeline:
            lines.append("II.A. Chronologia zdarzeń")
            lines.append("")
            lines.append("Data | Zdarzenie | Źródło | Znaczenie procesowe")
            lines.append("-" * 72)
            for ev in case.ordered_timeline():
                lines.append(
                    f"{ev.date_label} | {ev.event} | {ev.source} | {ev.procedural_meaning}"
                )
            lines.append("")

        if case.evidence:
            lines.append("II.B. Analiza materiału dowodowego")
            lines.append("")
            for i, evidence_item in enumerate(case.evidence, start=1):
                lines.append(
                    f"{i}. {evidence_item.label} (źródło: {evidence_item.source_ref})"
                )
                lines.append(f"   Waga: {evidence_item.weight.name}")
                if evidence_item.proves:
                    lines.append("   Potwierdza:")
                    for p in evidence_item.proves:
                        lines.append(f"   - {p}")
                if evidence_item.does_not:
                    lines.append("   Nie potwierdza:")
                    for p in evidence_item.does_not:
                        lines.append(f"   - {p}")
                if evidence_item.open_questions:
                    lines.append("   Pytania otwarte:")
                    for q in evidence_item.open_questions:
                        lines.append(f"   - {q}")
                lines.append("")

        lines.append("III. Podstawa prawna")
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

        lines.append("IV. Stanowisko")
        lines.append("")
        lines.append(dec.summary)
        if dec.assessment_points:
            lines.append("")
            for i, point in enumerate(dec.assessment_points, start=1):
                lines.append(f"{i}. {point}")
        lines.append("")

        lines.append("V. Wnioski")
        lines.append("")
        if not dec.outcomes:
            lines.append("1. Przyjęcie niniejszego pisma do akt.")
        else:
            for i, outcome in enumerate(dec.outcomes, start=1):
                lines.append(f"{i}. {outcome}")
        lines.append("")

        if dec.closing_statement.strip():
            lines.append(dec.closing_statement.strip())
            lines.append("")

        lines.append("Z poważaniem")
        lines.append("")
        if ctx.sender_name:
            lines.append(ctx.sender_name)
        else:
            applicant = self._party_by_role(case, "applicant")
            lines.append(applicant.name if applicant else "")

        if dec.attachments:
            lines.append("")
            lines.append("Załączniki:")
            for i, attachment in enumerate(dec.attachments, start=1):
                lines.append(f"{i}. {attachment}")

        return "\n".join(lines).rstrip() + "\n"

    def _place_date(self, ctx: LetterContext) -> str:
        d = ctx.letter_date or datetime.now(UTC).date()
        place = ctx.place.strip()
        formatted = d.strftime("%d.%m.%Y")
        if place:
            return f"{place}, dnia {formatted} r."
        return f"dnia {formatted} r."

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
