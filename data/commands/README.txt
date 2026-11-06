/dev/null COMMAND TABLE - how this folder works
================================================

Edit the YAML files here. The game, the command tree and the checker all read them.

  .\tools\cmdtree.cmd --check --deep      check everything (run before you commit)
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
  <group>.yaml     one file per group (survive.yaml, hack.yaml ...): a list of commands.
                   A new group = a line in groups.yaml + a new <group>.yaml.

A COMMAND
  - name: meet_bribe                    verb_noun. The word the player types is the first word of `syntax`.
    description: One line shown in the tree, the commands screen and help.
    status: implemented                 leave out while it is only an idea (planned). Live ones need a handler.
    syntax: meet <n> bribe              what the player types (default: the name)
    aliases: [h, "?"]                   other words that work (quote yes/no/on/off)
    parent: meet                        drawn under another command
    screen: people                      section of the in-game `commands` screen:
                                        look_around | internet | darknet | people | admin
    contexts: [world, shell]            default: [world]
    requires: {cash: 150, person.trust: 10}       must hold to RUN it; the hint says what is missing
    hidden_until: {person.meetings: 4}            must hold before it APPEARS (then it stays)
    cost: {hours: 1, money: 150}        leave out what is zero
    handler: cmd_meet                   the Python function (live commands)
    rule: people_actions.bribe          where its numbers live: an action name, shop.<item>, people_actions.<name>
    locked_message: text                shown instead of the generated hint when `requires` fails
    always_available: true              visible from the start, whatever hidden_until says
    examples: [{cmd: ..., shows: ...}]  for `help <command>`

CONDITIONS (requires / hidden_until)
  {cash: 300, evidence: 20}             everything listed must be at least that number
  {person.trust: 25}                    `person.` = about the one person you are dealing with
                                        (meetings, trust, bond, leverage, owes)
  [has_linux_laptop, {skills: 15}]      a name from gates.yaml, mixed with inline tests
  Hints are generated from variables.yaml, so you never write one per threshold.

PLANNED vs LIVE
  Planned commands are ignored by the game. Their numbers are placeholders; tune them when they go live.
  A live command may only test values the game really has (first section of variables.yaml).
