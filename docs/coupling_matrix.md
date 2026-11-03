# Coupling matrix

Status: v1, run against `data/world_state.yaml` schema v1 (115 variables, 15 actions).
Regenerate with `python tools/coupling_check.py --matrix`.

## Why

A variable that nothing changes, or that changes nothing, is dead weight or a missing system. Before writing simulation code we checked that every variable is wired in both directions, and that the main loops actually close.

## Method

`tools/coupling_check.py` builds a directed graph:

- `driven_by` text gives edges *into* a variable; `affects` text gives edges *out*.
- Each action's `reads` and `writes` lists give edges between variables and verbs.
- A link is found by matching variable names (or aliases) in the text. It is a heuristic: it can miss a link written in other words and can over-link generic words such as "heat" or "budget". Read the output as a prompt for review.
- Variables set from outside the model are marked in the schema: `exogenous` (calendar, city file, NPC roster), `infrastructure` (turn, date, seed), `terminal` (shown to the player, drives nothing: `time_energy`, `digest_items_per_turn`). Ending inputs count as terminal.

## First pass result

The first run (name matching only, no actions) reported 42 variables nothing drives and 55 that affect nothing. Most were wording gaps, but several were real holes:

| Gap | Fix |
|---|---|
| No verbs in the schema, so player-facing variables (`skills`, `tools_access`, `reputation`, `pattern_memory`) had no writer | Added an `actions` block: records, trace, attend, feed, leak, verify, file, negotiate, hack, trade, buy, maintain, meet, lay_low, work |
| Fail-soft states existed as text but no variable held the current state | Added `player.fail_soft_state`, driven by case status, case stage, legibility, heat |
| Markets had no player verb | `trade` reads market sentiment and skills, writes cash |
| Nothing connected elections to outcomes | `ad_saturation` and `public_opinion_ai` now drive `incumbents_control`, which drives regulation, agency priorities, legislation and judges |
| Courts did not touch the physical project | `case_stage` now drives `data_center_site.stage` and `nsa.legal_authority` |
| Win decay was not fed by anything | `durability` is driven by `enforcement_level` and `repeal_preemption_threat`, which have their own drivers |
| `player.legibility` (the key output) affected nothing | Now drives `attention_queue`, `case_file_on_player`, `fail_soft_state` |
| NPC variables (`knowledge`, `exposure`, `loyalty_vs_leverage`) were dead ends | Linked to verification, heat, legibility, informants and FBI undercover assets |

After the edits: 0 variables with no driver, 0 with no effect, no bad action references, 393 edges.

## Checks beyond orphans

- **Reachability:** every non-infrastructure variable can reach an ending input or a player-facing output.
- **Capture loop closes:** `gov_investment` -> `budget` -> `lobbying_spend` -> `war_chest` -> `ad_saturation` -> `incumbents_control` -> `legislation_pipeline` -> `gov_investment`.
- **Capability vs. legibility loop closes:** `ai_capability` -> `behavioral_model_accuracy` -> `legibility` -> `attention_queue` -> `open_case_status`, and `legibility` feeds back into `fail_soft_state` and the player's available actions.
- **Local loop:** `capture_level` -> `data_center_permits` -> `site.stage` -> `resource_draw` / `nuisance_load` -> `local_anger` -> `organizing_strength` -> `member_vulnerability` -> `capture_level`.
- **Legal route:** `procedural_violations` -> `case_strength` -> `case_stage` -> `site.stage` and `durability`. This path does not touch `natsec_flag`, which is the intent.
- **Hubs** (most links): legibility, time_energy, cash, heat, lobbying_spend, public_opinion_ai, incumbents_control, organizing_strength. Those are the variables to balance first.

## Group matrix

Row drives column; each cell is the number of links.

| from \ to | action | adversary_learning | ambiguity | city_council | community | corporations | courts_legal | data_center_site | fbi | government | information | local_media | local_organizing | meta | natsec_flag | news_digest | npcs | nsa | player | police | social_networks | super_pacs | utilities_state | win_durability | world_meters |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **action** |  | 5 | 1 | 1 | 2 |  | 4 | 1 |  |  | 4 |  | 2 |  | 1 |  | 4 | 1 | 45 | 1 | 2 | 1 |  | 2 |  |
| **adversary_learning** |  | 3 |  |  |  | 1 |  |  |  |  |  |  |  |  |  |  |  | 1 | 1 |  |  |  |  |  |  |
| **ambiguity** |  |  |  |  |  |  |  |  |  |  |  |  | 1 |  |  |  |  |  |  |  |  |  |  | 1 | 1 |
| **city_council** | 3 |  |  | 6 |  | 1 | 3 | 1 |  | 1 |  |  |  |  |  |  |  |  |  |  |  | 1 |  |  |  |
| **community** |  |  |  | 2 | 4 | 1 |  |  |  |  |  | 1 | 4 |  |  |  |  |  |  | 1 |  |  |  |  | 1 |
| **corporations** | 1 |  |  | 2 |  | 5 | 1 | 2 | 1 | 2 |  |  | 1 |  |  |  |  | 2 |  | 1 |  | 1 | 2 | 1 | 4 |
| **courts_legal** | 3 | 1 | 1 |  |  |  | 6 | 1 |  |  |  |  |  |  |  |  |  | 1 | 1 |  |  |  | 1 | 3 |  |
| **data_center_site** | 2 |  |  |  | 5 | 1 |  | 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 1 |
| **fbi** |  |  |  |  |  |  |  |  | 5 | 1 |  |  | 1 |  |  |  | 1 | 2 | 1 |  |  |  |  |  |  |
| **government** |  |  |  | 2 |  | 3 | 2 | 1 | 3 | 3 |  |  |  |  |  |  |  | 1 |  | 2 |  | 1 | 1 | 1 | 3 |
| **information** | 2 |  |  |  |  |  | 1 |  |  |  | 1 |  |  |  |  |  |  |  | 2 |  |  |  |  |  |  |
| **local_media** | 2 |  |  |  | 1 |  |  |  |  |  |  |  |  |  |  | 1 |  |  |  |  |  | 1 |  | 1 |  |
| **local_organizing** | 1 |  | 1 | 1 |  |  | 1 |  |  | 1 |  |  | 5 |  |  |  |  |  |  |  |  |  |  | 1 |  |
| **meta** |  |  |  |  |  |  |  |  |  | 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| **natsec_flag** |  |  |  |  |  |  |  |  | 3 | 1 |  |  |  |  |  |  |  | 1 | 1 |  |  |  |  |  |  |
| **news_digest** |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 2 | 2 |  |  |  |  |  |  |  |  |  |
| **npcs** | 6 |  |  |  |  |  |  |  | 1 |  | 3 |  | 1 |  |  |  | 7 |  | 2 | 1 |  |  |  |  |  |
| **nsa** |  | 1 |  |  |  |  |  |  | 3 |  |  |  |  |  |  |  |  | 4 | 2 |  |  |  |  |  | 2 |
| **player** | 14 |  |  |  |  |  | 2 |  | 2 |  |  | 1 | 1 |  |  |  | 3 | 2 | 23 | 2 | 2 |  |  | 1 |  |
| **police** |  |  |  |  |  |  |  |  | 1 |  |  |  |  |  |  |  |  | 1 | 2 | 7 |  |  |  |  | 2 |
| **social_networks** | 2 |  |  |  | 1 |  |  |  |  |  |  |  |  |  |  |  |  |  | 1 |  | 3 |  |  |  | 4 |
| **super_pacs** |  |  |  | 1 |  |  |  |  |  | 2 |  |  |  |  |  |  |  |  |  |  |  | 2 |  |  | 1 |
| **utilities_state** |  |  |  | 1 | 1 |  |  |  |  | 1 |  |  |  |  |  |  |  |  |  |  |  |  |  | 1 |  |
| **win_durability** | 1 |  |  | 1 |  |  |  | 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 3 | 1 |
| **world_meters** | 2 | 1 | 1 |  | 2 | 4 | 1 |  | 1 | 3 | 1 | 1 |  |  |  | 1 |  | 1 | 1 |  | 1 | 1 |  |  | 4 |

## Known limits and open items

- Edges say two variables are linked, not how. Signs, magnitudes and delays are undefined until we write the update rules.
- Name matching can over-link. Once the engine exists, replace `driven_by` / `affects` prose with explicit edge lists (`from`, `to`, `sign`, `lag`) and make the checker read those instead.
- Several variables are only written by actions (for example `pattern_memory`, `skills`). That is intended, but it means they do nothing until the player acts, so check them in playtests.
- Real-world inputs with no model yet: elections themselves (we model only their effect through `incumbents_control`), taxes, and the weather/drought input to `water_stress`.
- Feedback sign matters more than count. The next step is to mark each loop reinforcing or balancing and check that the opening state does not run away on its own.
