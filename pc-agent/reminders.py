"""
Understand "remind me at 5 to call mom", "remind me in 10 minutes to drink water",
"remind me to call mom tomorrow at 9 am", "मुझे 5 बजे याद दिलाना" ... and "my birthday is 12 March".
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

WORD_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
            "forty": 40, "forty five": 45, "fifty": 50, "half an": 0.5, "half a": 0.5}
UNITS = {"second": 1 / 60, "sec": 1 / 60, "minute": 1, "min": 1, "hour": 60, "hr": 60, "day": 1440,
         "मिनट": 1, "घंटे": 60, "घंटा": 60, "ನಿಮಿಷ": 1, "ಗಂಟೆ": 60, "నిమిష": 1, "గంట": 60}
TRIGGERS = re.compile(r"remind me|set (a )?reminder|reminder|याद दिला|याद करा|ನೆನಪಿಸ|ನೆನಪು ಮಾಡ|గుర్తు చేయ|గుర్తుచేయ", re.I)
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                       "september", "october", "november", "december"], 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS.update({"sept": 9})


def is_reminder(text: str) -> bool:
    return bool(TRIGGERS.search(text))


def parse(text: str, now: datetime | None = None) -> tuple[datetime, str] | None:
    """-> (when, what) or None if no time was found."""
    now = now or datetime.now()
    t = " " + text.lower().replace(".", "").replace(",", " ") + " "
    when = None
    used: list[str] = []
    # "in 10 minutes", "in an hour", "in half an hour", "10 मिनट में"
    m = re.search(r"\bin\s+(\d+(?:\.\d+)?|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                  r"fifteen|twenty|thirty|forty five|forty|fifty|half an|half a)\s*(seconds?|secs?|minutes?|mins?|"
                  r"hours?|hrs?|days?)\b", t)
    if m:
        n = float(m.group(1)) if m.group(1)[0].isdigit() else WORD_NUM[m.group(1)]
        unit = re.sub(r"s$", "", m.group(2))
        when = now + timedelta(minutes=n * UNITS.get(unit, 1))
        used.append(m.group(0))
    else:
        m = re.search(r"(\d+)\s*(मिनट|घंटे|घंटा|ನಿಮಿಷ\S*|ಗಂಟೆ\S*|నిమిష\S*|గంట\S*)\s*(में|ಲ್ಲಿ|ದಲ್ಲಿ|లో)?", t)
        if m and not re.search(r"बजे|ಗಂಟೆಗೆ|గంటలకు", m.group(0)):
            unit = next((u for u in UNITS if m.group(2).startswith(u)), "minute")
            when = now + timedelta(minutes=int(m.group(1)) * UNITS[unit])
            used.append(m.group(0))
    if when is None:
        # "at 5", "at 5:30 pm", "at 17:45", "5 बजे", "5 ಗಂಟೆಗೆ", "at noon"
        tomorrow = bool(re.search(r"\btomorrow\b|कल|ನಾಳೆ|రేపు", t))
        if tomorrow:
            used.append("tomorrow")
        m = re.search(r"\b(?:at|by|@)\s*(\d{1,2})(?::|\s)?(\d{2})?\s*(am|pm|a m|p m)?\b", t) \
            or re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a m|p m|o'?clock)\b", t) \
            or re.search(r"(\d{1,2})(?::(\d{2}))?\s*(बजे|ಗಂಟೆಗೆ|గంటలకు)", t)
        noon = re.search(r"\b(?:at\s+)?(noon|midnight)\b", t)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2) or 0)
            ampm = (m.group(3) or "").replace(" ", "")
            if ampm in ("बजे", "ಗಂಟೆಗೆ", "గంటలకు"):  # "o'clock": no am / pm
                ampm = ""
            used.append(m.group(0))
            if hour > 23 or minute > 59:
                return None
            evening = re.search(r"\b(evening|night|tonight|afternoon)\b|शाम|रात|ಸಂಜೆ|ರಾತ್ರಿ|సాయంత్రం|రాత్రి", t)
            morning = re.search(r"\bmorning\b|सुबह|ಬೆಳಿಗ್ಗೆ|ಬೆಳಗ್ಗೆ|ఉదయం", t)
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            elif not ampm or ampm.startswith("o"):
                if evening and hour < 12:
                    hour += 12
                elif not morning and hour <= 12:
                    # no am/pm: the next time that hour comes round (5 -> 5 PM if it's already past 5 AM)
                    cands = [now.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)]
                    if hour < 12:
                        cands.append(cands[0].replace(hour=hour + 12))
                    if tomorrow:
                        when = (cands[0] if 7 <= hour <= 11 else cands[-1]) + timedelta(days=1)
                    else:
                        future = [c for c in cands if c > now]
                        when = min(future) if future else cands[0] + timedelta(days=1)
            if when is None:
                when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if tomorrow:
                    when += timedelta(days=1)
                elif when <= now:
                    when += timedelta(days=1)
        elif noon:
            used.append(noon.group(0))
            when = now.replace(hour=12 if noon.group(1) == "noon" else 0, minute=0, second=0, microsecond=0)
            if tomorrow or when <= now:
                when += timedelta(days=1)
    if when is None:
        return None
    # what to remind: the rest of the sentence
    what = t
    for u in used:
        what = what.replace(u, " ")
    what = TRIGGERS.sub(" ", what)
    what = re.sub(r"(मुझे|मुझको|मेरे लिए|ನನಗೆ|నాకు)", " ", what)
    what = re.sub(r"\s(ना|नी|ನಾ|ಿ|ు)\s*$", " ", what)
    what = re.sub(r"\b(please|hey|bot|can you|could you|me|set|a|for|tomorrow|today|tonight|in the|this|"
                  r"morning|evening|afternoon|night|o'?clock)\b", " ", what)
    what = re.sub(r"^\s*(to|about|that)\s+", " ", what.strip())
    what = re.sub(r"\s+(to|about|at|in|that)\s*$", " ", what)
    what = re.sub(r"\s+", " ", what).strip(" -:")
    what = re.sub(r"^(to|about|that)\s+", "", what)
    return when, (what[:1].upper() + what[1:]) if what else "Your reminder ⏰"


def parse_birthday(text: str) -> str | None:
    """'my birthday is 12 March' / 'March 12th' / '12/03' -> 'MM-DD'."""
    t = text.lower().replace(",", " ")
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s+)?([a-z]{3,9})", t)
    if m and m.group(2) in MONTHS:
        day, month = int(m.group(1)), MONTHS[m.group(2)]
    else:
        m = re.search(r"([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?\b", t)
        if m and m.group(1) in MONTHS:
            month, day = MONTHS[m.group(1)], int(m.group(2))
        else:
            m = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})\b", t)
            if not m:
                return None
            day, month = int(m.group(1)), int(m.group(2))  # India: day first
    try:
        datetime(2000, month, day)
    except ValueError:
        return None
    return f"{month:02d}-{day:02d}"


def pretty(when: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    clock = when.strftime("%I:%M %p").lstrip("0")
    if when.date() == now.date():
        return f"today at {clock}"
    if when.date() == (now + timedelta(days=1)).date():
        return f"tomorrow at {clock}"
    return when.strftime("%d %b at ") + clock
