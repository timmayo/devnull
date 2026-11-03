# /dev/null: design doc

*Know Your Enemy.*

Status: early design. This is a working document; expect it to change.

## 1. The spine

**Player fantasy:** one unpredictable person in a world of predictors.

**Premise:** The government has enabled Mega Corporations to cut corners and deploy data centers and AI faster. It has invested in them, and they donate to the Super PACs that keep the incumbents in power. The corps burn billions, cut jobs, drain water and power, and push AI into daily life that nobody asked for. They bribe local councils to rezone land without proper process. Communities are only beginning to push back. You are one person with a skill the movement lacks.

**Tone:** dark, dry, corporate-euphemism satire over a serious core. A terminal-style interface carries the world's reaction to the player through a news digest.

**Not the goal:** "smash the AI." The game is about accountability, siting, and who pays. Some AI uses are genuinely beneficial, and some communities want the jobs and tax base.

**Central tension:** every system feeds one of two clocks.

- **Capability Clock:** AI progress. It can be slowed, never stopped.
- **Legibility:** how well the system can model you. Routine is a vulnerability, so erratic behavior is rewarded.

## 2. The capture loop

Gov investment → corp profit → PAC donations → incumbents win → deregulation → more investment.

The player's goal is to cut or reverse the loop. Each link is an attack surface.

| Link | Player levers |
|---|---|
| Gov investment | Expose conflicts of interest, leak financials to move markets |
| Corp profit | Short stocks, leak safety failures, sabotage a data center |
| PAC donations | Expose donors (Donor Exposure up, donor flight) |
| Elections | Shift public opinion, back challengers |
| Deregulation | Stall bills, feed regulators evidence |

The loop can flip. If investment drops or a scandal hits, the government may turn on the corps, which creates a new world state with different enemies.

### Opening state ("Regulatory Capture")

Regulatory Pressure very low (~10); Gov Investment in Corps high; Corp Lobbying and PAC War Chests high; Data Center Permits fast-track; AI Capability low-mid and rising; Power Grid Strain low and climbing; Info Integrity mid; Public Opinion neutral/uninformed; Player Legibility and Heat near zero.

## 3. Layers

### Local (the entry ramp)
Councils, zoning, utilities. The cheapest place to win: stopping a site at Proposed or Rezoned costs a records request and a leak, while stopping an Operational one costs sabotage. The player is the paper trail: tracing shell companies, pulling land records, finding payments. Organizers supply anger and bodies; the player supplies evidence.

Corporate counter-moves: shell companies and NDAs, astroturf groups, community benefit deals (co-optation), SLAPP suits, relocation threats, state preemption lobbying.

### State
Utility commissions, legislatures, preemption. Preemption can remove local control entirely, so local wins can be temporary.

### Federal
Super PACs, agencies, the NatSec fusion.

### Courts and legal
Injunctions, state AGs, public records litigation, zoning appeals. The realistic non-sabotage route to durable change, and it does not trip the NatSec Flag.

## 4. Agencies

| | Police | FBI | NSA |
|---|---|---|---|
| Tech literacy | ~5 | ~50 | ~95 |
| Powers | Stop, ticket, arrest, raid | Investigate, arrest (federal) | Intercept, decrypt, analyze. No arrests |
| Scope | Local district | Domestic | Global |
| Bandwidth | Plentiful, shallow | Limited, case-driven | Very scarce for you specifically |
| Failure mode | Blunt, wrong, exploitable | Slow, needs evidence | Misses you if you are low priority |

- **Police** are dangerous because they are dumb and violent, not smart. They cannot trace a hack but will kick in the wrong door. They can be weaponized (false tips, misdirected patrols).
- **FBI** understands cybercrime. Sloppy hacks get attributed to you. It needs Evidence Strength to act, so cases can be poisoned, exhausted, or redirected.
- **NSA** is passive. It never arrests anyone; it raises your Legibility floor and feeds tips downstream. It has an Attention Queue, so staying small and boring is a valid strategy.

**Escalation ladder:** Police Case File → FBI referral → NSA tips raise Evidence Strength → warrant → arrest. Each rung is a chance to disrupt the chain.

### National Security Trigger (NatSec Flag)

- **Below threshold:** agencies are siloed, with separate Heat.
- **Above threshold:** agencies fuse. Heat merges, NSA intel flows to FBI, FBI tasks local police, and Evidence Strength jumps.

Actions that hurt the AI buildout most are the ones most likely to trip it, since data centers and compute are likely to be treated as critical infrastructure. Hit hard and get fused, or hit small and stay slow.

- **Raises it:** attacking critical infrastructure, foreign contact, hitting government-invested companies, using stolen classified data.
- **Lowers it:** staying domestic and small, using the press, legal avenues, making the government's own investments look like the national-security risk.

## 5. Other systems

- **Personal life:** day job, rent, relationships, Burnout, and Integrity. Gray acts (disinfo, doxxing, sabotage) lower Integrity; honest wins raise it. Cover Quality lowers Legibility.
- **Enemy that learns:** Behavioral Model Accuracy rises with AI Capability and with your repeated patterns. Tactics you reuse lose effectiveness.
- **Unreliable information:** planted documents and deepfakes. `verify` costs time and risk. Publishing something false craters Credibility.
- **Wins that decay:** every victory has a Win Durability and needs maintenance (watchdogs, follow-up elections). Decay happens at election and session boundaries.
- **Fail-soft states** instead of game over: Under Investigation, Legal Defense, Lying Low, Operating Through Proxies, Exile / Relocation.

## 6. Interface

Command-line style. The end-of-turn **news digest** is the primary screen: local paper, wire service, corp press releases, social feed. The player infers hidden state from coverage. Verbs stay few, with heavy consequences.

Current verbs: `records`, `trace`, `attend`, `feed`, `leak`, `verify`, `file`, `negotiate`, `watch`, `lay-low`, `meet`, `work`. (`watch` and `negotiate` could merge into `maintain`.)

Launch model: the simulation core is separate from the display layer. Prototype in a real terminal UI; plan for an embedded terminal-style window for release so players can launch from an icon.

## 7. Real vs fictional (content rules)

The player selects a real city, and it keeps its real name. Real structure and conditions, fictional conduct and actors.

- **Real:** geography, climate, demographics, economy, government structure (council size, wards, charter, meeting and election calendars), state and local law, documented conditions (rate trends, water supply, grid operator). Each real fact carries a source and a retrieved date.
- **Fictional:** everyone who acts and anything that does something: council members, mayor, police chief and officers, lawyers, reporters, the developer, PACs, the proposed site. Real institutions (police department, utility, newspaper) appear only as neutral background supplying facts; a generated analogue acts in the plot.
- **Safeguards:** fictional office-holders get invented backgrounds and never match a real incumbent's name, biography, party, or term dates. A collision check rejects any generated name and role that matches a real person holding that role in the city, now or recently. The scenario must not mirror a live local dispute. A fiction disclaimer is shown in game.
- **Residual risk:** a corrupt mayor or chief in a named real city is the most recognizable pairing in the content. This is a business decision to review with a media/IP attorney before commercial release. This document is not legal advice.

## 8. Open questions

1. Can the player flip the government (winning elections so investment becomes oversight), or only in certain endings?
2. Do NPCs include people inside the agencies (a bored NSA analyst, a burned-out FBI agent) as allies, informants, or plants?
3. Does the NatSec Flag ever clear?
4. Is Integrity visible or hidden?
5. How many fail-soft states can stack?
6. Does the world run local fights without the player?
7. How hard does state preemption hit?
8. Curated hand-built opening towns, or procedural towns from a chosen state, or both?
9. Title and trademark: overlap with Dev Null Productions LLC should be reviewed before any store page.

## 9. Roadmap

1. Coupling matrix across the capture loop, local layer, and agencies, to find orphan variables.
2. Vertical slice (~30 minutes of play): AI Capability, Market Sentiment, Public Opinion, Legibility, Cash, Heat, NPC Trust, Police Case File, FBI Open Case Status, NSA Collection Coverage; 5 NPCs; one clock; one ending.
3. Content as data: events, NPCs, companies, and dialogue in YAML, simulation in code, seeded RNG, plain-text saves.
