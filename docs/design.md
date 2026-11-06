# /dev/null: design doc

*Humanity trained it. They own it. Your job is to break it.*

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

## 5b. Time and the opening

- **1 turn = 1 day.** The simulation ticks daily; the player can batch quiet days (lay low, rest, extra shifts) so a long run does not mean thousands of keypresses. A news digest summarizes skipped days.
- **A run lasts up to 8 years from the day the player first picks a city.** The start date is the real date on the player's machine and is saved with the run. Any 8-year window contains exactly two US presidential elections and four federal general elections, so two full major cycles are guaranteed whenever the player starts.
- **Elections.** Ballots are counted the day after election day. The national result is seeded and fictional; real results are never encoded. In the slice an election moves `regulation` in proportion to public opinion; `regulation` then decays daily and slows the AI clock.
- **Endings are thresholds, not the calendar.** Most runs end early; the date is only a backstop.
- **Capability Clock** is an S-curve (logistic). Public opinion, market sentiment and regulation scale its rate. Pressure can slow it, not stop it.
- **Real-layer facts are dated.** City data carries a `retrieved` date, and a player may start years later. Show that date, and re-verify the city file on a schedule.

### The first morning

The player wakes up in a cheap apartment with a cheap laptop whose battery is dead: it only runs while plugged in. They have a weekday day job they dislike that pays little.

- **Day job.** Monday to Friday. Take-home is low against daily costs, so there is a small surplus. It gives a boring cover story (lowers legibility) and costs hours and burnout. Burnout cuts the free hours left in the day.
- **Free hours.** About 4 on a workday, 10 on a day off. Every action costs hours.
- **The tethered laptop.** Online actions (posting, leaking, trading) work, but only from the apartment's connection, which leaves a trail: extra legibility and case-file suspicion. A mobile laptop also gives better coverage at live events.
- **Fixing it is a discovery, not a menu item.** Two routes so far:
  - *Store:* browse electronics and pawn shops to find a seller, then pay for a used laptop with a working battery.
  - *NPC:* build enough trust with a person for them to offer a battery swap for a favor.
  Both are found by doing things in the world. Upgrades beyond this (hardened hardware, better tools) are open for later.
- Cash has no real sink beyond the laptop yet, so a saver ends up rich.

### Gear: OS, hardware, apps

The laptop's operating system, hardware and apps are progression. Each item opens options when acquired, and the player has to find out how to get it.

- **Operating system.** Day 1 is Windows 11. The player can learn how to run Linux (found by researching) and install it once the laptop works on battery. Linux unlocks `hack` and makes `trace` stronger.
- **Hardware.** The battery fix is the first upgrade (see above). Other hardware is still to be designed. A placeholder burner phone exists to exercise the system: it makes meetings quieter.
- **Apps.** Still to be designed. A placeholder VPN exists: it shrinks the trail left by the tethered laptop.
- **How the code treats gear.** Each item is a state flag set by an action (`research`, `install_linux`, `buy <item>`, `upgrade_*`). Other actions read the flag in their `requires` lists or effect `terms`. New gear is added in `data/slice_rules.yaml` under `gear` and `shop`; no engine change needed.

### Verbs in the slice

Morning-to-night actions: `extra_shift`, `rest`, `trade`, `attend`, `feed`, `meet`, `lay_low`. Investigation and publishing: `records` (delayed reply, tied to Michigan FOIA timing), `trace`, `verify`, `leak`, `file` (a lawsuit that runs for months), `negotiate`, `maintain`, `hack`. Setup: `research`, `install_linux`, `browse_store`, `upgrade_store`, `upgrade_npc`, `buy <item>`.

The legal route (`records`, `verify`, `file`, `negotiate`, `maintain`) builds evidence and accountability terms without breaking anything, and does not draw FBI attention the way `hack` and unverified `leak` do.

### The morning news digest

The digest is the player's only view of most hidden state. Headlines are lagged and noisy (AI progress, opinion, markets, regulation). A second section, "On your mind", turns hidden agency state into small signs (a patrol car, a blocked call, a bank notice). Silence is ambiguous: a quiet digest can mean safety or a missed sign. Real texture comes from the city file (for example the City Commission usually meets on Tuesdays).

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

## 5c. People, meetings, and what you can see

**Opening sentiment.** Every run starts with two opposed views, and the first
digest says both: the CEOs of the Mega Corps warn that AI could end humanity
(`elite_alarm` starts high, 70) while most of the public uses it as a glorified
search engine (`public_concern` starts low, 10). Leaks and posts move public
concern up; it feeds opinion against AI and the election effect on regulation.

**Meetings.** `data/people.yaml` defines generic meeting types (city
commission, planning commission, web user group, AI builders meetup,
neighborhood association, labor hall, ratepayers group, library talk). The
digest lists the ones held today; `attend [n]` goes to one. Only the City
Commission schedule is a sourced fact; the others are game approximations
modeled on the kinds of groups found on Meetup. Real group names are never used.

**People.** Each meeting has a chance to introduce a fictional person (names
come from `pools/`, rejected if on the real-officials blocklist). Per person:
trust, bond, owes, leverage, ally, hostile, plus hidden traits and a possible
plant. `people` lists them, `person <n>` shows detail and the recorded
history of everything done with them. `meet <n> [action]` offers coffee, favor,
ask, confide, flirt, bribe, extort, recruit; each has a success, fail and
backfire outcome, recorded in the history. Trust drifts down after three weeks
of silence. Allies give small daily benefits.

**Unlocks.** `data/commands/` is the one source for commands: a folder with one file per group,
plus `groups.yaml`, `contexts.yaml`, `gates.yaml` and `variables.yaml` (see `README.txt` there).
A command appears when its `hidden_until` conditions hold (sticky), and the CLI announces each new
one; it runs when its `requires` conditions hold, and a failing one prints a generated hint instead
of "unknown command". Conditions are written inline: `requires: { cash: 300, evidence: 20 }`, or
`{ person.trust: 25 }` for the person being dealt with; only a bundle several commands share gets a
name in `gates.yaml`. Commands also list the `contexts` where they work (only `world` exists so far).
Typed words resolve as exact name, then alias, then a unique prefix; an ambiguous prefix lists the
candidates. Commands without `status: implemented` are planned: designed, and ignored by the game.
The in-game `commands` screen is built from the same table. `tools/cmdtree.py --check --deep` and the
game's startup run the same checks. `status` is always available. Admin mode (`--admin`, or type `admin`) unlocks
everything and adds `admin set|skill|reveal|spawn|unlock|hours|skip`.

**Saving.** `save [name]` writes one JSON file; `load` lists saves, `load <n or name>` loads one. The game autosaves each morning and when you quit, and `play.cmd --continue` (or `--load NAME`, `--saves`) resumes a run. A save holds everything that changes in play (state, people with their hidden traits, pending results, log, market path, the random generator), so a loaded run plays out exactly like the unsaved one. Rules and city data are read fresh on load. Saves live in `%APPDATA%\devnull\saves` (set `DEVNULL_SAVES` to move them) and are per PC. Code: `core/save.py`.

## 5d. Events, meetings and the tape

**Gatherings.** Meetings and real events are one list. The digest shows TODAY
(attendable now, numbered) and UPCOMING (the next occurrence of each, with
links); `upcoming [days]` shows further out. Real events live in the city file
(`events:`) with a source link and retrieval date, and borrow a meeting
template (`kind`) from `data/people.yaml` for who attends. The people you
meet are always fictional. Eventbrite and Meetup are not scraped (no stable
public feed); the recurring meeting types stand in for them.

**The tape.** `data/market.yaml` lists the Mega Corps (Microsoft, Apple, Meta,
Alphabet, Amazon) and five neo-clouds (Nebius, CoreWeave, IREN, Hut 8, Applied
Digital; chosen by market value at the Oct 12, 2026 close from a secondary
source, so revisit). Day 1 shows real delayed quotes fetched at run start
(`devnull.core.market`: Stooq, then Yahoo, both free and unofficial). Later
days are simulated from those prices, driven by the game's market sentiment, and
the digest says so. Real companies appear as market data only and never take
plot actions. **Before release:** use a licensed market-data feed (the free
endpoints are for personal use) and have the use of company names and tickers
reviewed along with the other trademark questions.

## 5e. News sections and Day 1

The digest has LOCAL NEWS and NATIONAL NEWS. Each mixes: curated real items
(city file, with source, date and link), live headlines fetched at run start
(`devnull.core.feeds`, day 1 only, from `data/feeds.yaml`), and stories the game
generates from its own state (`data/news.yaml`, via `devnull.core.news`): police
standoffs, layoffs and hiring, local business leaders' views, FBI raids after
the case against the player escalates, big market moves, and CEO-versus-public
sentiment. Generated stories are generic and fictional and lag reality by three
days. Real items are always tagged `[real]`.

`events` shows today's gatherings and the next occurrence of each; `markets`
shows the tape. Neither appears in the digest (it only lists what is on today).
Real City Commission dates come from the city's adopted 2026 schedule; the
recurring Tuesday approximation applies only in years the city file does not
list. Day 1 always includes a made-up neighbors' open house with high odds of
meeting people.

**Links.** Real news and events are clickable terminal hyperlinks (OSC 8; Windows
Terminal and VS Code). The whole line is the link and nothing is printed below it.
Terminals without support get the URL inline after the text. Force a mode with
`DEVNULL_LINKS=osc8` or `plain`. News sections show at most 10 stories each, and
today's events appear only through the `events` command.

## 5f. People's skills

Each person has 2-3 related skills and 1-2 unrelated side skills, each at one of
three levels: beginner, advanced, expert (`skills:` in `data/people.yaml`). Related
skills come from the person's type plus the event where you met them (a web user
group produces web and Python people; a labor hall produces labor-law and organizing
people). Side skills (cooking, ham radio, car repair, and so on) appear on the person
sheet once their trust reaches 30. The `learn` action asks a trusting person to teach
you their best skill: your skills rise by 0.8 + 0.8 x their level, and an advanced or
expert Linux person can reveal how to boot Linux.

**Your skills.** `status` lists your own skills with the same three levels as people
(none, beginner, advanced, expert). You start with data analysis (beginner, from your
day job). `research` slowly teaches tech skills (self-study tops out at advanced), and
`meet <n> learn` teaches a person's best skill up to their level. The older 0-100
"know-how" number still gates tools (trace, VPN, hack). Status also explains burnout
(hours lost past 60, 85 and 95), heat and legibility in plain words.

## 5g. Research

`research` opens a menu of 16 topics (`data/research.yaml`). Each is studied by one of
three methods: online (2h, free, leaves a trail on the tethered laptop), library (3h,
slower, no trail) or a paid course (2h, $60, fastest). Study adds xp; the levels are
beginner, advanced and expert (3, 9 and 18 xp). Online and library study stop at advanced;
a course or an expert person gets you to expert. Each level shows a discovery and applies
one-time effects (for example, hardware repair level 1 shows where to buy a laptop and
level 2 lets you fix yours for $60; Linux level 1 teaches how to install it).

Your levels are exposed to the rules as variables `sk_<topic>` (0 to 3), so actions improve
as you learn: records requests (public-records law, Python), tracing (data analysis,
finance, Linux), hacking (network security is now required; Linux helps), leaks and
verification (investigative reporting), lawsuits (litigation), attending and posting
(land use, public speaking, organizing, web development). A few levels also unlock
readings in `status`: data analysis 2 shows AI progress, network security 2 the police
file, network security 3 the FBI's interest and NSA coverage.

**Darknet.** The place where gear is bought (`buy <item>`) is called the DARKNET in the
command list. Items appear as you unlock them. The internal rules key is still `shop`.
