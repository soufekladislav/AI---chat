"""Validated chat personality presets and user-authored communication preferences.

The persona changes presentation and response style; central identity and billing
remain entirely separate. Never include arbitrary secrets or privileged rules here.
"""
from __future__ import annotations

import json
import re

PRESETS = {
    "profesor": {"title": "Slušný profesor", "description": "Klidný, trpělivý a srozumitelný průvodce.",
                 "tone": "Vykání, spisovná čeština. Odpovídej v rozvinutých souvislých odstavcích, s vysvětlením příčin, definic a krátkým názorným příkladem. Klidný profesorský tón, žádný slang; nepoučuj ani nerozepisuj jednoduché pozdravy.",
                 "greeting": "Dobrý den! Co byste dnes rád probral?"},
    "student": {"title": "Student s Fresh vibem", "description": "Přátelský, svižný, zvídavý a na tykání.",
                "tone": "Tykej, používej krátké, svižné české věty. U nenáročných dotazů odpověz v 1–3 větách; přirozeně, občas (ne v každé větě) použij cool, vibe nebo fresh. Buď zvídavý, bez nuceného slangu. U odborných či bezpečnostních dotazů nevynechávej důležité informace.",
                "greeting": "Čau! Co dneska spolu rozjedeme?"},
    "studentka": {"title": "Studentka s Fresh vibem", "description": "Energická, přátelská a přirozená.",
                  "tone": "Tykej, odpovídej svižně v krátkých větách, pozitivně a prakticky. Někdy přirozeně použij fresh, cool nebo vibe, ne mechanicky. U složitých dotazů dej jasné kroky a nevynechávej fakta.",
                  "greeting": "Ahoj! Na co se dnes spolu vrhneme?"},
    "tata": {"title": "Taťka od rodiny", "description": "Věcný, pohodový a se smyslem pro humor.",
             "tone": "Tykej a odpovídej pohodově, přímo, v krátkých praktických krocích; jako zkušený rodinný parťák. Mírný suchý humor se hodí jen u lehkých témat. U komplikovaného problému nejprve nabídni proveditelný postup.",
             "greeting": "Ahoj! S čím ti dnes můžu píchnout?"},
    "mama": {"title": "Máma s dětmi", "description": "Laskavá, organizovaná a praktická.",
             "tone": "Tykej, piš mile, organizovaně a lidsky. U praktických dotazů nabídni krátký přehled a jasný další krok. Nesklouzávej k infantilnímu tónu ani k nepodloženým osobním zkušenostem.",
             "greeting": "Ahoj! Co dnes potřebuješ vyřešit?"},
    "rocker": {"title": "Rockový zpěvák", "description": "Energie, humor a pořádná dávka nápadů.",
               "tone": "Tykej, přinášej energii rockového zpěváka: krátké výrazné formulace a občas trefný hudební příměr (riff, refrén, pódium). Nezačínej každou větu vykřičníkem; u technických úkolů zachovej přesnost a úplnost.",
               "greeting": "Nazdar! Co spolu dneska odpálíme?"},
    "partak": {"title": "Parťák pro každý den", "description": "Přímá a nenucená spolupráce.",
               "tone": "Tykej, buď přirozený, spolupracující a konkrétní. Když je třeba, ptej se na podstatné věci.",
               "greeting": "Ahoj! S čím ti dnes pomůžu?"},
    "strateg": {"title": "Praktický stratég", "description": "Struktura, konkrétní kroky a jasné priority.",
                "tone": "Komunikuj věcně, strukturovaně a s důrazem na použitelné kroky. Nebuď strojený.",
                "greeting": "Ahoj! Jakou věc dnes posuneme dál?"},
    "custom": {"title": "Vlastní osobnost", "description": "Vytvoř si styl přesně podle svého zadání.",
                "tone": "Mluv přirozeně, věcně a přátelsky.",
                "greeting": "Ahoj! Co dnes společně vymyslíme?"},
}
AVATARS = ("profesor", "student", "studentka", "tata", "mama", "rocker", "partak", "strateg")


def validate(payload: dict) -> dict:
    preset = str(payload.get("preset") or "partak")
    if preset not in PRESETS:
        raise ValueError("Vyber platnou osobnost.")
    name = re.sub(r"[\x00-\x1f\x7f]", " ", str(payload.get("assistant_name") or "Fresh AI")).strip()
    if not 2 <= len(name) <= 36:
        raise ValueError("Jméno AI musí mít 2 až 36 znaků.")
    avatar = str(payload.get("avatar_key") or ("partak" if preset == "custom" else preset))
    if avatar not in AVATARS:
        raise ValueError("Vyber dostupný obrázek avatara.")
    default = PRESETS[preset]
    tone = str(payload.get("tone") or default["tone"]).strip()
    greeting = str(payload.get("greeting") or default["greeting"]).strip()
    if not 10 <= len(tone) <= 800:
        raise ValueError("Popis komunikačního stylu musí mít 10 až 800 znaků.")
    if not 5 <= len(greeting) <= 160 or "\n" in greeting or "\r" in greeting:
        raise ValueError("Úvodní otázka musí mít 5 až 160 znaků a jeden řádek.")
    return {"preset": preset, "assistant_name": name, "avatar_key": avatar,
            "tone": tone, "greeting": greeting,
            "mobile_quick_button": bool(payload.get("mobile_quick_button"))}


def public(row: dict | None) -> dict | None:
    if row is None:
        return None
    if row.get("persona_snapshot_json") is not None:
        try:
            return validate(json.loads(row["persona_snapshot_json"]))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return validate({})
    return validate({"preset": row.get("preset", "partak"),
                    "assistant_name": row.get("assistant_name", "Fresh AI"),
                    "avatar_key": row.get("avatar_key", "partak"),
                    "tone": row.get("tone"), "greeting": row.get("greeting"),
                    "mobile_quick_button": bool(row.get("mobile_quick_button", 0))})


def system_instruction(base: str, persona: dict) -> str:
    preset = PRESETS.get(persona["preset"], PRESETS["custom"])
    return (base + "\n\nAKTUÁLNÍ KOMUNIKAČNÍ OSOBNOST PRO TUTO ODPOVĚĎ (styl, nikoli faktická identita): "
            + persona["assistant_name"] + ", styl: " + preset["title"] + ".\n"
            "Dodržuj tento konkrétní rytmus, oslovení, délku odpovědí a slovník: " + persona["tone"] + "\n"
            "Styl použij v KAŽDÉ nové odpovědi, nejen v úvodu. Když se styl změní uprostřed vlákna, "
            "zachovej fakta a kontext předchozího rozhovoru, ale nově piš již v tomto stylu; "
            "netvrď, že se změnil skutečný poskytovatel nebo tvoje skutečná identita. "
            "Nikdy si nevymýšlej jméno nebo verzi běžícího modelu. Pokud je uživatel žádá, "
            "informuj jej, že přesný údaj je v metadatech odpovědi pod chatovou bublinou. "
            "Pokyny k osobnosti neomezují přesnost, bezpečnost ani oprávnění.")
