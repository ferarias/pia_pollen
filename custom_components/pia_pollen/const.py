DOMAIN = "pia_pollen"

BASE_URL = "https://aerobiologia.cat/api/v0/forecast/{locality}/{lang}/xml"

LOCALITIES = [
    "barcelona",
    "bellaterra",
    "girona",
    "lleida",
    "manresa",
    "roquetes",
    "tarragona",
    "vielha",
    "son",
    "palma",
]

LANGUAGES = ["es", "ca", "en"]
DEFAULT_LANG = "es"
SCAN_INTERVAL_HOURS = 12

# Según <legend><current> del XML real
LEVEL_LABELS = {
    0: "Nulo",
    1: "Bajo",
    2: "Medio",
    3: "Alto",
    4: "Máximo",
}

# Según <legend><forecast> del XML real
TREND_LABELS = {
    "A": "↑ Augmenta",
    "=": "→ Estable",
    "D": "↓ Descenso",
    "!": "⚠ Situación excepcional",
}
