"""Run with:  python -m unittest -v test_matcher"""
import unittest

from matcher import match

CASES = [
    # (what the phone heard, expected intent, expected target-or-arg or None)
    # ---- English
    ("open chrome", "open_app", "chrome"),
    ("Open Notepad.", "open_app", "notepad"),
    ("launch spotify", "open_app", "spotify"),
    ("open youtube", "open_site", "youtube"),
    ("youtube", "open_site", "youtube"),
    ("open github.com", "open_url", "https://github.com"),
    ("open obs studio", "start_menu", "obs studio"),
    ("close chrome", "close_app", "chrome"),
    ("close this window", "close_window", None),
    ("close the tab", "close_tab", None),
    ("volume up", "volume_up", None),
    ("turn the volume down", "volume_down", None),
    ("mute", "mute", None),
    ("search python tutorials", "google_search", "python tutorials"),
    ("google weather in bangalore", "google_search", "weather bangalore"),
    ("play arijit singh songs on youtube", "youtube_search", "arijit singh songs"),
    ("open youtube and search lofi music", "youtube_search", "lofi music"),
    ("play despacito", "youtube_search", "despacito"),
    ("play", "play_pause", None),
    ("pause the music", "play_pause", None),
    ("next song", "next_track", None),
    ("next window", "switch_window", None),
    ("type Hello World", "type_text", "Hello World"),
    ("lock the computer", "lock", None),
    ("shutdown", "shutdown", None),
    ("turn off the computer", "shutdown", None),
    ("cancel shutdown", "cancel_shutdown", None),
    ("restart", "restart", None),
    ("take a screenshot", "screenshot", None),
    ("scroll down", "scroll_down", None),
    ("scroll up", "scroll_up", None),
    ("new tab", "new_tab", None),
    ("open new tab", "new_tab", None),
    ("show desktop", "show_desktop", None),
    ("double click", "double_click", None),
    ("help", "help", None),
    ("hide the cursor", "bubble_off", None),
    ("turn off the bubble", "bubble_off", None),
    ("show the cursor", "bubble_on", None),
    ("कर्सर बंद करो", "bubble_off", None),
    ("कर्सर चालू करो", "bubble_on", None),
    ("ಕರ್ಸರ್ ಆಫ್ ಮಾಡು", "bubble_off", None),
    ("ಕರ್ಸರ್ ಆನ್ ಮಾಡು", "bubble_on", None),
    ("కర్సర్ ఆఫ్ చేయి", "bubble_off", None),
    ("కర్సర్ ఆన్ చేయి", "bubble_on", None),
    ("how much battery is left", "battery", None),
    ("बैटरी कितनी है", "battery", None),
    ("ಬ್ಯಾಟರಿ ಎಷ್ಟು ಇದೆ", "battery", None),
    ("బ్యాటరీ ఎంత ఉంది", "battery", None),
    # ---- Hindi
    ("क्रोम खोलो", "open_app", "chrome"),
    ("यूट्यूब खोलो", "open_site", "youtube"),
    ("नोटपैड खोल दो", "open_app", "notepad"),
    ("आवाज़ बढ़ाओ", "volume_up", None),
    ("आवाज कम करो", "volume_down", None),
    ("आवाज़ बंद करो", "mute", None),
    ("क्रोम बंद करो", "close_app", "chrome"),
    ("कंप्यूटर बंद करो", "shutdown", None),
    ("कंप्यूटर लॉक करो", "lock", None),
    ("गूगल पर मौसम सर्च करो", "google_search", "मौसम"),
    ("यूट्यूब पर अरिजीत सिंह के गाने चलाओ", "youtube_search", "अरिजीत सिंह गाने"),
    ("स्क्रीनशॉट लो", "screenshot", None),
    ("नमस्ते लिखो", "type_text", "नमस्ते"),
    ("अगला गाना", "next_track", None),
    ("नीचे स्क्रॉल करो", "scroll_down", None),
    # ---- Kannada
    ("ಕ್ರೋಮ್ ತೆರೆ", "open_app", "chrome"),
    ("ಯೂಟ್ಯೂಬ್ ಓಪನ್ ಮಾಡು", "open_site", "youtube"),
    ("ಯುಟ್ಯೂಬ ತೆರೆ", "open_site", "youtube"),  # misspelt -> fuzzy match
    ("ವಾಲ್ಯೂಮ್ ಹೆಚ್ಚಿಸು", "volume_up", None),
    ("ಸೌಂಡ್ ಕಡಿಮೆ ಮಾಡು", "volume_down", None),
    ("ಗೂಗಲ್ ನಲ್ಲಿ ಹವಾಮಾನ ಹುಡುಕು", "google_search", "ಹವಾಮಾನ"),
    ("ಸ್ಕ್ರೀನ್‌ಶಾಟ್ ತೆಗೆ", "screenshot", None),
    ("ಕಂಪ್ಯೂಟರ್ ಲಾಕ್ ಮಾಡು", "lock", None),
    ("ಕ್ರೋಮ್ ಮುಚ್ಚು", "close_app", "chrome"),
    # ---- Telugu
    ("క్రోమ్ ఓపెన్ చేయి", "open_app", "chrome"),
    ("నోట్‌ప్యాడ్ తెరువు", "open_app", "notepad"),
    ("సౌండ్ పెంచు", "volume_up", None),
    ("వాల్యూమ్ తగ్గించు", "volume_down", None),
    ("గూగుల్ లో వాతావరణం వెతుకు", "google_search", "వాతావరణం"),
    ("లాక్ చేయి", "lock", None),
    ("కంప్యూటర్ ఆఫ్ చేయి", "shutdown", None),
    ("స్క్రీన్‌షాట్ తీసుకో", "screenshot", None),
    # ---- nonsense
    ("blah blah", None, None),
    ("", None, None),
]


class MatcherTest(unittest.TestCase):
    def test_cases(self):
        for heard, intent, detail in CASES:
            with self.subTest(heard=heard):
                m = match(heard)
                if intent is None:
                    self.assertIsNone(m)
                    continue
                self.assertIsNotNone(m, "no match")
                self.assertEqual(m.intent, intent)
                if detail is not None:
                    self.assertIn(detail, (m.target, m.arg))


if __name__ == "__main__":
    unittest.main()
