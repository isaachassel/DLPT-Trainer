"""Transparent interval ladder for practice, not Anki/FSRS or a calibrated memory model."""
from datetime import datetime
from zoneinfo import ZoneInfo

DAY = 86400
LADDER = (1, 3, 7, 14, 30, 60, 120, 180)
RATINGS = ('Again', 'Hard', 'Good', 'Easy')


def day_key(now, zone='America/Los_Angeles'):
    return datetime.fromtimestamp(now, ZoneInfo(zone)).date().isoformat()


def schedule(previous, rating, now, zone='America/Los_Angeles'):
    if rating not in RATINGS:
        raise ValueError('Unknown review rating')
    old = previous or {}
    step = int(old.get('step', -1))
    streak = int(old.get('streak', 0))
    last_success = old.get('last_success_day', '')
    today = day_key(now, zone)
    lapses = int(old.get('lapses', 0))
    if rating == 'Again':
        step, interval, streak, last_success = -1, 600, 0, ''
        lapses += 1
    elif rating == 'Hard':
        step = max(-1, step - 1)
        interval = max(21600, min(7 * DAY, int(old.get('interval_seconds', 0) / 2)))
        streak, last_success = 0, ''
    else:
        step = min(len(LADDER) - 1, step + (2 if rating == 'Easy' else 1))
        interval = LADDER[step] * DAY
        if today != last_success:
            streak += 1
            last_success = today
    return {'step': step, 'interval_seconds': interval, 'due': now + interval,
            'reviews': int(old.get('reviews', 0)) + 1, 'lapses': lapses, 'streak': streak,
            'last_success_day': last_success, 'last_rating': rating, 'last_review': now,
            'introduced_day': old.get('introduced_day') or today}


def mastery(card):
    if not card:
        return 'New'
    if card['last_rating'] in ('Again', 'Hard'):
        return 'Shaky'
    if card['interval_seconds'] >= 30 * DAY and card['streak'] >= 3:
        return 'Well known'
    return 'Learning'


def due_label(due, now):
    seconds = max(0, round(due - now))
    if not seconds:
        return 'Due now'
    if seconds < 3600:
        return f'in {max(1, round(seconds / 60))} min'
    if seconds < DAY:
        count = max(1, round(seconds / 3600))
        return f'in {count} hour' + ('s' if count != 1 else '')
    count = max(1, round(seconds / DAY))
    return f'in {count} day' + ('s' if count != 1 else '')
