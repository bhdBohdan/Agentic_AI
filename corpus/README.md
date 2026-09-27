---
license: cc-by-nc-sa-4.0
language:
- en
pretty_name: Clash-Royale-Cards-Data
size_categories:
- n<1K
---
# Dataset Card for Dataset Name

<!-- Provide a quick summary of the dataset. -->

This dataset provides a comprehensive view of all Clash Royale cards, combining core gameplay attributes with usage and balance-related statistics. Each entry represents a card and includes details such as elixir cost, rarity, evolution levels, mobility, and attack type. The dataset also includes derived fields like hitpoints and usage frequency, allowing for strategic and analytical insights into the game’s meta.


### Dataset Description

<!-- Provide a longer summary of what this dataset is. -->


It can be used for various types of analysis from studying the relationship between card cost and effectiveness to exploring balance trends across rarities and troop types. Developers and data analysts can also apply this data in visualization projects, AI-driven strategy tools, or game balance simulations.

All original game data and images belong to Supercell. This dataset is a structured aggregation created for research, learning, and non-commercial analytical purposes.



## Uses

<!-- Address questions around how the dataset is intended to be used. -->
It can be used for various types of analysis from studying the relationship between card cost and effectiveness to exploring balance trends across rarities and troop types. Developers and data analysts can also apply this data in visualization projects, AI-driven strategy tools, or game balance simulations.


#### Data Collection and Processing

<!-- This section describes the data collection and processing process such as data selection criteria, filtering and normalization methods, tools and libraries used, etc. -->

Card data such as name, rarity, elixir cost, and type were sourced from the official Clash Royale API and verified using in-game information. Additional statistics, including usage levels and hitpoints, were aggregated from publicly available community datasets and leaderboard analyses. The data was cleaned and merged from multiple structured files, ensuring consistent card naming and removing duplicates. Numeric fields such as hitpoints and usage were standardized, and the “groupCard” flag was verified using troop count data.