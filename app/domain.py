from datetime import datetime, timezone


def now(): return datetime.now(timezone.utc)
def stamp(): return now().isoformat()
def parse_time(value):
    dt = datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError("Timezone is required")
    return dt.astimezone(timezone.utc)
