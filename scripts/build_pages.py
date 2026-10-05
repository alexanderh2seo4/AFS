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

RETURNEES_REDIRECT = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex">
  <meta http-equiv="refresh" content="0; url=../../returnees/">
  <link rel="canonical" href="../../returnees/">
  <title>AFS Returnees</title>
  <script>location.replace(new URL('../../returnees/', location.href).href);</script>
</head>
<body>
  <p>Weiterleitung zu <a href="../../returnees/">Returnees</a>...</p>
</body>
</html>
"""

CONTACT_REDIRECT = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex">
  <meta http-equiv="refresh" content="0; url=../../Kontaktformular/">
  <link rel="canonical" href="../../Kontaktformular/">
  <title>Kontaktformular · AFS Karte</title>
  <script>location.replace(new URL('../../Kontaktformular/', location.href).href);</script>
</head>
<body>
  <p>Weiterleitung zum <a href="../../Kontaktformular/">Kontaktformular</a>...</p>
</body>
</html>
"""

for route, (eyebrow, title, description) in routes.items():
    folder=root/'docs'/route
    folder.mkdir(exist_ok=True)
    page=source.replace('="assets/','="../assets/').replace('href="./"','href="../"')
    for name in routes:
        page=page.replace('href="'+name+'/"','href="../'+name+'/"')
    page=page.replace('href="returnees/"','href="../returnees/"')
    page=page.replace('href="Kontaktformular/"','href="../Kontaktformular/"')
    page=page.replace('>SENDING · HOMEINTERVIEWS</p>', '>'+eyebrow+'</p>', 1)
    page=page.replace('<h1 id="page-title">Engagiere dich bei uns!</h1>', '<h1 id="page-title">'+title+'</h1>', 1)
    page=page.replace('<p id="page-description">Finde offene Homeinterviews in unserem Komitee und melde dich direkt auf AFSer an.</p>', '<p id="page-description">'+description+'</p>', 1)
    (folder/'index.html').write_text(page)

    ret_folder = folder / 'returnees'
    ret_folder.mkdir(exist_ok=True)
    (ret_folder / 'index.html').write_text(RETURNEES_REDIRECT)

    contact_folder = folder / 'Kontaktformular'
    contact_folder.mkdir(exist_ok=True)
    (contact_folder / 'index.html').write_text(CONTACT_REDIRECT)

print('Built four map routes; the returnee dataset page is maintained separately.')
