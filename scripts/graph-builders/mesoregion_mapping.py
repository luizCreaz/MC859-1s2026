from __future__ import annotations

import re
import subprocess
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PDF_PATH = ROOT / "data" / "bronze" / "ibge" / "meso-regioes" / "meso-micro-regioes-mg.pdf"
MAPPING_CSV_PATH = ROOT / "data" / "silver" / "mesoregion_municipalities.csv"

MESOREGION_LABELS = {
    "noroeste_de_minas": "Noroeste de Minas",
    "norte_de_minas": "Norte de Minas",
    "jequitinhonha": "Jequitinhonha",
    "vale_do_mucuri": "Vale do Mucuri",
    "triangulo_mineiro_alto_paranaiba": "Triângulo Mineiro / Alto Paranaíba",
    "central_mineira": "Central Mineira",
    "metropolitana_belo_horizonte": "Metropolitana de Belo Horizonte",
    "vale_do_rio_doce": "Vale do Rio Doce",
    "oeste_de_minas": "Oeste de Minas",
    "sul_sudoeste_de_minas": "Sul / Sudoeste de Minas",
    "campo_das_vertentes": "Campo das Vertentes",
    "zona_da_mata": "Zona da Mata",
}

PDF_MESOREGION_NAMES = {v: k for k, v in MESOREGION_LABELS.items()}

MANUAL_NODE_MESOREGION = {
    "Capitão Enéas": "norte_de_minas",
    "Dona Euzébia": "zona_da_mata",
    "Itabirinha": "vale_do_rio_doce",
    "Itamogi": "sul_sudoeste_de_minas",
    "Jequitinhonha": "jequitinhonha",
    "Monjolos": "central_mineira",
    "Passabém": "metropolitana_belo_horizonte",
    "Tiradentes": "campo_das_vertentes",
}


def _normalize(value: str) -> str:
    ascii_text = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode()
    )
    ascii_text = ascii_text.replace("-", " ").replace("'", " ")
    return re.sub(r"\s+", " ", ascii_text.lower().strip())


NAME_ALIASES = {
    _normalize("Amparo do Serra"): _normalize("Amparo da Serra"),
    _normalize("Barão de Monte Alto"): _normalize("Barão do Monte Alto"),
    _normalize("Brazópolis"): _normalize("Brasópolis"),
    _normalize("Dona Euzébia"): _normalize("Dona Eusébia"),
    _normalize("Estrela Dalva"): _normalize("Estrela d Alva"),
    _normalize("Itapagipe"): _normalize("Itapajipe"),
    _normalize("Jaboticatubas"): _normalize("Jabuticatubas"),
    _normalize("Machacalis"): _normalize("Maxacalis"),
    _normalize("Mathias Lobato"): _normalize("Matias Lobato"),
    _normalize("Piumhi"): _normalize("Pium i"),
    _normalize("Santa Rita de Jacutinga"): _normalize("Santa Rita do Jacutinga"),
    _normalize("Santa Rita de Ibitipoca"): _normalize("Santa Rita do Ibitipoca"),
    _normalize("São João Del-Rei"): _normalize("São João del Rei"),
    _normalize("Wenceslau Braz"): _normalize("Venceslau Brás"),
}


def _pdf_lookup_key(municipality_name: str) -> str:
    normalized = _normalize(municipality_name)
    return NAME_ALIASES.get(normalized, normalized)


def _extract_pdf_text() -> str:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Mesoregion PDF not found: {PDF_PATH}")
    return subprocess.check_output(["pdftotext", str(PDF_PATH), "-"], text=True)


def _parse_pdf_mapping() -> dict[str, str]:
    text = _extract_pdf_text()
    lines = [line.strip() for line in text.splitlines()]

    micro_names: set[str] = set()
    for index, line in enumerate(lines):
        if re.fullmatch(r"\d{1,2}", line) and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if (
                next_line
                and next_line not in PDF_MESOREGION_NAMES
                and not re.fullmatch(r"\d{1,2}", next_line)
            ):
                micro_names.add(next_line)

    skip_pattern = re.compile(
        r"^(ESTADO DE|MESO E|Código da|Mesorregião|Microrregião|Município|"
        r"Site Minas|Página|\f|\s*$|Alto Paranaíba|Dona Eusébia|Passabém)$",
        re.I,
    )

    def is_municipality_line(line: str) -> bool:
        if not line or skip_pattern.match(line) or re.fullmatch(r"\d{1,2}", line):
            return False
        if line in PDF_MESOREGION_NAMES or line in micro_names:
            return False
        return bool(re.search(r"[A-Za-zÀ-ú]", line))

    mapping: dict[str, str] = {}
    pending: list[str] = []
    current_meso: str | None = None

    for line in lines:
        if line in PDF_MESOREGION_NAMES:
            current_meso = PDF_MESOREGION_NAMES[line]
            mapping[_normalize(line)] = current_meso
            for municipality in pending:
                mapping[_normalize(municipality)] = current_meso
            pending = []
            continue

        if not is_municipality_line(line):
            continue

        if current_meso:
            mapping[_normalize(line)] = current_meso
        else:
            pending.append(line)

    return mapping


def get_municipality_mesoregion_map(node_names: list[str]) -> dict[str, str]:
    pdf_mapping = _parse_pdf_mapping()
    node_mapping: dict[str, str] = {}

    for node_name in node_names:
        if node_name in MANUAL_NODE_MESOREGION:
            node_mapping[node_name] = MANUAL_NODE_MESOREGION[node_name]
            continue

        lookup_key = _pdf_lookup_key(node_name)
        if lookup_key in pdf_mapping:
            node_mapping[node_name] = pdf_mapping[lookup_key]

    missing = sorted(set(node_names) - set(node_mapping))
    if missing:
        raise ValueError(
            "Could not assign mesoregion to municipalities: "
            + ", ".join(missing)
        )

    return node_mapping


def get_mesoregion_groups(node_names: list[str]) -> dict[str, list[str]]:
    node_mapping = get_municipality_mesoregion_map(node_names)
    groups: dict[str, list[str]] = {slug: [] for slug in MESOREGION_LABELS}
    for node_name, meso_slug in node_mapping.items():
        groups[meso_slug].append(node_name)
    return {slug: sorted(nodes) for slug, nodes in groups.items() if nodes}


def save_mapping_csv(node_names: list[str], output_path: Path | None = None) -> Path:
    import csv

    if output_path is None:
        output_path = MAPPING_CSV_PATH

    node_mapping = get_municipality_mesoregion_map(node_names)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["municipality", "mesoregion_slug", "mesoregion_label"])
        for municipality in sorted(node_mapping):
            slug = node_mapping[municipality]
            writer.writerow([municipality, slug, MESOREGION_LABELS[slug]])

    return output_path
