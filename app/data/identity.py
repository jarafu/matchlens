# Explicit aliases only. Unresolved names are withheld, never guessed by fuzzy match.
ALIASES={'Wolverhampton Wanderers FC':'Wolverhampton Wanderers FC','Brighton & Hove Albion FC':'Brighton & Hove Albion FC',
         'Manchester City FC':'Manchester City FC','Tottenham Hotspur FC':'Tottenham Hotspur FC',
         'FC Bayern München':'Bayern München','Borussia Dortmund':'Borussia Dortmund',
         'Paris Saint-Germain FC':'Paris Saint-Germain FC'}


def resolve(name,known):
    if name in known: return name
    candidate=ALIASES.get(name)
    return candidate if candidate in known else None
