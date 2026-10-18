# Clash Royale Knowledge Graph

The knowledge graph is based on the corpus in `corpus/cr`, including the
gameplay guide, deck strategies, tower-troop information, and card datasets.
It represents the cards, deck archetypes, game mechanics, and source evidence
in a way that supports both factual and provenance-oriented questions.

## Entity types and properties

| Entity type | Description | Properties |
|---|---|---|
| `Document` | A source file in the corpus | `name`, `path`, `format`, `description` |
| `Chunk` | A section or extract from a source document | `text`, `section`, `position` |
| `Card` | A troop, building, spell, or spawner card | `name`, `card_type`, `elixir_cost`, `count`, `damage`, `crown_tower_damage`, `damage_per_second`, `death_damage`, `health`, `hit_speed`, `range`, `level` |
| `DeckType` | A strategic deck archetype | `name`, `description`, `typical_elixir_cost`, `primary_strategy` |
| `TowerTroop` | A troop that defends a Crown Tower | `name`, `rarity`, `description`, `maximum_level`, `attack_speed`, `special_ability` |
| `GameMechanic` | A gameplay rule or concept | `name`, `category`, `description` |
| `Role` | A strategic function of a card | `name`, `description` |
| `CrownTower` | A tower belonging to a player | `name`, `tower_type`, `description` |

Card types found in the card dataset include `Troops and Defenses`,
`Spawners`, and `Damaging Spells`. Deck types described in the strategy
material include `Beatdown`, `Control`, `Bait`, `Bridge Spam`, `Siege`, and
`Cycle`. Game mechanics include `Elixir Management`, `Card Rotation`,
`Territory`, `Overtime`, `Tiebreaker`, and `Deck Construction`.

## Relationships

| Relationship | Meaning | Relationship properties |
|---|---|---|
| `(:Document)-[:HAS_CHUNK]->(:Chunk)` | A document contains a traceable passage | `section`, `position` |
| `(:Chunk)-[:MENTIONS]->(:Card)` | A passage mentions a card | `mention_text`, `confidence` |
| `(:Chunk)-[:MENTIONS]->(:DeckType)` | A passage mentions a deck archetype | `mention_text`, `confidence` |
| `(:Chunk)-[:MENTIONS]->(:GameMechanic)` | A passage mentions a mechanic | `mention_text`, `confidence` |
| `(:DeckType)-[:INCLUDES_CARD]->(:Card)` | An archetype contains or recommends a card | `role`, `evidence`, `confidence` |
| `(:Card)-[:HAS_ROLE]->(:Role)` | A card has a strategic function | `evidence`, `confidence` |
| `(:Document)-[:DESCRIBES]->(:GameMechanic)` | A document explains a gameplay rule | `section`, `evidence` |
| `(:TowerTroop)-[:DEFENDS]->(:CrownTower)` | A tower troop defends a Crown Tower | `attack_behavior`, `evidence` |
| `(:Card)-[:INTERACTS_WITH]->(:GameMechanic)` | A card participates in a mechanic | `interaction`, `evidence` |

For example:

```text
(:DeckType {name: "Beatdown"})
  -[:INCLUDES_CARD {role: "win condition"}]->
(:Card {name: "Golem"})
```

## Competency questions and Cypher queries

The graph should answer the following competency questions.

```python
QUERIES = {
    "Q1": """
    // Which cards are included in each deck archetype?
    MATCH (d:DeckType)-[r:INCLUDES_CARD]->(c:Card)
    RETURN d.name AS deck_type,
           c.name AS card,
           c.elixir_cost AS elixir_cost,
           r.role AS role
    ORDER BY deck_type, elixir_cost, card
    """,

    "Q2": """
    // Which cards have the highest Crown Tower damage?
    MATCH (c:Card)
    WHERE c.crown_tower_damage IS NOT NULL
    RETURN c.name AS card,
           c.card_type AS card_type,
           c.elixir_cost AS elixir_cost,
           c.crown_tower_damage AS crown_tower_damage
    ORDER BY crown_tower_damage DESC, card
    LIMIT 10
    """,

    "Q3": """
    // Which deck types use Miner, and what role does it play?
    MATCH (d:DeckType)-[r:INCLUDES_CARD]->(c:Card {name: "Miner"})
    RETURN d.name AS deck_type,
           c.name AS card,
           r.role AS role,
           r.evidence AS evidence
    ORDER BY deck_type
    """,

    "Q4": """
    // Which gameplay mechanics are described in each source document?
    MATCH (doc:Document)-[r:DESCRIBES]->(m:GameMechanic)
    RETURN doc.name AS document,
           m.name AS mechanic,
           r.section AS section,
           r.evidence AS evidence
    ORDER BY document, mechanic
    """,

    "Q5": """
    // Which cards occur in more than one deck archetype?
    MATCH (d:DeckType)-[:INCLUDES_CARD]->(c:Card)
    WITH c, collect(DISTINCT d.name) AS deck_types
    WHERE size(deck_types) > 1
    RETURN c.name AS card,
           deck_types,
           size(deck_types) AS number_of_deck_types
    ORDER BY number_of_deck_types DESC, card
    """
}
```

These questions test deck composition, card statistics, strategic roles,
document provenance, and graph aggregation. Card names should be normalized
when loading the CSV, Excel, and text sources so that variants such as
`The Log` and `P.E.K.K.A.` refer to the same `Card` node.