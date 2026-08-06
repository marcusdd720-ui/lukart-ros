"""
ReviewAgent (v1) – checklist review of a generated dossier text.
No LLM. Deterministic rules for LukArt pleadings.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@dataclass(slots=True)
class Finding:
    severity: str  # ERROR | WARNING | INFO
    code: str
    message: str


def _normalize_sig(value: str) -> str:
    """Lowercase, unify separators for signature comparison."""
    text = (value or "").lower().strip()
    text = text.replace("—", "-").replace("–", "-")
    text = re.sub(r"[_\s./\\]+", "", text)
    return text


def _signature_found(text: str, signature_hint: str) -> bool:
    if not signature_hint.strip():
        return False
    raw = text.lower()
    hint = signature_hint.strip()
    if hint.lower() in raw:
        return True
    # compact form: "II Kp 459/26" vs "II_Kp_459_26" vs "II.Kp.459.26"
    norm_body = _normalize_sig(text)
    norm_hint = _normalize_sig(hint)
    if norm_hint and norm_hint in norm_body:
        return True
    # last segment often unique: 459/26
    parts = re.findall(r"\d+", hint)
    if len(parts) >= 2:
        tail = f"{parts[-2]}/{parts[-1]}"
        if tail in text:
            return True
        if f"{parts[-2]}{parts[-1]}" in norm_body:
            return True
    return False


def review_text(text: str, *, signature_hint: str = "DS.3960") -> list[Finding]:
    findings: list[Finding] = []
    t = text or ""
    low = t.lower()

    def need(code: str, ok: bool, msg: str, severity: str = "ERROR") -> None:
        if not ok:
            findings.append(Finding(severity=severity, code=code, message=msg))

    need("HDR001", "stanowisko" in low or "STANOWISKO" in t, "Brak nagłówka stanowiska.")
    need(
        "SIG001",
        _signature_found(t, signature_hint),
        f"Brak sygnatury ({signature_hint}).",
    )
    need("SEC001", "I." in t or "I " in t, "Brak sekcji numerowanych (I.).", "WARNING")
    need("SEC006", "VI" in t and "PODSTAWA" in t.upper(), "Brak sekcji VI Podstawa prawna.")
    need(
        "SEC006A",
        "VI.A" in t or "ORZECZNICTWO" in t.upper(),
        "Brak sekcji orzecznictwa (VI.A / ORZECZNICTWO).",
        "WARNING",
    )
    need(
        "SN001",
        "KK" in t or "KZP" in t or "Sąd Najwyższy" in t or "SN " in t,
        "Brak odniesienia do orzecznictwa SN.",
        "WARNING",
    )
    need("ART001", "art." in low or "§" in t, "Brak odesłania do artykułu ustawy.")
    need(
        "OUT001",
        "WNIOSEK" in t.upper() or "wnoszę" in low or "wnosze" in low,
        "Brak wniosków / prośby procesowej.",
    )
    need(
        "ATT001",
        "ZAŁĄCZNIK" in t.upper() or "Załącznik" in t,
        "Brak wykazu załączników.",
        "WARNING",
    )
    need("LEN001", len(t) >= 800, "Tekst bardzo krótki jak na dossier analityczne.", "WARNING")

    if "na oko" in low or "wydaje się że" in low:
        findings.append(
            Finding("WARNING", "STY001", "Sformułowania spekulatywne („na oko” / „wydaje się”).")
        )
    if "oskarżam" in low:
        findings.append(
            Finding("ERROR", "STY002", "Ton oskarżycielski — unikaj w stanowisku obronnym.")
        )

    return findings


def format_report(findings: list[Finding]) -> str:
    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARNING"]
    infos = [f for f in findings if f.severity == "INFO"]

    lines = [
        "ReviewAgent report",
        f"ERRORS:   {len(errors)}",
        f"WARNINGS: {len(warnings)}",
        f"INFO:     {len(infos)}",
        "",
    ]
    for label, group in (("ERRORS", errors), ("WARNINGS", warnings), ("INFO", infos)):
        if not group:
            continue
        lines.append(label)
        for f in group:
            lines.append(f"  [{f.code}] {f.message}")
        lines.append("")

    if not findings:
        lines.append("PASS – no checklist issues.")
    elif not errors:
        lines.append("RESULT: PASS WITH WARNINGS")
    else:
        lines.append("RESULT: FAIL")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Review a dossier/letter text file")
    parser.add_argument(
        "path",
        nargs="?",
        default="output/cases/DS_3960_2025/stanowisko_dossier_with_authorities.txt",
        help="Path to generated dossier text",
    )
    parser.add_argument(
        "--signature",
        default="DS.3960",
        help="Expected signature fragment (flexible match)",
    )
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        return 2

    text = path.read_text(encoding="utf-8")
    findings = review_text(text, signature_hint=args.signature)
    print(format_report(findings))
    return 1 if any(f.severity == "ERROR" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())