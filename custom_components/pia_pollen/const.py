DOMAIN = "pia_pollen"

BASE_URL = "https://aerobiologia.cat/api/v0/forecast/{locality}/{lang}/xml"

LOCALITIES = [
    "barcelona", "bellaterra", "girona", "lleida",
    "manresa", "roquetes", "tarragona", "vielha",
    "son", "palma",
]

LANGUAGES = ["es", "ca", "en"]
DEFAULT_LANG = "es"
SCAN_INTERVAL_HOURS = 12

# Nivel numérico → etiqueta legible
LEVEL_LABELS = {
    0: "absent",
    1: "molt baix",
    2: "baix",
    3: "moderat",
    4: "alt",
    5: "molt alt",
}

# La API puede devolver tendencia como número (-1/0/1)
# o como texto (d/e/u o down/equal/up). Cubrimos ambos.
TREND_LABELS = {
    "-1": "↓ baixant", "d": "↓ baixant", "down": "↓ baixant",
     "0": "→ estable", "e": "→ estable", "equal": "→ estable",
     "1": "↑ pujant",  "u": "↑ pujant",  "up": "↑ pujant",
}
