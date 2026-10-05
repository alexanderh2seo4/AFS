# AFS Karte

Public anonymous volunteer maps on GitHub Pages, with a separate private local AFSer importer and MCP server.

- `/sending/`: published Sending homeinterviews, including open and picked slots, urgent highlighting, nearby suggestions and verified AFSer project links. Filters offer open slots, picked interviews, and pickups detected in the last 30 days.
- `/awayees/`: outgoing students currently abroad by default, grouped by destination country. The filter can show preparation or all current outgoing participants.
- `/hostees/`: active hosted students, with approximate location areas and source links.
- `/families/`: active host families and Hosting homeinterviews.
- `/returnees/`: pseudonymous Returnees, filtered by default to people whose two AFS seminars are not both marked complete. The page can show all Returnees together or filter and sort by exchange year, and it links to the current Excel table and monthly snapshots.

The map opens by default, including on phones. On the first visit, visitors choose only their city/postcode; München is prefilled. The matching chapter is selected automatically and can then be changed above the map, including **Alle verfügbaren anzeigen**, which clears the current record and urgency filters. Returning visitors keep their location and selected chapter. Only the selected chapter file is fetched by default. Residence preferences remain in the browser. The default distance reference is Munich's public city centroid, not a visitor's detected location.

## Public data and private source

`docs/data/` deliberately contains only approved anonymous projections. Map records use opaque IDs, chapter, public city/country labels, status, urgency, deadline, approximate coordinates and AFSer links. Returnee files contain a keyed pseudonym, exchange year and whether each of the two AFS seminar fields is populated. They contain no names, contact details, dates of birth, household addresses, source payloads, login credentials or access tokens. Returnees are limited to records available to the configured AFSer account, currently Süd; they are not a Germany-wide register. Every home location displays a **1 km radius** circle around a stable randomly shifted public postal-area centroid. This is not a confirmed home address or a claim that the household lies inside that circle. Awayees show country points only. Unknown locations are never guessed; unassigned open interviews appear in the All list without a map point.

The complete source responses and SQLite dataset remain only in the ignored local `.private-data/` directory with owner-only permissions. The separate `mcp/` code repository contains the importer, MCP tools and audited public export command. Raw source payloads have no HTTP or MCP read endpoint. AFSer still requires its own login to view details or join interview teams.

GitHub Pages serves both code and anonymous data. Visitors do not need an invitation, a tunnel or this computer online. The previous private tunnel service has been stopped.

Sending source links open verified signup project pages. Awayees, Hostees and family links open verified AFSer lists; AFSer's own saved chapter setting may require selecting the committee there. No unverified individual participant permalink is invented.

## Automatic publication

The dedicated updater runs in Ubuntu on **elrsisbest** (`alex-pc` / `alex-linux` over SSH), in `~/work/afs-live/site`. It imports AFSer immediately on startup and every **5 minutes after a completed import**, validates the snapshot, exports only anonymous fields, audits the files and publishes GitHub Pages. The first successful import of each calendar month also saves that month's Returnee workbook under `docs/data/returnees/archive/YYYY-MM.xlsx`; an existing monthly snapshot is kept unchanged. Open browser tabs check for new data every **minute**, on returning to the tab, and after reconnecting. GitHub Pages build/CDN time adds a short delay; this is automatic polling, not an instantaneous AFSer event feed. Failed imports retain the last published snapshot.

The `afs-live.service` user service restarts failed workers. Windows starts Ubuntu through the `AFS Live Updater` scheduled task; user lingering keeps the Linux service running independently of SSH sessions. The worker fast-forwards both dedicated repositories before an import and refuses dirty checkouts. Its repository-specific deployment key can publish only the AFS repository. Source login, database, projection key and caches remain private on that computer.

```sh
ssh alex-linux 'systemctl --user status afs-live.service'
ssh alex-linux 'cd ~/work/afs-live/site && python3 scripts/update_public.py status'
```

The old laptop updater is stopped to avoid competing writers. A local fallback can still be started explicitly:

```sh
python3 scripts/update_public.py background --interval 300 --initial-sync
```

For immediate manual publication, stop the worker first and run `python3 scripts/update_public.py sync-and-publish`. `once` exports an already committed snapshot without reading AFSer again.

## Source coverage

The importer uses AFSer's authenticated read-only APIs and the interview task board. It checks list completeness within the account's accessible source scope, follows all board pages, partitions capped student lists by chapter and source status/year, and verifies open interview roles. All source fields returned by supported endpoints remain local; only relevant active records enter the public map.

The database includes all 95 committees, a Germany-wide aggregate, and nationwide postcode/locality geography. Sending interviews cover Germany. The current AFSer account returns participant and hosting data for Süd; checks with Hamburg and the Nord/West source filters return no records. Empty participant or hosting lists outside Süd do not establish that there are no active records there. Germany-wide coverage for those categories requires broader source access. The currently accessible data is retained.

Interview pickup dates are inferred only from a decrease in open slots between successful committed imports. Existing assignments without that evidence retain an unknown date and remain in the picked/all view; they are never stamped as newly picked. Fully picked interviews no longer show a signup action. Partially picked interviews retain the link to their remaining open slots.

The optional historical interview API returns only 2,000 of 4,489 records and exposes no usable pagination. This limitation is recorded in the local coverage manifest; it does not limit the fully traversed actionable interview board.

## Development

The location finder includes every distinct postal/locality row from the GeoNames Germany download: 23,297 entries across 10,813 postcodes in the current index. Shared postcodes retain all town names; county labels and confirmed chapter mappings distinguish repeated names. Search accepts German umlauts, transliterations, Munich's English name, and postcode prefixes. Selecting a postcode uses that postal area's coordinates. Searches run in the browser without sending the entered location to a geocoding provider.

Refresh the public geography index and run its search checks with:

```sh
python3 scripts/build_locations.py
node scripts/test_locations.mjs
```

No npm build is required. After changing `docs/index.html`, rebuild its four route wrappers:

```sh
python3 scripts/build_pages.py
python3 -m http.server 5173 --bind 127.0.0.1 --directory docs
```

The browser cancels superseded chapter requests, rejects mixed export generations, and bounds downloads to 12 seconds. Failed refreshes retain the last successful view for the selected chapter and display the failure. Run the fetch regression checks with:

```sh
node --test scripts/tests/*.mjs
```

Backend tests cover public field leakage, active/chapter filtering, randomized locations, source coverage, atomic snapshots, authentication and actual MCP stdio. Public file audits reject unknown fields and wrong home-circle radii before publishing.

## Attribution

Leaflet 1.9.4 is vendored with its BSD-2-Clause license. OpenStreetMap tiles include visible contributor attribution and origin-only referrers. Public Germany postcode centroids use GeoNames (CC BY 4.0); country points use Natural Earth (public domain). Private household addresses are never sent to a geocoding provider.
