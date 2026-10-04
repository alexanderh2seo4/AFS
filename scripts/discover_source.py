"""Read-only source discovery. Private HTML/cookies are written locally, never printed."""
import html.parser
import http.cookiejar
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.private-data'
BASE = 'https://www.afser.de'

class Metadata(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.hidden = {}; self.links = []; self.scripts = []; self.anchor = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'input' and a.get('type') == 'hidden': self.hidden[a.get('name')] = a.get('value', '')
        if tag == 'a': self.anchor = [a.get('href', ''), '']
        if tag == 'script' and a.get('src'): self.scripts.append(a['src'])
    def handle_data(self, data):
        if self.anchor is not None: self.anchor[1] += data
    def handle_endtag(self, tag):
        if tag == 'a' and self.anchor is not None:
            self.links.append(self.anchor); self.anchor = None

def connect():
    PRIVATE.mkdir(exist_ok=True, mode=0o700)
    cookies = http.cookiejar.MozillaCookieJar(str(PRIVATE / 'cookies.txt'))
    if Path(cookies.filename).exists(): cookies.load(ignore_discard=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    opener.addheaders = [('User-Agent', 'AFS-Karte/1.0 (authorized local read-only data sync)')]
    home = opener.open(BASE + '/', timeout=40).read().decode('utf-8')
    if 'name="password"' in home:
        meta = Metadata(); meta.feed(home)
        form = dict(meta.hidden, username='Alexander Kluge', password=(ROOT / '.afser-password').read_text().strip())
        home = opener.open(BASE + '/', urllib.parse.urlencode(form).encode(), timeout=40).read().decode('utf-8')
        if 'name="password"' in home: raise RuntimeError('AFSer authentication failed; no dataset was fetched.')
    cookies.save(ignore_discard=True); os.chmod(cookies.filename, 0o600)
    return opener, home

if __name__ == '__main__':
    import sys
    opener, home = connect()
    path = sys.argv[1] if len(sys.argv)>1 else '/'
    document = home if path=='/' else opener.open(urllib.parse.urljoin(BASE,path), timeout=60).read().decode('utf-8')
    target = PRIVATE / ('discovery-' + str(abs(hash(path))) + '.html')
    target.write_text(document); os.chmod(target, 0o600)
    meta = Metadata(); meta.feed(document)
    # Structural URLs and navigation only; no national record text.
    navigation = [[url, text.strip()] for url,text in meta.links if any(x in url.lower() for x in ['sending','hosting','interview','hopee','hostee','gastfamil','komitee'])]
    print(json.dumps({'authenticated':True,'saved':str(target),'scripts':meta.scripts,'navigation':navigation}, ensure_ascii=False))
