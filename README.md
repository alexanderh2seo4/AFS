# AFS Karte

Public anonymous volunteer maps on GitHub Pages, with a separate private local AFSer importer and MCP server.

- `/sending/`: active open Sending homeinterviews, urgent highlighting, nearby suggestions and the verified AFSer project page for signing up.
- `/hopees/`: relevant active outgoing participants, grouped by destination country.
- `/hostees/`: active hosted students, with approximate location areas and source links.
- `/families/`: active host families and Hosting homeinterviews.

München loads by default, without a login or a location dialog. Visitors can change their residence, select a chapter, or explicitly select **Alle Komitees**. Only the selected chapter file is fetched by default. Residence preferences remain in the browser. The default distance reference is Munich's public city centroid, not a visitor's detected location.

## Public data and private source

`docs/data/` deliberately contains the approved anonymous static projection: opaque IDs, chapter, public city/country labels, status, urgency, deadline, approximate coordinates and AFSer links. It contains no names, contact details, household addresses, source payloads, login credentials or access tokens. Every home location displays a **1 km radius** circle around a stable randomly shifted public postal-area centroid. This is not a confirmed home address or a claim that the household lies inside that circle. Hopees show country points only. Unknown locations are never guessed; unassigned open interviews appear in the All list without a map point.

The complete source responses and SQLite dataset remain only in the ignored local `.private-data/` directory with owner-only permissions. The separate `mcp/` code repository contains the importer, MCP tools and audited public export command. Raw source payloads have no HTTP or MCP read endpoint. AFSer still requires its own login to view details or join interview teams.

GitHub Pages serves both code and anonymous data. Visitors do not need an invitation, a tunnel or this computer online. The previous private tunnel service has been stopped.

Sending source links open verified signup project pages. Hopees, Hostees and family links open verified AFSer lists; AFSer's own saved chapter setting may require selecting the committee there. No unverified individual participant permalink is invented.

## Automatic publication

The local updater synchronizes AFSer, validates a complete source snapshot, exports only approved active fields, audits the public files, commits only `docs/data/` and pushes GitHub Pages. It runs every **30 minutes** while this computer's current session is running. A source failure preserves the previous published snapshot. GitHub continues serving that snapshot while this computer is offline; a notice appears if it is more than 24 hours old.

```sh
python3 scripts/update_public.py background
python3 scripts/update_public.py status
python3 scripts/update_public.py stop
```

After reboot/login, start the updater again from an authorized terminal or Codex session. macOS blocked the old LaunchAgent's Documents access; no privacy settings were weakened. To synchronize and publish immediately:

```sh
python3 scripts/update_public.py sync-and-publish
```

To publish an already complete local snapshot without reading AFSer again:

```sh
python3 scripts/update_public.py once
```

## Source coverage

The importer uses AFSer's authenticated read-only APIs and the interview task board. It checks list completeness, follows all board pages, partitions capped student lists by chapter and source status/year, and verifies open interview roles. The nationwide student list is covered in full. All source fields returned by supported endpoints remain local; only relevant active records enter the public map.

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

Backend tests cover public field leakage, active/chapter filtering, randomized locations, source coverage, atomic snapshots, authentication and actual MCP stdio. Public file audits reject unknown fields and wrong home-circle radii before publishing.

## Attribution

Leaflet 1.9.4 is vendored with its BSD-2-Clause license. OpenStreetMap tiles include visible contributor attribution and origin-only referrers. Public Germany postcode centroids use GeoNames (CC BY 4.0); country points use Natural Earth (public domain). Private household addresses are never sent to a geocoding provider.
