from collections import Counter
from datetime import date
import math
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson


def score_grid(home,away):
    if not all(math.isfinite(v) and 0<=v<=30 for v in (home,away)): raise ValueError('Invalid or unsupported goal intensity')
    n=max(12,int(poisson.ppf(1-1e-12,max(home,away)))+1) if max(home,away)>0 else 12
    grid=np.outer(poisson.pmf(np.arange(n),home),poisson.pmf(np.arange(n),away))
    if 1-grid.sum()>1e-8: raise ValueError('Unresolved score-grid tail')
    return grid/grid.sum()


def fit_model(rows,cutoff,half_life=240.,penalty=2.):
    cutoff=str(cutoff)[:10]
    rows=[r for r in rows if r['date']<cutoff]
    if len(rows)<10: raise ValueError('Insufficient history')
    teams=sorted({r[k] for r in rows for k in ['home','away']});ids={t:i for i,t in enumerate(teams)};n=len(teams)
    home=np.array([ids[r['home']] for r in rows]);away=np.array([ids[r['away']] for r in rows])
    hg=np.array([r['hg'] for r in rows]);ag=np.array([r['ag'] for r in rows])
    age=np.array([(date.fromisoformat(cutoff)-date.fromisoformat(r['date'])).days for r in rows])
    weight=np.exp(-np.log(2)*age/half_life)
    def objective(x):
        attack=x[2:2+n];defence=x[2+n:]
        eh=x[0]+x[1]+attack[home]+defence[away];ea=x[0]+attack[away]+defence[home]
        lh=np.exp(eh);la=np.exp(ea)
        loss=np.sum(weight*(lh-hg*eh+la-ag*ea))+penalty*np.sum(x[2:]**2)
        rh=weight*(lh-hg);ra=weight*(la-ag)
        grad=np.zeros_like(x);grad[0]=(rh+ra).sum();grad[1]=rh.sum()
        grad[2:2+n]=np.bincount(home,rh,minlength=n)+np.bincount(away,ra,minlength=n)+2*penalty*attack
        grad[2+n:]=np.bincount(away,rh,minlength=n)+np.bincount(home,ra,minlength=n)+2*penalty*defence
        return loss,grad
    x=np.zeros(2+2*n);x[0]=math.log(max(.1,ag.mean()));x[1]=math.log(max(.1,hg.mean())/max(.1,ag.mean()))
    result=minimize(objective,x,jac=True,method='L-BFGS-B',bounds=[(-2,2),(-1,1)]+[(-2,2)]*(2*n),options={'maxiter':400})
    if not result.success or not np.isfinite(result.fun): raise ValueError('Goal model did not converge')
    counts=Counter(r[k] for r in rows for k in ['home','away'])
    return {'teams':teams,'coefficients':result.x.tolist(),'counts':dict(counts),'cutoff':cutoff,'n':len(rows),'scale':1.,'half_life':half_life,'penalty':penalty}


def rates(model,home,away):
    if any(model['counts'].get(t,0)<10 for t in [home,away]): raise ValueError('Insufficient team history')
    ids={t:i for i,t in enumerate(model['teams'])}
    if home not in ids or away not in ids: raise ValueError('Unresolved team history')
    h,a=ids[home],ids[away];x=model['coefficients'];n=len(ids)
    lh=math.exp(x[0]+x[1]+x[2+h]+x[2+n+a]);la=math.exp(x[0]+x[2+a]+x[2+n+h])
    return lh,la
