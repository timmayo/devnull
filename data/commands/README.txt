/dev/null COMMAND TABLE - how this folder works
================================================

Edit the YAML files here. The game, the command tree and the checker all read them.

  .\tools\cmdview.cmd                    open the command map in your browser (search, variables, unlock paths)
  .\tools\check.cmd                      run every check GitHub runs (run before you commit)
  .\tools\cmdtree.cmd --check --deep      the command-table check on its own
  .\tools\cmdtree.cmd                     draw the tree        (-g hack = one group, -d = details)
  .\tools\cmdtree.cmd --view needs        what each requirement unlocks
  python tools/gen_docs.py                rebuild docs/command_tree.txt

FILES
  contexts.yaml    where the player can be (world, shell). A command works only in the contexts it lists.
  groups.yaml      the groups, their titles and their order on screen.
  gates.yaml       the few conditions worth a name (a bundle several commands share, admin mode,
                   an idea that is not built yet). Most commands do NOT use this file.
  variables.yaml   the values a condition may test (cash, evidence, person.trust ...) and the hint shown
                   when a test fails. A name that is not listed here is a typo and the checker says so.
  schema.json      the shape every file here must have (field names, kinds of value). Checked by
                   tools/validate_schema.py. Add a field to a command? Add it here too.
  <group>.yaml     one file per group (survive.yaml, hack.yaml ...): a list of commands.
                   A new group = a line in groups.yaml + a new <group>.yaml.

A COMMAND
  - name: install_linux                 the word the player types is the first word of `syntax` (default: the name).
                                        (Fields below are illustrative; not every command uses all of them.)
    description: One line shown in the tree, the commands screen and help.
    status: implemented                 leave out while it is only an idea (planned). Live ones need a handler.
    syntax: install_linux               what the player types
    aliases: [h, "?"]                   other words that work (quote yes/no/on/off)
    parent: install                     drawn under another command
    screen: people                      section of the in-game `commands` screen:
                                        look_around | internet | darknet | people | admin
    contexts: [world, shell]            default: [world]
    requires: {cash: 150, person.trust: 10}       must hold to RUN it; the hint says what is missing
    hidden_until: {person.meetings: 4}            must hold before it APPEARS (then it stays)
    cost: {hours: 3, money: 150}        leave out what is zero
    handler: cmd_action                 the Python function (live commands)
    rule: install_linux                 where its numbers live: an action name in slice_rules.yaml
    locked_message: text                shown instead of the generated hint when `requires` fails
    always_available: true              visible from the start, whatever hidden_until says
    examples: [{cmd: ..., shows: ...}]  for `help <command>`

VERBS AND THEIR ITEMS  (buy, meet)
  Some verbs take an item: `buy vpn`, `meet 2 coffee`. The items are NOT listed here. They live in data:
    buy   -> shop:           in data/slice_rules.yaml   (price, note, market, unlock, category)
    meet  -> people_actions: in data/people.yaml        (hours, cost, help, visible, requires_person)
  The verb says where its items come from, and the game builds one command per item (buy_vpn, meet_coffee):
    - name: buy
      items: shop                       the catalog: shop | people_actions
      item_syntax: buy {item}           what the player types for one item
  To add an item: add one entry to its catalog and rebuild the map. Nothing in this folder changes.
  Field mapping for a shop item:   note = description, price = cost, market: darknet = darknet screen,
  unlock = hidden_until, category = type.   For a people action: help = description, hours/cost = cost,
  visible = hidden_until, requires_person = requires (both with `person.`).
  Generated commands show in the command map under their verb, with where each one is defined.

CONDITIONS (requires / hidden_until)
  {cash: 300, evidence: 20}             everything listed must be at least that number
  {person.trust: 25}                    `person.` = about the one person you are dealing with
                                        (meetings, trust, bond, leverage, owes)
  [has_linux_laptop, {skills: 15}]      a name from gates.yaml, mixed with inline tests
  Hints are generated from variables.yaml, so you never write one per threshold.
  A variable written `prefix_*` there covers a whole family: sk_* is every skill topic, and
  {name} in its hint becomes the topic (sk_network_security -> "network security").
  Skill topics are sk_<topic> (levels 1-3); `skills` is overall know-how (0-100).

PLANNED vs LIVE
  Planned commands are ignored by the game. Their numbers are placeholders; tune them when they go live.
  A live command may only test values the game really has (first section of variables.yaml).
