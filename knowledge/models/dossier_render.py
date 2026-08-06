"""
Knowledge Operating System (KOS)

File: knowledge/models/dossier_render.py
Version: 1.3.0
Sprint: CASE-012

Analytical dossier renderer (not a short letter).
Optional authorities_text from AuthoritySection (graph) is injected in section VI.
LegalIssues + Arguments rendered from domain model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from knowledge.models.case import Case, Decision


@dataclass(slots=True)
class DossierContext:
    author_name: str = ""
    place: str = ""
    dossier_date: date | None = None
    recipient_lines: list[str] | None = None
    subject: str = ""
    # Plain text from AuthoritySection.to_plain_text() — optional
    authorities_text: str | None = None


class DossierRenderer:
    """
    Render a full analytical dossier from Case.

    Sections:
      I    Metodyka
      II   Przedmiot
      II.A Zagadnienia prawne (LegalIssue)
      II.B Argumenty (Argument)
      III  Stan faktyczny
      IV   Chronologia
      V    Analiza materiału dowodowego
      VI   Podstawa prawna (+ optional graph authorities)
      VII  Ocena łączna / stanowisko
      VIII Wnioski dowodowe
      IX   Wnioski końcowe
      X    Załączniki
    """

    def render(
        self,
        case: Case,
        *,
        decision: Decision | None = None,
        context: DossierContext | None = None,
    ) -> str:
        ctx = context or DossierContext()
        dec = decision or case.latest_decision()
        if dec is None:
            raise ValueError("Case has no decision to render dossier.")

        fact_map = {f.id: f for f in case.facts}
        law_map = {b.id: b for b in case.legal_bases}
        issue_map = {i.id: i for i in case.legal_issues}
        lines: list[str] = []

        lines.append("STANOWISKO PROCESOWE")
        lines.append("WRAZ Z ANALIZĄ MATERIAŁU DOWODOWEGO")
        lines.append("")
        if case.has_signature():
            lines.append(f"Sygnatura: {case.signature.strip()}")
        else:
            lines.append(f"Sprawa: {case.display_title()}")
        pros = str(case.metadata.get("prosecutor_ref", "") or "").strip()
        if pros and pros != (case.signature or "").strip():
            lines.append(f"Sygn. prokuratorska: {pros}")
        lines.append(f"Tytuł: {case.display_title()}")
        lines.append("")
        if ctx.recipient_lines:
            lines.extend(ctx.recipient_lines)
            lines.append("")
        place_date = self._place_date(ctx)
        if place_date:
            lines.append(place_date)
            lines.append("")
        if ctx.author_name:
            lines.append(f"Składający: {ctx.author_name}")
            lines.append("")
        subject = ctx.subject or case.display_title()
        lines.append(f"Dotyczy: {subject}")
        lines.append("")
        lines.append("=" * 72)
        lines.append("")

        lines.append("I. METODYKA OPRACOWANIA")
        lines.append("")
        lines.append(
            "Niniejsze stanowisko zostało opracowane na podstawie dokumentów "
            "pozostających w dyspozycji składającego. Rozdzielono okoliczności "
            "wynikające bezpośrednio z dokumentów od ocen prawnych i wniosków. "
            "Okoliczności oparte wyłącznie na oświadczeniu strony oznaczono wprost. "
            "Nie formułuje się twierdzeń wykraczających poza materiał źródłowy."
        )
        lines.append("")

        lines.append("II. PRZEDMIOT STANOWISKA")
        lines.append("")
        if dec.scope_not_challenged:
            lines.append("Nie jest kwestionowane:")
            for i, item in enumerate(dec.scope_not_challenged, start=1):
                lines.append(f"{i}. {item}")
            lines.append("")
        if dec.issues:
            lines.append("Przedmiotem analizy jest:")
            for i, item in enumerate(dec.issues, start=1):
                lines.append(f"{i}. {item}")
            lines.append("")
        if not dec.scope_not_challenged and not dec.issues:
            lines.append(dec.summary)
            lines.append("")

        # ----- II.A LegalIssues (CASE-011) -----
        if case.legal_issues:
            lines.append("II.A. ZAGADNIENIA PRAWNE")
            lines.append("")
            for i, issue in enumerate(case.legal_issues, start=1):
                lines.append(f"{i}. {issue.question}")
                if issue.hypothesis.strip():
                    lines.append(f"   Hipoteza robocza: {issue.hypothesis.strip()}")
                if issue.statute_refs:
                    lines.append(
                        f"   Przepisy: {', '.join(issue.statute_refs)}"
                    )
                if issue.case_law_refs:
                    lines.append(
                        f"   Orzecznictwo: {', '.join(issue.case_law_refs)}"
                    )
                linked_facts = [
                    fact_map[fid].statement[:100]
                    for fid in issue.fact_ids
                    if fid in fact_map
                ]
                if linked_facts:
                    lines.append("   Powiązane fakty:")
                    for fs in linked_facts:
                        lines.append(f"   - {fs}...")
                lines.append("")

        # ----- II.B Arguments (CASE-012) -----
        if case.arguments:
            lines.append("II.B. ARGUMENTY")
            lines.append("")
            for i, arg in enumerate(case.arguments, start=1):
                lines.append(f"{i}. {arg.claim}")
                lines.append(f"   Status: {arg.status.name}")
                issue = issue_map.get(arg.issue_id)
                if issue is not None:
                    lines.append(f"   Zagadnienie: {issue.question[:120]}")
                if arg.legal_basis_ids:
                    refs = [
                        law_map[bid].reference
                        for bid in arg.legal_basis_ids
                        if bid in law_map
                    ]
                    if refs:
                        lines.append(f"   Podstawa: {', '.join(refs)}")
                lines.append("")

        lines.append("III. STAN FAKTYCZNY")
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
                    f" [źródła: {', '.join(fact.source_refs)}]"
                    if fact.source_refs
                    else ""
                )
                kind = ""
                if fact.metadata.get("kind") == "party_statement":
                    kind = " [oświadczenie strony]"
                lines.append(f"{i}. {fact.statement}{sources}{kind}")
        lines.append("")
        lines.append("Wniosek z rozdziału III")
        lines.append(
            "Zgromadzone ustalenia opierają się na dokumentach i oznaczonych "
            "oświadczeniach strony. Stanowią one punkt wyjścia do oceny zamiaru "
            "i przebiegu zdarzeń, a nie ostateczne rozstrzygnięcie sprawy."
        )
        lines.append("")

        lines.append("IV. CHRONOLOGIA ZDARZEŃ")
        lines.append("")
        if not case.timeline:
            lines.append("(brak wpisów chronologii)")
        else:
            lines.append("Data | Zdarzenie | Źródło | Znaczenie procesowe")
            lines.append("-" * 72)
            for ev in case.ordered_timeline():
                lines.append(
                    f"{ev.date_label} | {ev.event} | {ev.source} | {ev.procedural_meaning}"
                )
        lines.append("")
        lines.append("Wniosek z rozdziału IV")
        lines.append(
            "Kolejność zdarzeń pozwala ocenić, które czynności poprzedzały spór, "
            "a które go ujawniły. Chronologia nie rozstrzyga odpowiedzialności, "
            "ale porządkuje materiał do oceny zamiaru i przebiegu zdarzeń."
        )
        lines.append("")

        lines.append("V. ANALIZA MATERIAŁU DOWODOWEGO")
        lines.append("")
        if not case.evidence:
            lines.append("(brak pozycji evidence)")
        else:
            for i, item in enumerate(case.evidence, start=1):
                lines.append(f"{i}. {item.label}")
                lines.append(f"   Źródło: {item.source_ref}")
                lines.append(f"   Waga: {item.weight.name}")
                if item.proves:
                    lines.append("   Potwierdza:")
                    for p in item.proves:
                        lines.append(f"   - {p}")
                if item.does_not:
                    lines.append("   Nie potwierdza:")
                    for p in item.does_not:
                        lines.append(f"   - {p}")
                if item.open_questions:
                    lines.append("   Pytania otwarte:")
                    for q in item.open_questions:
                        lines.append(f"   - {q}")
                lines.append("")
        lines.append("Wniosek z rozdziału V")
        lines.append(
            "Poszczególne dokumenty mają różną wartość i zakres. Żaden z nich "
            "nie powinien być oceniany w izolacji od pozostałych. Dla prawidłowej "
            "oceny niezbędny jest całokształt materiału."
        )
        lines.append("")

        lines.append("VI. PODSTAWA PRAWNA")
        lines.append("")
        if not dec.legal_basis_ids:
            lines.append("(brak podstawy prawnej w modelu Case)")
        else:
            for i, lid in enumerate(dec.legal_basis_ids, start=1):
                basis = law_map.get(lid)
                if basis is None:
                    lines.append(f"{i}. [brak podstawy id={lid}]")
                    continue
                note = f" — {basis.note}" if basis.note else ""
                lines.append(f"{i}. {basis.reference}{note}")
        lines.append("")

        # Optional block from Knowledge Graph (AuthoritySection)
        if ctx.authorities_text and ctx.authorities_text.strip():
            lines.append("VI.A. ORZECZNICTWO I TEZY (Knowledge Graph)")
            lines.append("")
            for block_line in ctx.authorities_text.strip().splitlines():
                if block_line.strip() == "PODSTAWA PRAWNA I ORZECZNICTWO":
                    continue
                lines.append(block_line)
            lines.append("")

        lines.append("VII. OCENA ŁĄCZNA I STANOWISKO")
        lines.append("")
        lines.append(dec.summary)
        lines.append("")
        if dec.assessment_points:
            for i, point in enumerate(dec.assessment_points, start=1):
                lines.append(f"{i}. {point}")
            lines.append("")

        lines.append("VIII. WNIOSKI DOWODOWE")
        lines.append("")
        lines.append(
            "Na podstawie art. 167 k.p.k. wnoszę o uwzględnienie w ocenie sprawy "
            "następujących dokumentów i okoliczności:"
        )
        lines.append("")
        if case.evidence:
            for i, item in enumerate(case.evidence, start=1):
                lines.append(f"{i}. {item.label} ({item.source_ref})")
        else:
            for i, name in enumerate(dec.attachments, start=1):
                lines.append(f"{i}. {name}")
        lines.append("")
        lines.append(
            "Dowody te powinny służyć ustaleniu kolejności zdarzeń, podstaw "
            "działań dotyczących pojazdu, momentu powstania sporu oraz tego, "
            "czy czynności były podejmowane w przekonaniu o prawie do dysponowania pojazdem."
        )
        lines.append("")

        lines.append("IX. WNIOSKI KOŃCOWE")
        lines.append("")
        if not dec.outcomes:
            lines.append("1. Przyjęcie niniejszego stanowiska do akt.")
        else:
            for i, item in enumerate(dec.outcomes, start=1):
                lines.append(f"{i}. {item}")
        lines.append("")
        if dec.closing_statement.strip():
            lines.append(dec.closing_statement.strip())
            lines.append("")

        lines.append("X. ZAŁĄCZNIKI")
        lines.append("")
        if not dec.attachments:
            lines.append("(brak wykazu)")
        else:
            for i, name in enumerate(dec.attachments, start=1):
                lines.append(f"{i}. {name}")
        lines.append("")

        if ctx.author_name:
            lines.append("Z poważaniem")
            lines.append("")
            lines.append(ctx.author_name)

        return "\n".join(lines).rstrip() + "\n"

    def _place_date(self, ctx: DossierContext) -> str:
        d = ctx.dossier_date or datetime.now(UTC).date()
        place = ctx.place.strip()
        formatted = d.strftime("%d.%m.%Y")
        if place:
            return f"{place}, dnia {formatted} r."
        return f"dnia {formatted} r."