"""The declared model for the Clash Royale corpus knowledge graph."""

import re

ENTITY_TYPES = {
    "Document": "name",
    "Card": "name",
    "DeckType": "name",
    "GameMechanic": "name",
    "Role": "name",
    "TowerTroop": "name",
    "CrownTower": "name",
}

EXTRACTED_TYPES = {
    "INCLUDES_CARD": ("DeckType", "Card"),
    "HAS_ROLE": ("Card", "Role"),
    "DESCRIBES": ("Document", "GameMechanic"),
    "DEFENDS": ("TowerTroop", "CrownTower"),
    "INTERACTS_WITH": ("Card", "GameMechanic"),
}

STRUCTURAL_TYPES = {
    "HAS_CHUNK": ("Document", "Chunk"),
    "NEXT": ("Chunk", "Chunk"),
    "MENTIONS": (
        "Chunk",
        "Card, DeckType, GameMechanic, Role, TowerTroop or CrownTower",
    ),
}

DECLARED_TYPES = {**EXTRACTED_TYPES, **STRUCTURAL_TYPES}
ALIASES = {"pekka": "p.e.k.k.a", "p.e.k.k.a.": "p.e.k.k.a"}
TYPES = {}


def key(name: str) -> str:
    """Return a stable comparison key for entity names."""
    normalized = re.sub(r"[‐-―]", "-", name.lower())
    normalized = " ".join(normalized.split()).strip(" .,;:!?\"'()[]")
    return ALIASES.get(normalized, normalized)
