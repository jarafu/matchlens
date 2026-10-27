import numpy as np

MARKETS = {
    'over15': ('Over 1.5 goals','At least two goals in the match'),
    'under45': ('Under 4.5 goals','Four goals or fewer'),
    'home05': ('Home team to score','Home team over 0.5 goals'),
    'away05': ('Away team to score','Away team over 0.5 goals'),
    'dc_1x': ('Home or draw','Double chance · 1X'),
    'dc_x2': ('Away or draw','Double chance · X2'),
    'dc_12': ('Either team to win','Double chance · 12'),
    'btts_yes': ('Both teams score — Yes','Both teams score at least once'),
    'btts_no': ('Both teams score — No','At least one team does not score'),
}


def probabilities(grid):
    h,a=np.indices(grid.shape)
    masks={'over15':h+a>=2,'under45':h+a<=4,'home05':h>=1,'away05':a>=1,
           'dc_1x':h>=a,'dc_x2':a>=h,'dc_12':h!=a,'btts_yes':(h>=1)&(a>=1),'btts_no':(h==0)|(a==0)}
    return {k:float(grid[m].sum()) for k,m in masks.items()}


def settle(market,hg,ag):
    if hg is None or ag is None: return None
    if not isinstance(hg,int) or not isinstance(ag,int) or hg<0 or ag<0: raise ValueError('Invalid regulation score')
    outcomes={'over15':hg+ag>=2,'under45':hg+ag<=4,'home05':hg>=1,'away05':ag>=1,
              'dc_1x':hg>=ag,'dc_x2':ag>=hg,'dc_12':hg!=ag,'btts_yes':hg>0 and ag>0,'btts_no':hg==0 or ag==0}
    return outcomes[market]
