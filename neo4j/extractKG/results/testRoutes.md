# Retriever Test Results: `test_set.json`

**Evaluated Retrievers:** `hybrid`, `cypher`

---

## Question Q1

> Which cards are included in each deck archetype?

**Expected Answer:** The graph should return deck types, cards, elixir costs, and strategic roles.

| Run | Retriever | Answer | Problem |
|:---:|:---|:---|:---|
| 1 | `cypher` | The Bait deck includes The Log, Goblin Barrel, Rocket, Ice Spirit, Knight, Inferno Tower, Goblin Gang, and Princess, while the Beatdown deck uses Baby Dragon, Lightning, Mega Minion, Night Witch, Tornado, Zap, Lumberjack, and Golem [1, 2]. Other archetypes like Bridge Spam, Control, Cycle, Siege, Log Lure, Spell Cycle, and Tesla contain various combinations of cards such as Miner, X-Bow, and Zappies [3, 4, 5, 6, 7, 8, 9, 10]. |  |
| 1 | `hybrid` | Beatdown decks include Golem, Lumberjack, Night Witch, Baby Dragon, Mega Minion, Zap, Tornado, and Lightning, while Cycle decks include Goblin Drill, Knight, Goblins, Fire Spirit, Bomber, Poison, Snowball, and Cannon [1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 22, 23, 24, 25, 26, 27, 28]. Bridge Spam includes Fireball, Lumberjack, and Zap, whereas Bait decks include Knight and The Log, and Control decks include Poison and Skeletons [4, 5, 16, 17, 18, 19, 20, 21]. |  |

**Generated Queries:**

- **Run 1 (cypher):**
  ```cypher
  MATCH (d:DeckType)-[r:INCLUDES_CARD]->(c:Card) RETURN d.name AS deck_archetype, collect(c.name) AS cards, collect(r.chunks) AS evidence_chunks
  ```

---

## Question Q2

> How many cards are in the game?

**Expected Answer:** The graph should return the number of cards.

| Run | Retriever | Answer | Problem |
|:---:|:---|:---|:---|
| 1 | `cypher` | There are 153 cards in the game. [1] |  |
| 1 | `hybrid` | The number of cards in a deck depends on the game mode: a default deck contains 8 cards, while the Mega Deck Challenge uses 18 cards and various 4-card challenges use 4 cards [3]. Players battle using a deck of 8 cards by default [1, 3]. |  |

**Generated Queries:**

- **Run 1 (cypher):**
  ```cypher
  MATCH (c:Card) RETURN count(c) AS total_cards
  ```

---

## Question Q3

> Which deck types use Miner, and what role does it play?

**Expected Answer:** The graph should return the deck types containing Miner and the role recorded on each relationship.

| Run | Retriever | Answer | Problem |
|:---:|:---|:---|:---|
| 1 | `cypher` | Miner is used in Control decks where it acts as a win condition [1], [2]. |  |
| 1 | `hybrid` | Miner is used in Control decks [3, 22, 27]. It functions as a win condition [2]. |  |

**Generated Queries:**

- **Run 1 (cypher):**
  ```cypher
  MATCH (c:Card)-[:HAS_ROLE]->(r:Role), (dt:DeckType)-[rel:INCLUDES_CARD]->(c) WHERE toLower(c.name) CONTAINS 'miner' RETURN dt.name AS deck_type, c.name AS card, r.name AS role, rel.chunks AS evidence_chunks
  ```

---

## Question Q4

> Which gameplay mechanics are described in each source document?

**Expected Answer:** The graph should return source documents, mechanics, sections, and evidence.

| Run | Retriever | Answer | Problem |
|:---:|:---|:---|:---|
| 1 | `cypher` | GameModes.txt describes the Elixir Management mechanic [1]. Strategies.txt#14 describes the Elixir Control mechanic [2]. |  |
| 1 | `hybrid` | Source 1 details targeting, sight range, building mechanics, damage types, and friendly fire/buff rules [1]. Sources 2 and 3 describe draft challenges, deck building, territory deployment, emote communication, and elixir management mechanics [2, 3]. |  |

**Generated Queries:**

- **Run 1 (cypher):**
  ```cypher
  MATCH (d:Document)-[:DESCRIBES]->(g:GameMechanic) RETURN d.name AS document, collect(g.name) AS mechanics
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
  MATCH (d:DeckType)-[r:INCLUDES_CARD]->(c:Card) WITH c, count(d) AS deck_count, collect({deck: d.name, chunks: r.chunks}) AS evidence WHERE deck_count > 1 RETURN c.name AS card, deck_count, evidence
  ```

---
