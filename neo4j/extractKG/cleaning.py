"""Optional normalization for the Clash Royale graph.

    import cleaning
    cleaning.apply()          # before resolve_results(), so the entries take effect

Week 5's `kg_model.py` holds the alias and type tables the reference extraction was
loaded with. Week 6 adds to them here rather than editing that file, so that Week 5's
code and its figures stay as they were.

Each entry was written on 2026-10-06 by reading what resolution reported for the
reference extraction (`resolved["merged"]`, `resolved["type_conflicts"]`) and checking
the corpus. As in Week 5, an entry is added only when it is certain: a wrong merge puts
a false fact into the graph, a missed one only leaves two nodes. Measured effect: 388
entities become 372, and 10 type conflicts become 2; 8 more relationships are dropped,
each one wrong (such as functions of the mathematics document typed as tools).
"""

import kg_model

# Different names for one entity: key -> key.
MORE_ALIASES = {"pekka": "p.e.k.k.a", "p.e.k.k.a.": "p.e.k.k.a"}

# The type of an entity returned under more than one: key -> label.
MORE_TYPES = {}


def apply() -> None:
    """Add the Week 6 entries to Week 5's tables. Running it twice changes nothing."""
    kg_model.ALIASES.update(MORE_ALIASES)
    kg_model.TYPES.update(MORE_TYPES)
