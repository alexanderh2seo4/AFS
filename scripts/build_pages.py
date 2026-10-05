"""Materialize real route directories for GitHub Pages. No data enters the build."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root/'docs/index.html').read_text()
routes = {
    'sending': ('SENDING · HOMEINTERVIEWS', 'Engagiere dich bei uns!', 'Finde offene Homeinterviews in unserem Komitee und melde dich direkt auf AFSer an.'),
    'awayees': ('SENDING · AWAYEES', 'Unsere Awayees in der Welt.', 'Entdecke, in welche Länder unsere Awayees reisen und wo sie gerade sind.'),
    'hostees': ('HOSTING · HOSTEES', 'Unsere Hostees aus aller Welt.', 'Unsere aktiven Gastschüler*innen – anonymisiert und mit direktem Link zu AFSer.'),
    'families': ('HOSTING · GASTFAMILIEN', 'Wir geben dem Austausch ein Zuhause.', 'Entdecke unsere aktiven Gastfamilien und offenen Homeinterviews in unserem Komitee.'),
}
for route, (eyebrow, title, description) in routes.items():
    folder=root/'docs'/route
    folder.mkdir(exist_ok=True)
    page=source.replace('="assets/','="../assets/').replace('href="./"','href="../"')
    for name in routes:
        page=page.replace('href="'+name+'/"','href="../'+name+'/"')
    page=page.replace('>SENDING · HOMEINTERVIEWS</p>', '>'+eyebrow+'</p>', 1)
    page=page.replace('<h1 id="page-title">Engagiere dich bei uns!</h1>', '<h1 id="page-title">'+title+'</h1>', 1)
    page=page.replace('<p id="page-description">Finde offene Homeinterviews in unserem Komitee und melde dich direkt auf AFSer an.</p>', '<p id="page-description">'+description+'</p>', 1)
    (folder/'index.html').write_text(page)
print('Built four GitHub Pages routes; no dataset included.')
