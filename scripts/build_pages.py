"""Materialize real route directories for GitHub Pages. No data enters the build."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root/'docs/index.html').read_text()
for route in ['sending','hopees','hostees','families']:
    folder=root/'docs'/route
    folder.mkdir(exist_ok=True)
    page=source.replace('="assets/','="../assets/').replace('href="./"','href="../"')
    for name in ['sending','hopees','hostees','families']:
        page=page.replace('href="'+name+'/"','href="../'+name+'/"')
    (folder/'index.html').write_text(page)
print('Built four GitHub Pages routes; no dataset included.')
