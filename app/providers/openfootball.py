import hashlib
import json
import re
from datetime import date
from pathlib import Path
import httpx
from app.providers.base import get_json, ProviderError

COMPETITIONS={'PL':('en.1','Premier League'),'ELC':('en.2','Championship'),'BL1':('de.1','Bundesliga'),'PD':('es.1','La Liga'),'SA':('it.1','Serie A'),'FL1':('fr.1','Ligue 1'),'DED':('nl.1','Eredivisie'),'PPL':('pt.1','Primeira Liga')}


def parse_history(payload,competition,revision):
    matches=payload.get('matches',[])
    if not matches and 'rounds' in payload: matches=[m for r in payload['rounds'] for m in r.get('matches',[])]
    out=[]
    for m in matches:
        try:
            hg,ag=m['score']['ft'];day=date.fromisoformat(m['date']).isoformat();home=m['team1'];away=m['team2']
            if type(hg)!=int or type(ag)!=int or min(hg,ag)<0 or max(hg,ag)>30 or not home or not away or home==away: continue
            identity=f'{competition}|{day}|{home}|{away}'
            out.append({'id':hashlib.sha256(identity.encode()).hexdigest(),'competition':competition,'home':home,'away':away,'date':day,'hg':hg,'ag':ag,'revision':revision})
        except (KeyError,ValueError,TypeError): continue
    return out


def import_history(seasons,competitions,cache_dir=Path('data/history')):
    cache_dir.mkdir(parents=True,exist_ok=True)
    revision_file=cache_dir/'revision.json'
    with httpx.Client(timeout=45,follow_redirects=True) as client:
        if revision_file.exists(): revision=json.loads(revision_file.read_text())['sha']
        else:
            revision=get_json(client,'https://api.github.com/repos/openfootball/football.json/commits/master')['sha']
            revision_file.write_text(json.dumps({'sha':revision}))
        if not re.fullmatch('[0-9a-f]{40}',revision): raise ProviderError('Invalid source revision')
        rows=[];missing=[]
        for competition in competitions:
            if competition not in COMPETITIONS: raise ValueError('Unsupported competition mapping')
            for season in seasons:
                if not re.fullmatch(r'20\d{2}-\d{2}',season): raise ValueError('Invalid season')
                filename=f'{competition}-{season}-{revision}.json';path=cache_dir/filename
                if path.exists(): payload=json.loads(path.read_text())
                else:
                    url=f'https://raw.githubusercontent.com/openfootball/football.json/{revision}/{season}/{COMPETITIONS[competition][0]}.json'
                    try: payload=get_json(client,url)
                    except ProviderError:
                        missing.append(f'{competition}/{season}');continue
                    path.write_text(json.dumps(payload))
                rows.extend(parse_history(payload,competition,revision))
        return rows,{'revision':revision,'missing':missing,'count':len(rows)}
