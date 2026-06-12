"""
Calcula a taxa de vítimas de feminicídio (tentativas + consumações) por 100.000 habitantes
em 2022 e a taxa normalizada (divisão pela maior taxa) por município de Minas Gerais.

Dados de entrada (cruzamento pelos 6 primeiros dígitos de municipio_cod):
  - data/bronze/portal-dados-abertos/mapa-violencia-mulher-mg/casos_feminicidio_mg_2022.csv
  - data/bronze/ibge/censo-2022/populacao_mg_2022.csv

Saída:
  - data/silver/taxa_feminicidio_mg_2022.csv

Uso (na raiz do repositório):
  python scripts/calculate_femicide_rate.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEMICIDE_REPORTS = (
    ROOT
    / "data"
    / "bronze"
    / "portal-dados-abertos"
    / "mapa-violencia-mulher-mg"
    / "casos_feminicidio_mg_2022.csv"
)
CITIES_POPULATION = ROOT / "data" / "bronze" / "ibge" / "censo-2022" / "populacao_mg_2022.csv"
OUTPUT_FILE = ROOT / "data" / "silver" / "taxa_feminicidio_mg_2022.csv"


def prefix6(codigo) -> str:
    """
    6 primeiros dígitos do código IBGE (malha/CSV com 6 ou 7 dígitos).
    """
    if codigo is None or str(codigo).strip() == "":
        return "000000"
    s = str(int(str(codigo).strip().replace(",", "")))
    s = s.zfill(6)
    if len(s) > 6:
        return s[:6]
    return s


def load_femicide_reports() -> dict[str, int]:
    """
    Carrega o número de feminicídios por município de Minas Gerais.

    Saída:
      - dict[str, int]: município_cod -> número de feminicídios tentados e consumados em 2022
    """
    total_femicides: dict[str, int] = defaultdict(int)
    with FEMICIDE_REPORTS.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            k = prefix6(row.get("municipio_cod", ""))
            try:
                number_of_femicides = int(row.get("qtde_vitimas", "0"))
            except ValueError:
                number_of_femicides = 0
            total_femicides[k] += number_of_femicides
    return dict(total_femicides)


def load_cities_population() -> dict[str, int]:
    """
    Carrega a população por município de Minas Gerais.

    Saída:
      - dict[str, int]: município_cod -> população em 2022
    """
    cities_population: dict[str, int] = defaultdict(int)
    with CITIES_POPULATION.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city_code = row.get("municipio_cod", "")
            if not city_code:
                continue
            try:
                population = parse_population(row.get("populacao", "0"))
            except ValueError:
                population = 0
            cities_population[city_code] = population
    return dict(cities_population)


def parse_population(val: str) -> int:
    """
    Converte o valor da população para um inteiro.
    """
    v = val.strip().replace(" ", "").replace("\u00a0", "")
    if not v:
        return 0
    if "," in v and not v.isdigit():
        v = v.replace(".", "").replace(",", "")
    return int(v)


def calculate_femicide_rate_to_all_cities() -> None:
    # Reading source files and loading data
    if not FEMICIDE_REPORTS.is_file():
        raise SystemExit(f"Arquivo inexistente: {FEMICIDE_REPORTS}")
    if not CITIES_POPULATION.is_file():
        raise SystemExit(f"Arquivo inexistente: {CITIES_POPULATION}")

    femicides = load_femicide_reports()
    cities_population = load_cities_population()

    # Calculating the rate of feminicidios per 100.000 inhabitants
    rates: list[tuple[str, int, int, float]] = []
    for city_code, population in cities_population.items():
        number_of_femicides = femicides.get(prefix6(city_code), 0)
        if population > 0:
            rate = 100000 * number_of_femicides / population
        else:
            rate = 0.0
        rates.append((city_code, number_of_femicides, population, rate))

    # Finding the maximum rate
    max_rate = max(rates, key=lambda x: x[3])[3]

    # Writing the output file
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "municipio_cod",
                "qtde_vitimas",
                "populacao",
                "taxa_feminicidio_por_100k_hab",
                "taxa_feminicidio_normalizada",
            ]
        )
        for city_code, number_of_femicides, population, rate in rates:
            if max_rate > 0:
                normalized_rate = rate / max_rate
            else:
                normalized_rate = 0.0
            w.writerow(
                [
                    f'{city_code}',
                    number_of_femicides,
                    population,
                    f"{rate:.3f}",
                    f"{normalized_rate:.3f}",
                ]
            )


def get_femicide_rate_by_city_code(city_code: str) -> float:
    """
    Retorna a taxa normalizada de feminicídio (coluna `taxa_feminicidio_normalizada`
    de OUTPUT_FILE) para o município, ou 0,0 se não houver linha correspondente.

    Gera o arquivo em disco com `calculate_femicide_rate_to_all_cities` quando
    OUTPUT_FILE ainda não existir. A comparação usa `prefix6` no código pedido
    e no `municipio_cod` lido do CSV.
    """
    if not OUTPUT_FILE.is_file():
        calculate_femicide_rate_to_all_cities()

    key = prefix6(city_code)
    with OUTPUT_FILE.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cod = (row.get("municipio_cod") or "").strip()
            if prefix6(cod) != key:
                continue
            raw = row.get("taxa_feminicidio_normalizada", "0")
            try:
                return float(str(raw).replace(",", "."))
            except ValueError:
                return 0.0
    return 0.0
