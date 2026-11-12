import datetime

def get_holiday_info(today: datetime.date = None):
    if today is None:
        today = datetime.date.today()
    
    month, day = today.month, today.day
    
    # Thanksgiving (Fourth Thursday of November)
    if month == 11:
        first_day = datetime.date(today.year, 11, 1)
        first_thu_offset = (3 - first_day.weekday()) % 7
        fourth_thu = 1 + first_thu_offset + 21
        if day == fourth_thu:
            return {
                "name": "Thanksgiving",
                "color": 0xD35400,
                "emoji": "🦃",
                "title_prefix": "Happy Thanksgiving",
                "quote": "Gratitude turns what we have into enough.",
                "joke": "Why did the turkey join the band? Because it had the drumsticks!"
            }

    # Christmas (Dec 24 - Dec 26)
    if month == 12 and 24 <= day <= 26:
        return {
            "name": "Christmas",
            "color": 0xC0392B,
            "emoji": "🎄",
            "title_prefix": "Merry Christmas",
            "quote": "May your days be merry and bright.",
            "joke": "What do you call an obnoxious reindeer? Caribou-t rude!"
        }

    # New Year's Eve / Day (Dec 31 - Jan 1)
    if (month == 12 and day == 31) or (month == 1 and day == 1):
        return {
            "name": "New Year",
            "color": 0xF1C40F,
            "emoji": "✨",
            "title_prefix": "Happy New Year",
            "quote": "Cheers to a new year and another chance for us to get it right.",
            "joke": "What does a ghost wear to a New Year's Eve party? A boo-tiful tuxedo!"
        }

    # Halloween (Oct 25 - Oct 31)
    if month == 10 and 25 <= day <= 31:
        return {
            "name": "Halloween",
            "color": 0xE67E22,
            "emoji": "🎃",
            "title_prefix": "Spooky Morning",
            "quote": "There is magic in the night when pumpkins glow in the dark.",
            "joke": "Why don't skeletons fight each other? They don't have the guts!"
        }

    # Default / Standard Day
    return {
        "name": "Normal",
        "color": 0x3498DB,
        "emoji": "🌅",
        "title_prefix": "Daily Morning Briefing",
        "quote": None,
        "joke": None
    }
