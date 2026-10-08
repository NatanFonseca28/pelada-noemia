"""Campeonatos do football-data.org e ajustes de nome/sigla/cor dos clubes (regra pura).

Os nomes vêm do `shortName` da API; os ajustes abaixo corrigem apelidos estranhos ("Mineiro"), traduzem
seleções para o português e desfazem siglas repetidas no mesmo campeonato (Corinthians e Coritiba = COR).
"""

# (código da API, nome exibido) — a ordem é a do dropdown do sorteio
COMPETITIONS: list[tuple[str, str]] = [
    ("BSA", "Brasileirão Série A"),
    ("CL", "Champions League"),
    ("WC", "Copa do Mundo"),
    ("EC", "Eurocopa"),
    ("PL", "Premier League"),
    ("PD", "La Liga"),
    ("SA", "Serie A (Itália)"),
    ("BL1", "Bundesliga"),
    ("FL1", "Ligue 1"),
    ("PPL", "Primeira Liga (Portugal)"),
    ("DED", "Eredivisie"),
    ("ELC", "Championship (Inglaterra)"),
]
NATIONAL = {"WC", "EC"}

# shortName da API → nome exibido
CLUB_NAMES: dict[str, str] = {
    # Brasil
    "Mineiro": "Atlético-MG",
    "Paranaense": "Athletico-PR",
    "Clube do Remo": "Remo",
    "Bragantino": "RB Bragantino",
    "Vasco da Gama": "Vasco",
    # Europa
    "Atleti": "Atlético de Madrid",
    "Barça": "Barcelona",
    "Athletic": "Athletic Bilbao",
    "Sevilla FC": "Sevilla",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Brighton Hove": "Brighton",
    "Nottingham": "Nottingham Forest",
    "Inter": "Inter de Milão",
    "Venezia FC": "Venezia",
    "Como 1907": "Como",
    "Bayern": "Bayern de Munique",
    "HSV": "Hamburgo",
    "M'gladbach": "Gladbach",
    "1. FC Köln": "Colônia",
    "Olympique Lyon": "Lyon",
    "SL Benfica": "Benfica",
    "Sporting CP": "Sporting",
    "Shaktar": "Shakhtar Donetsk",
    "PAE AEK": "AEK Atenas",
    "Sl. Bratislava": "Slovan Bratislava",
    "Slavia Praha": "Slavia Praga",
}

# nome exibido → sigla (quando a da API repete ou não é a conhecida no Brasil)
CLUB_TLAS: dict[str, str] = {
    "Coritiba": "CFC",
    "São Paulo": "SAO",
    "Grêmio": "GRE",
    "Internacional": "INT",
    "Barcelona": "BAR",
    "Bayern de Munique": "BAY",
}

# Seleções (Copa do Mundo e Eurocopa) em português, pela sigla FIFA
NATIONS: dict[str, str] = {
    "ALB": "Albânia", "ALG": "Argélia", "ARG": "Argentina", "AUS": "Austrália", "AUT": "Áustria",
    "BEL": "Bélgica", "BIH": "Bósnia", "BRA": "Brasil", "CAN": "Canadá", "CIV": "Costa do Marfim",
    "COD": "RD Congo", "COL": "Colômbia", "CPV": "Cabo Verde", "CRO": "Croácia", "CUW": "Curaçao",
    "CZE": "Tchéquia", "DEN": "Dinamarca", "ECU": "Equador", "EGY": "Egito", "ENG": "Inglaterra",
    "ESP": "Espanha", "FRA": "França", "GEO": "Geórgia", "GER": "Alemanha", "GHA": "Gana",
    "HAI": "Haiti", "HUN": "Hungria", "IRN": "Irã", "IRQ": "Iraque", "ITA": "Itália",
    "JOR": "Jordânia", "JPN": "Japão", "KOR": "Coreia do Sul", "KSA": "Arábia Saudita", "MAR": "Marrocos",
    "MEX": "México", "NED": "Holanda", "NOR": "Noruega", "NZL": "Nova Zelândia", "PAN": "Panamá",
    "PAR": "Paraguai", "POL": "Polônia", "POR": "Portugal", "QAT": "Catar", "ROU": "Romênia",
    "RSA": "África do Sul", "SCO": "Escócia", "SEN": "Senegal", "SRB": "Sérvia", "SUI": "Suíça",
    "SVK": "Eslováquia", "SVN": "Eslovênia", "SWE": "Suécia", "TUN": "Tunísia", "TUR": "Turquia",
    "UKR": "Ucrânia", "URU": "Uruguai", "USA": "Estados Unidos", "UZB": "Uzbequistão", "WAL": "País de Gales",
    "CHI": "Chile", "PER": "Peru", "BOL": "Bolívia", "VEN": "Venezuela", "CRC": "Costa Rica",
    "NGA": "Nigéria", "CMR": "Camarões", "IRL": "Irlanda", "ISL": "Islândia", "FIN": "Finlândia",
}

COLORS: dict[str, str] = {
    "black": "#1f2937", "blue": "#2f6fdb", "brown": "#7c4a2d", "claret": "#7b1e3a", "crimson": "#c0183c",
    "dark blue": "#1e3a8a", "gold": "#d4a017", "green": "#1f9d55", "light blue": "#5aa9e6",
    "maroon": "#7a1f2b", "navy blue": "#1e2a5a", "orange": "#ea580c", "purple": "#6d28d9", "red": "#e0443a",
    "royal blue": "#1d4ed8", "sky blue": "#56b4e9", "violet": "#7c3aed", "white": "#e5e7eb", "yellow": "#f4c20d",
    "grey": "#6b7280", "gray": "#6b7280", "silver": "#9ca3af", "amber": "#f59e0b", "pink": "#ec4899",
}
FALLBACK_COLOR = "#5d6b5f"


def club_color(club_colors: str | None) -> str:
    """Primeira cor de "Red / Black"; pula o branco para o escudo gerado e as tarjas não ficarem brancos."""
    names = [c.strip().lower() for c in (club_colors or "").split("/") if c.strip()]
    known = [COLORS[n] for n in names if n in COLORS]
    non_white = [c for n, c in zip([n for n in names if n in COLORS], known, strict=True) if n != "white"]
    return (non_white or known or [FALLBACK_COLOR])[0]


def club_name(code: str, team: dict) -> str:
    short = (team.get("shortName") or team.get("name") or "").strip()
    if code in NATIONAL:
        return NATIONS.get((team.get("tla") or "").upper(), short)
    return CLUB_NAMES.get(short, short)


def club_tla(name: str, tla: str) -> str:
    return CLUB_TLAS.get(name, tla.upper())[:5]
