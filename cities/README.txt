/dev/null CITIES - how to add one (the admin's guide)
=====================================================

A city is one file here, cities/<id>.yaml, plus a few small files in pools/. A new city is a new major version
of the game; extra features for a city are minor versions (see docs/design.md, section 10).

THE WORKFLOW
  1. Make the file          python tools/newcity.py rochester_ny --name "Rochester" --state "New York"
                            Every fact starts as VERIFY and every resource as "needs a URL". The city is a
                            draft: it is hidden from the city menu, but  play.cmd --city rochester_ny  opens it for testing.
  2. Give the URLs          In cities/<id>.yaml, `resources:` lists every outside page the city's content comes from.
                            Fill in each  url: null  (or give the URLs to Claude in chat). One resource per source;
                            `covers` says which facts it supports.
  3. Fill in the facts      Under `real:`, replace each VERIFY with the value, its source and the date you got it.
                            Real structure and conditions only. Nothing about wrongdoing by a real person or party.
  4. Real officials         Put the city's real office-holders (now and recent past) in pools/<id>_real_officials_blocklist.txt,
                            one "Given Surname" per line, from the published rosters. Generated names never match them.
  5. Name pool, events      pools/<state>_surnames.txt (40+ names). Dated events under `events:`, each with a source and url.
                            Invented small-town items for quiet days under `news: fillers:`.
  6. Check it               .\tools\citycheck.cmd <id>        lists what is left (blockers must reach zero)
                            .\tools\cityfetch.cmd <id>        fetches every resource URL: DEAD, MOVED or CHANGED links
                            .\tools\cityfetch.cmd <id> --update   saves what the pages look like now (cities/<id>.links.json)
  7. Test it                Play it:  .\play.cmd --city <id>   Run the bots on it, and read the first week.
  8. Release                .\tools\citycheck.cmd --release   must pass. Then set  status: released  in the city file
                            (it appears in the menu), set content_version, bump the game version, and publish release notes.

THE RESOURCES LIST
    - { id: gr_zone_change, kind: facts, name: "Apply for a Zone Change", url: "https://...", retrieved: "2026-11-03",
        covers: [real.law.zoning_process] }
  kind      facts | events | feed | roster | other. A city needs at least one of facts, events, feed and roster.
  url       null = still needed (a blocker). A feed url may contain {city} and {state}.
  scope     for a feed: local. The game reads a city's local feeds for the headlines on day 1 (without one it uses
            the default in data/feeds.yaml).
  covers    the facts this page supports (checked: a typo is a warning). Any URL cited in `real:` must also be listed here.

KEEPING A CITY CURRENT
  The weekly GitHub check (.github/workflows/links.yml) runs cityfetch for every city and fails on a dead link.
  CHANGED means a page's text differs from the last saved check: re-read it, update any fact it supports, then run
  cityfetch --update. Facts older than 180 days are flagged by citycheck as worth re-checking.

CONTENT RULES (docs/design.md, section 7)
  Real: geography, demographics, government structure, law, documented conditions, each with a source and date.
  Fictional: everyone who acts. Real institutions appear only as neutral background. Never a real person.
