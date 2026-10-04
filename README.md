# AFS Karte

Private volunteer maps for AFSer.de, with public code hosted on GitHub Pages.

- `/sending/`: open Sending homeinterviews with urgent highlighting, nearby suggestions, an approximate area and the real AFSer task page for signing up.
- `/hopees/`: active outgoing participants, grouped by destination country, with source links. No foreign home addresses.
- `/hostees/`: active hosted students, shown around their public postal locality.
- `/families/`: active host families and open Hosting homeinterviews.

Visitors first choose a city/postcode or their chapter. The browser requests only that chapter's records. The chapter switcher and **Alle Komitees** explicitly change the scope. The same preference applies to all four pages.

## Hosting and private data

The `docs/` directory is the complete public GitHub Pages deployment. It contains code and map-library assets only. Its real route directories work when opened directly or refreshed.

The separately versioned MCP service lives locally in `mcp/`. Its code repository is separate from this website. The full authenticated source payloads, cookies, private access codes, local geodata caches and SQLite dataset remain in the ignored `.private-data/` directory. Private files use owner-only permissions. Never add either directory to this website repository.

GitHub Pages cannot run the data service. A read-only local HTTP bridge serves anonymous projections through an HTTPS tunnel for remote volunteers. The bridge requires expiring bearer access codes; every invitation can be revoked locally. The complete raw dataset has no HTTP or MCP access endpoint. The public website contains neither AFSer credentials nor private invitations.

The local computer must be awake and online. The supplied Cloudflare Quick Tunnel creates a temporary endpoint, which changes after restart and has no uptime guarantee. A stable production installation requires a named tunnel or an equivalent authenticated private connection. The dataset still stays on this computer.

## Local use

See `mcp/README.md` for the local data service. With its dependencies installed:

```sh
cd mcp
uv run afser-data --data-dir ../.private-data sync
uv run afser-data --data-dir ../.private-data serve --frontend-dir ../docs
```

Create an invitation locally, then open the resulting `.private-data/invite.html` file:

```sh
uv run afser-data --data-dir ../.private-data invite \
  --website http://127.0.0.1:8765 \
  --endpoint http://127.0.0.1:8765 \
  --label owner
```

The invite carries the access code in the URL fragment, which is removed immediately after the website reads it. It is not sent to GitHub in an HTTP request or included in an AFSer source link. The browser keeps the code only for its current session; records are not stored by the website.

For remote service preparation/start/status, use `scripts/start_remote.py --help`. Open the private invite locally to retrieve the latest volunteer link; do not paste it into public issues or repository files. Use `afser-data revoke-all` to invalidate access.

## Source updates and coverage

The importer uses AFSer's authenticated read-only APIs and the actual interview task board. It checks complete list responses, follows board pagination, partitions capped student lists by chapter, and verifies interview signup availability. It retains original source payloads locally and prints only counts and safe error codes. All active, cancelled and historical source fields returned by supported endpoints are retained in raw storage; only current relevant records enter the maps.

Automatic updates run every 30 minutes while the local service runs. A sync activates atomically only after all required sources validate. If AFSer authentication expires or source structure changes, the previous complete snapshot remains available. Optional unsupported historical API pagination is reported separately in the local coverage manifest, rather than presented as complete.

AFSer's own login and permissions apply to every linked source page. The map does not register a volunteer for an interview automatically. It opens the actual task page where they can join the interview team.

## Development

No npm install or application build is needed. Rebuild the four static route files after editing `docs/index.html`:

```sh
python3 scripts/build_pages.py
python3 -m http.server 5173 --bind 127.0.0.1 --directory docs
```

The private backend has automated tests for source normalization, record privacy, active/chapter filtering, pagination, atomic sync, authentication, CORS, and MCP tools. Browser verification should use isolated synthetic data, not expose national raw data to a model.

## Attribution

Leaflet 1.9.4 (BSD-2-Clause) is vendored with its license. Interactive raster tiles use OpenStreetMap with visible contributor attribution and origin-only referrers. Public Germany postcode centroids use GeoNames (CC BY 4.0); country centroids use Natural Earth (public domain). Private household addresses are never sent to a geocoding provider.
