from datetime import date, timedelta
import numpy as np
from app.model.poisson import fit_model, rates, score_grid
from app.model.markets import MARKETS, probabilities, settle


def metrics(ps,ys):
    p=np.clip(np.array(ps,dtype=float),1e-10,1-1e-10);y=np.array(ys,dtype=float)
    if not len(p): return {'n':0,'brier':None,'logloss':None,'ece':None,'bands':{}}
    bins=np.minimum((p*10).astype(int),9);bands={};ece=0.
    for b in np.unique(bins):
        mask=bins==b;n=int(mask.sum());expected=float(p[mask].mean());actual=float(y[mask].mean())
        ece+=n/len(p)*abs(expected-actual)
        # Wilson interval for the empirical hit rate, not a probability guarantee.
        z=1.96;center=(actual+z*z/(2*n))/(1+z*z/n);half=z*np.sqrt(actual*(1-actual)/n+z*z/(4*n*n))/(1+z*z/n)
        bands[str(b)]={'n':n,'expected':expected,'observed':actual,'interval':[max(0,float(center-half)),min(1,float(center+half))]}
    return {'n':len(p),'brier':float(np.mean((p-y)**2)),'logloss':float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),'ece':float(ece),'bands':bands}


def activation(report):
    return bool(report.get('n',0)>=200 and report.get('calibration_n',200)>=200 and report.get('training_n',300)>=300 and
                report.get('ece',1)<=.08 and report.get('brier',1)<=report.get('baseline_brier',0) and
                report.get('logloss',99)<=report.get('baseline_logloss',0))


def split_history(rows):
    rows=sorted(rows,key=lambda r:r['date']);dates=sorted({r['date'] for r in rows})
    if len(dates)<5: raise ValueError('Insufficient chronological dates')
    c1=dates[max(1,int(len(dates)*.6))];c2=dates[max(2,int(len(dates)*.8))]
    return ([r for r in rows if r['date']<c1],[r for r in rows if c1<=r['date']<c2],[r for r in rows if r['date']>=c2])


def evaluate_model(rows):
    train,cal,test=split_history(rows)
    if len(train)<300 or len(cal)<200 or len(test)<200: raise ValueError('Need at least 300 training, 200 calibration and 200 test matches')
    calibration=[];next_refit='';model=None
    for r in cal:
        if model is None or r['date']>=next_refit:
            model=fit_model([v for v in rows if v['date']<r['date']],r['date'])
            next_refit=(date.fromisoformat(r['date'])+timedelta(days=30)).isoformat()
        try: lh,la=rates(model,r['home'],r['away'],as_of=r['date'])
        except ValueError: continue
        calibration.append((lh+la,r['hg']+r['ag']))
    if len(calibration)<200: raise ValueError('Fewer than 200 eligible calibration matches')
    scale=float(np.clip(sum(y for _,y in calibration)/sum(p for p,_ in calibration),.65,1.35))
    forecasts={k:[] for k in MARKETS};outcomes={k:[] for k in MARKETS};baselines={k:[] for k in MARKETS}
    # Refit every 30 days using only strictly prior results; calibration remains frozen.
    next_refit='';current=None;training=[];base={}
    for r in test:
        if current is None or r['date']>=next_refit:
            training=[v for v in rows if v['date']<r['date']]
            current=fit_model(training,r['date'])
            next_refit=(date.fromisoformat(r['date'])+timedelta(days=30)).isoformat()
            base={k:float(np.mean([settle(k,v['hg'],v['ag']) for v in training])) for k in MARKETS}
        try: lh,la=rates(current,r['home'],r['away'],as_of=r['date'])
        except ValueError: continue
        p=probabilities(score_grid(lh*scale,la*scale))
        for k in MARKETS:
            forecasts[k].append(p[k]);outcomes[k].append(int(settle(k,r['hg'],r['ag'])));baselines[k].append(base[k])
    reports={}
    for k in MARKETS:
        report=metrics(forecasts[k],outcomes[k]);baseline=metrics(baselines[k],outcomes[k])
        report.update(baseline_brier=baseline['brier'],baseline_logloss=baseline['logloss'],calibration_n=len(calibration),training_n=len(train))
        report['enabled']=activation(report) if report['n'] else False;reports[k]=report
    cutoff=(date.fromisoformat(max(r['date'] for r in rows))+timedelta(days=1)).isoformat()
    final=fit_model(rows,cutoff);final['scale']=scale
    return final,{'markets':reports,'training_n':len(train),'calibration_n':len(calibration),'test_n':len(test),'test_start':min(r['date'] for r in test),'test_end':max(r['date'] for r in test),'scale':scale,'policy_version':'v2-team-freshness-2026-10-27'}
