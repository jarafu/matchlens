import math


def assess_value(p,odds):
    if not math.isfinite(p) or not 0<=p<=1: raise ValueError('Invalid probability')
    fair=1/p if p else None
    if odds is None: return {'label':'Value unavailable','expected_return':None,'fair_odds':fair}
    if not math.isfinite(odds) or odds<=1: raise ValueError('Invalid decimal odds')
    ev=p*odds-1
    return {'label':'Positive estimated value' if ev>0 else 'Negative value','expected_return':ev,'fair_odds':fair,'offered_odds':odds}


def rank(items):
    def key(item):
        value=item.get('value',{}).get('expected_return')
        return (-item['probability'],-value if value is not None else float('inf'),item.get('market',''))
    return sorted(items,key=key)
