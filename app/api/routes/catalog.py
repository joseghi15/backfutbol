from fastapi import APIRouter

router = APIRouter(tags=["catalog"])

CATALOG = {
    "tournamentFormats": [
        {"key": "liga", "label": "Liga", "subtitle": "Todos contra todos"},
        {"key": "copa", "label": "Copa", "subtitle": "Eliminación directa"},
    ],
    "teamCounts": [8, 12, 16, 24],
    "gameModalities": ["Fútbol 5", "Fútbol 7", "Fútbol 11"],
    "pitchSurfaces": ["Sintético", "Asfalto"],
    "matchDurations": ["2 × 25 min", "2 × 20 min", "2 × 30 min"],
    "venues": ["El Templo FC", "La Bombonerita 5", "Complejo Norte"],
    "playerPositions": [
        "Arquero",
        "Defensor",
        "Mediocampista",
        "Delantero",
    ],
    "goalTypes": [
        "Jugada colectiva",
        "Tiro libre",
        "Penal",
        "Cabeza",
    ],
    "cardStyles": [
        {"key": "neon", "label": "Neón", "dotColor": "#4EDEA3"},
        {"key": "gold", "label": "Gold", "dotColor": "#F2B24C"},
        {"key": "black", "label": "Black", "dotColor": "#94A3B8"},
        {"key": "cyber", "label": "Cyber", "dotColor": "#7BD0FF"},
    ],
}


@router.get("/catalog")
def read_catalog() -> dict:
    return CATALOG
