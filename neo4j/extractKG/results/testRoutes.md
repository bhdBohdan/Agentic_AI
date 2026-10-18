# Retriever Test Results: `test_set.json`

**Evaluated Retrievers:** `hybrid`, `cypher`

---

## Question Q1

> Which cards are included in each deck archetype?

**Expected Answer:** The graph should return deck types, cards, elixir costs, and strategic roles.

| Run | Retriever | Answer | Problem |
|:---:|:---|:---|:---|
| 1 | `cypher` | The Bait Deck includes The Log, Goblin Barrel, Rocket, Ice Spirit, Knight, Inferno Tower, Goblin Gang, and Princess [1, 2, 3, 4, 5, 6, 7, 8], while Beatdown contains Baby Dragon, Lightning, Mega Minion, Night Witch, Tornado, Zap, Lumberjack, and Golem [9, 10, 11, 12, 13, 14, 15, 16]. Bridge Spam consists of Zappies, Royal Ghost, Fireball, Battle Ram, Lumberjack, Zap, Inferno Dragon, Bandit, and Ice Golem [17, 18, 19, 20, 21, 22, 23, 24, 25]; Control features Barbarian Barrel, Poison, Skeletons, Royal Ghost, Goblin Hut, Little Prince, Wallbreakers, and Miner [26, 27, 28, 29, 30, 31, 32, 33]; Cycle Deck includes Knight, Goblin Drill, Cannon, Goblins, Bomber, Fire Spirit, Poison, and Snowball [36, 37, 38, 39, 40, 41, 42, 43]; and Siege includes X-Bow, Knight, Mortar, The Log, Skeletons, and Electro Spirit [45, 46, 47, 48, 49, 50]. |  |
| 1 | `hybrid` | Beatdown decks include Golem, Lumberjack, Night Witch, Baby Dragon, Mega Minion, Zap, Tornado, and Lightning, while Cycle decks include Goblin Drill, Knight, Goblins, Fire Spirit, Bomber, Poison, Snowball, and Cannon [1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 22, 23, 24, 25, 26, 27, 28]. Bridge Spam includes Fireball, Lumberjack, and Zap, whereas Bait decks include Knight and The Log, and Control decks include Poison and Skeletons [4, 5, 16, 17, 18, 19, 20, 21]. |  |

**Generated Queries:**

- **Run 1 (cypher):**
  ```cypher
  MATCH (d:DeckType)-[r:INCLUDES_CARD]->(c:Card) RETURN d.name AS deck_type, c.name AS card, r.chunks AS chunks
  ```

---

## Question Q2

> Which cards have the highest Crown Tower damage?

**Expected Answer:** The graph should return cards ordered by crown_tower_damage.

| Run | Retriever | Answer | Problem |
|:---:|:---|:---|:---|
| 1 | `cypher` | not stated (no sources) |  |
| 1 | `hybrid` | not stated. |  |

**Generated Queries:**

- **Run 1 (cypher):**
  ```cypher
  MATCH (c:Card)-[r:INTERACTS_WITH]->(gm:GameMechanic) WHERE toLower(gm.name) CONTAINS 'crown tower damage' RETURN c.name AS card, gm.name AS mechanic, r.chunks AS evidence
  ```

---

## Question Q3

> Which deck types use Miner, and what role does it play?

**Expected Answer:** The graph should return the deck types containing Miner and the role recorded on each relationship.

| Run | Retriever | Answer | Problem |
|:---:|:---|:---|:---|
| 1 | `cypher` | Miner is used in Control decks, where it serves as a win condition [1], [2]. |  |
| 1 | `hybrid` | Miner is used in Control decks [3, 27]. It functions as a win condition [2]. |  |

**Generated Queries:**

- **Run 1 (cypher):**
  ```cypher
  MATCH (c:Card)-[r:HAS_ROLE]->(role:Role), (dt:DeckType)-[rel:INCLUDES_CARD]->(c) WHERE toLower(c.name) CONTAINS 'miner' RETURN dt.name AS deck_type, c.name AS card, role.name AS role, r.chunks AS role_evidence, rel.chunks AS deck_evidence
  ```

---

## Question Q4

> Which gameplay mechanics are described in each source document?

**Expected Answer:** The graph should return source documents, mechanics, sections, and evidence.

| Run | Retriever | Answer | Problem |
|:---:|:---|:---|:---|
| 1 | `cypher` | GameModes.txt describes the Elixir Management mechanic [1]. The strategies.txt document describes the Elixir Control mechanic [2]. |  |
| 1 | `hybrid` | Source [1] describes targeting, sight range, building mechanics, damage types, and friendly fire/buff rules, while Source [2] details Draft and Triple Draft challenge mechanics. Source [3] covers deck management, card placement territory, emote communication, and elixir management principles. |  |

**Generated Queries:**

- **Run 1 (cypher):**
  ```cypher
  MATCH (d:Document)-[r:DESCRIBES]->(g:GameMechanic) RETURN d.name AS document, g.name AS mechanic, r.chunks AS chunks
  ```

---

## Question Q5

> Which cards occur in more than one deck archetype?

**Expected Answer:** The graph should return cards and the deck archetypes in which they occur.

| Run | Retriever | Answer | Problem |
|:---:|:---|:---|:---|
| 1 | `cypher` | The cards that occur in more than one deck archetype are The Log, Goblin Barrel, Knight, Zap, Lumberjack, Royal Ghost, Fireball, Poison, Skeletons, Miner, X-Bow, and Baby Goblins [1], [2], [3], [4], [5], [6], [7], [8], [9], [10], [11], [12]. |  |
| 1 | `hybrid` | not stated. |  |

**Generated Queries:**

- **Run 1 (cypher):**
  ```cypher
  MATCH (d:DeckType)-[r:INCLUDES_CARD]->(c:Card) WITH c, collect(d.name) AS deck_types, collect(r.chunks) AS chunk_evidence WHERE size(deck_types) > 1 RETURN c.name AS card, deck_types, chunk_evidence
  ```

---
