"""
All the words BOT understands, in English, Hindi, Kannada and Telugu.

Edit this file to teach BOT new words. Matching rules:
  * English words must match as whole words ("up" will not match "update").
  * Hindi / Kannada / Telugu words match at the START of a word, so a stem like
    "बढ़ा" matches "बढ़ाओ", "बढ़ा दो", "बढ़ाना". Use stems to cover many verb forms.
  * Case, punctuation, nukta (ज़ vs ज) and invisible joiners are ignored.

If BOT says it did not understand you, check pc-agent/unmatched.txt to see the
exact text your phone heard, then add those words here.
"""

# --------------------------------------------------------------------------
# Verbs and helper words used by commands that take an argument
# --------------------------------------------------------------------------

OPEN = [
    "open", "launch", "start", "run",
    "खोल", "ओपन", "चालू", "शुरू",
    "ತೆರೆ", "ತೆರೆಯ", "ಓಪನ್", "ಶುರು",
    "తెరువు", "తెరవ", "తెరిచ", "ఓపెన్", "ప్రారంభించ",
]

CLOSE = [
    "close", "quit", "exit", "kill",
    "बंद", "क्लोज",
    "ಮುಚ್ಚ", "ಕ್ಲೋಸ್", "ಬಂದ್",
    "మూసి", "మూసే", "మూయ", "క్లోజ్", "బంద్",
]

SEARCH = [
    "search", "search for", "look up",
    "सर्च", "खोज", "ढूंढ", "ढूँढ",
    "ಹುಡುಕ", "ಸರ್ಚ್",
    "వెత", "సెర్చ్", "శోధించ",
]

PLAY = [
    "play",
    "प्ले", "चला", "बजा",
    "ಪ್ಲೇ", "ಹಾಕು",
    "ప్లే", "పెట్టు",
]

# Indian-language "type/write" verbs. (English uses "type ..." / "write ..." at the start.)
TYPE = [
    "टाइप", "लिख",
    "ಟೈಪ್", "ಬರೆ",
    "టైప్", "రాయ", "రాసి",
]

# Small words removed when working out WHAT to open / search / play.
FILLERS = [
    # English
    "the", "a", "an", "on", "in", "for", "and", "to", "of", "please", "app",
    "application", "my", "me", "can", "you", "could", "now", "about", "website",
    # Hindi
    "पर", "में", "को", "का", "की", "के", "से", "करो", "कर", "दो", "करें", "कीजिए",
    "जरा", "ज़रा", "प्लीज", "प्लीज़", "एप", "ऐप", "और", "वेबसाइट",
    # Kannada
    "ಮಾಡು", "ಮಾಡಿ", "ಮಾಡಿರಿ", "ಅನ್ನು", "ನಲ್ಲಿ", "ಅಲ್ಲಿ", "ದಯವಿಟ್ಟು", "ಸ್ವಲ್ಪ", "ಆ್ಯಪ್", "ಆಪ್", "ಮತ್ತು",
    # Telugu
    "చేయి", "చేయండి", "చెయ్యి", "చేసి", "లో", "ని", "ను", "దయచేసి", "కొంచెం", "యాప్", "మరియు",
]

# Helper verbs stripped from text you ask BOT to type.
TYPE_FILLERS = ["करो", "कर", "दो", "कीजिए", "ಮಾಡು", "ಮಾಡಿ", "చేయి", "చేయండి", "చెయ్యి"]

# "play music" on its own = press play; "play <something>" = search YouTube.
MUSIC = [
    "music", "song", "songs", "video", "videos",
    "गाना", "गाने", "गीत", "संगीत", "म्यूजिक", "म्यूज़िक",
    "ಹಾಡು", "ಹಾಡುಗಳು", "ಸಾಂಗ್", "ಮ್ಯೂಸಿಕ್",
    "పాట", "పాటలు", "సాంగ్", "మ్యూజిక్",
]

# --------------------------------------------------------------------------
# Apps and websites
#   launch:  what Windows should open (first one that works wins)
#   process: exe name used by "close <app>" (None = closing not allowed)
#   menu:    name typed into the Start menu if launching fails
# --------------------------------------------------------------------------

APPS = {
    "chrome": {
        "label": "Chrome", "launch": ["chrome.exe"], "process": "chrome.exe", "menu": "chrome",
        "names": ["chrome", "google chrome", "क्रोम", "ಕ್ರೋಮ್", "క్రోమ్"],
    },
    "edge": {
        "label": "Edge", "launch": ["msedge.exe"], "process": "msedge.exe", "menu": "edge",
        "names": ["edge", "microsoft edge", "एज ब्राउज़र", "माइक्रोसॉफ्ट एज", "ಎಡ್ಜ್", "ఎడ్జ్"],
    },
    "notepad": {
        "label": "Notepad", "launch": ["notepad.exe"], "process": "Notepad.exe", "menu": "notepad",
        "names": ["notepad", "note pad", "नोटपैड", "नोट पैड", "ನೋಟ್‌ಪ್ಯಾಡ್", "ನೋಟ್ ಪ್ಯಾಡ್", "నోట్‌ప్యాడ్", "నోట్ ప్యాడ్"],
    },
    "calculator": {
        "label": "Calculator", "launch": ["calc.exe"], "process": "CalculatorApp.exe", "menu": "calculator",
        "names": ["calculator", "calc", "कैलकुलेटर", "कैलक्यूलेटर", "ಕ್ಯಾಲ್ಕುಲೇಟರ್", "ಕ್ಯಾಲ್ಕ್ಯುಲೇಟರ್",
                  "కాలిక్యులేటర్", "క్యాలిక్యులేటర్", "కాల్క్యులేటర్"],
    },
    "explorer": {
        "label": "File Explorer", "launch": ["explorer.exe"], "process": None, "menu": "file explorer",
        "names": ["file explorer", "explorer", "files", "this pc", "my computer",
                  "फाइल एक्सप्लोरर", "फाइल्स", "फाइल", "ಫೈಲ್ ಎಕ್ಸ್‌ಪ್ಲೋರರ್", "ಫೈಲ್ಸ್", "ಫೈಲ್",
                  "ఫైల్ ఎక్స్‌ప్లోరర్", "ఫైల్స్", "ఫైల్"],
    },
    "settings": {
        "label": "Settings", "launch": ["ms-settings:"], "process": "SystemSettings.exe", "menu": "settings",
        "names": ["settings", "setting", "सेटिंग", "ಸೆಟ್ಟಿಂಗ್", "సెట్టింగ్"],
    },
    "task_manager": {
        "label": "Task Manager", "launch": ["taskmgr.exe"], "process": "Taskmgr.exe", "menu": "task manager",
        "names": ["task manager", "टास्क मैनेजर", "ಟಾಸ್ಕ್ ಮ್ಯಾನೇಜರ್", "టాస్క్ మేనేజర్"],
    },
    "paint": {
        "label": "Paint", "launch": ["mspaint.exe"], "process": "mspaint.exe", "menu": "paint",
        "names": ["paint", "ms paint", "पेंट", "ಪೇಂಟ್", "పెయింట్"],
    },
    "terminal": {
        "label": "Command Prompt", "launch": ["cmd.exe"], "process": None, "menu": "command prompt",
        "names": ["command prompt", "cmd", "terminal", "कमांड प्रॉम्प्ट", "टर्मिनल", "ಕಮಾಂಡ್ ಪ್ರಾಂಪ್ಟ್",
                  "ಟರ್ಮಿನಲ್", "కమాండ్ ప్రాంప్ట్", "టెర్మినల్"],
    },
    "vscode": {
        "label": "VS Code",
        "launch": [r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
                   r"%ProgramFiles%\Microsoft VS Code\Code.exe"],
        "process": "Code.exe", "menu": "visual studio code",
        "names": ["vs code", "vscode", "visual studio code", "वीएस कोड", "ವಿಎಸ್ ಕೋಡ್", "వీఎస్ కోడ్"],
    },
    "word": {
        "label": "Word", "launch": ["winword.exe"], "process": "WINWORD.EXE", "menu": "word",
        "names": ["word", "ms word", "microsoft word", "वर्ड", "ವರ್ಡ್", "వర్డ్"],
    },
    "excel": {
        "label": "Excel", "launch": ["excel.exe"], "process": "EXCEL.EXE", "menu": "excel",
        "names": ["excel", "ms excel", "एक्सेल", "ಎಕ್ಸೆಲ್", "ఎక్సెల్"],
    },
    "powerpoint": {
        "label": "PowerPoint", "launch": ["powerpnt.exe"], "process": "POWERPNT.EXE", "menu": "powerpoint",
        "names": ["powerpoint", "power point", "ppt", "पावरपॉइंट", "पावर पॉइंट", "ಪವರ್‌ಪಾಯಿಂಟ್", "పవర్‌పాయింట్"],
    },
    "spotify": {
        "label": "Spotify", "launch": ["spotify:"], "process": "Spotify.exe", "menu": "spotify",
        "names": ["spotify", "स्पॉटिफाई", "स्पोटिफाई", "ಸ್ಪಾಟಿಫೈ", "స్పాటిఫై"],
    },
    "whatsapp": {
        "label": "WhatsApp", "launch": ["whatsapp:"], "process": "WhatsApp.exe", "menu": "whatsapp",
        "names": ["whatsapp", "whats app", "व्हाट्सएप", "व्हाट्सऐप", "वॉट्सऐप", "ವಾಟ್ಸಾಪ್", "ವಾಟ್ಸ್‌ಆ್ಯಪ್",
                  "వాట్సాప్", "వాట్సప్"],
    },
    "camera": {
        "label": "Camera", "launch": ["microsoft.windows.camera:"], "process": "WindowsCamera.exe", "menu": "camera",
        "names": ["camera", "कैमरा", "ಕ್ಯಾಮೆರಾ", "కెమెరా"],
    },
}

SITES = {
    "youtube": {"label": "YouTube", "url": "https://www.youtube.com",
                "names": ["youtube", "you tube", "यूट्यूब", "यू ट्यूब", "ಯೂಟ್ಯೂಬ್", "ಯುಟ್ಯೂಬ್", "యూట్యూబ్", "యుట్యూబ్"]},
    "google": {"label": "Google", "url": "https://www.google.com",
               "names": ["google", "गूगल", "ಗೂಗಲ್", "గూగుల్"]},
    "gmail": {"label": "Gmail", "url": "https://mail.google.com",
              "names": ["gmail", "email", "mail", "जीमेल", "ईमेल", "ಜಿಮೇಲ್", "ಇಮೇಲ್", "జీమెయిల్", "ఈమెయిల్"]},
    "github": {"label": "GitHub", "url": "https://github.com",
               "names": ["github", "git hub", "गिटहब", "ಗಿಟ್‌ಹಬ್", "గిట్‌హబ్"]},
    "instagram": {"label": "Instagram", "url": "https://www.instagram.com",
                  "names": ["instagram", "insta", "इंस्टाग्राम", "इंस्टा", "ಇನ್‌ಸ್ಟಾಗ್ರಾಮ್", "ಇನ್ಸ್ಟಾ",
                            "ఇన్‌స్టాగ్రామ్", "ఇన్‌స్టా"]},
    "facebook": {"label": "Facebook", "url": "https://www.facebook.com",
                 "names": ["facebook", "फेसबुक", "ಫೇಸ್‌ಬುಕ್", "ఫేస్‌బుక్"]},
    "linkedin": {"label": "LinkedIn", "url": "https://www.linkedin.com",
                 "names": ["linkedin", "linked in", "लिंक्डइन", "ಲಿಂಕ್ಡ್‌ಇನ್", "లింక్డ్‌ఇన్"]},
    "maps": {"label": "Google Maps", "url": "https://maps.google.com",
             "names": ["maps", "google maps", "map", "मैप्स", "मैप", "ಮ್ಯಾಪ್", "మ్యాప్"]},
    "amazon": {"label": "Amazon", "url": "https://www.amazon.in",
               "names": ["amazon", "अमेज़न", "अमेजन", "ಅಮೆಜಾನ್", "అమెజాన్"]},
    "flipkart": {"label": "Flipkart", "url": "https://www.flipkart.com",
                 "names": ["flipkart", "फ्लिपकार्ट", "ಫ್ಲಿಪ್‌ಕಾರ್ಟ್", "ఫ్లిప్‌కార్ట్"]},
    "netflix": {"label": "Netflix", "url": "https://www.netflix.com",
                "names": ["netflix", "नेटफ्लिक्स", "ನೆಟ್‌ಫ್ಲಿಕ್ಸ್", "నెట్‌ఫ్లిక్స్"]},
    "chatgpt": {"label": "ChatGPT", "url": "https://chatgpt.com",
                "names": ["chatgpt", "chat gpt", "चैटजीपीटी", "चैट जीपीटी", "ಚಾಟ್‌ಜಿಪಿಟಿ", "చాట్‌జీపీటీ"]},
    "claude": {"label": "Claude", "url": "https://claude.ai",
               "names": ["claude", "क्लॉड", "ಕ್ಲಾಡ್", "క్లాడ్"]},
}

# --------------------------------------------------------------------------
# Simple commands (no argument)
#   Each rule is a list of word-groups; a rule matches when EVERY group has
#   at least one word in what you said. Rules with more groups win, then
#   higher "priority", then longer matched words.
# --------------------------------------------------------------------------

VOLUME = ["volume", "sound", "audio", "आवाज", "आवाज़", "वॉल्यूम", "वोल्यूम", "साउंड",
          "ವಾಲ್ಯೂಮ್", "ವಾಲ್ಯೂಂ", "ಸೌಂಡ್", "ಧ್ವನಿ", "ಶಬ್ದ",
          "వాల్యూమ్", "వాల్యూం", "సౌండ్", "శబ్ద"]
MORE = ["up", "increase", "raise", "more", "higher", "बढ़ा", "तेज", "ज्यादा", "ज़्यादा", "अप",
        "ಹೆಚ್ಚ", "ಜಾಸ್ತಿ", "ಅಪ್", "పెంచ", "ఎక్కువ", "అప్"]
LESS = ["down", "decrease", "lower", "reduce", "less", "कम", "घटा", "धीमा", "धीरे", "डाउन",
        "ಕಡಿಮೆ", "ತಗ್ಗಿಸ", "ಇಳಿಸ", "ಡೌನ್", "తగ్గ", "తక్కువ", "డౌన్"]
OFF = ["off", "बंद", "ऑफ", "ಆಫ್", "ಬಂದ್", "ఆఫ్", "బంద్"]
PC = ["computer", "pc", "laptop", "system", "कंप्यूटर", "कम्प्यूटर", "पीसी", "लैपटॉप", "सिस्टम",
      "ಕಂಪ್ಯೂಟರ್", "ಪಿಸಿ", "ಲ್ಯಾಪ್‌ಟಾಪ್", "ಸಿಸ್ಟಮ್", "కంప్యూటర్", "పీసీ", "ల్యాప్‌టాప్", "సిస్టమ్"]
SHUTDOWN = ["shutdown", "shut down", "power off", "switch off", "शटडाउन", "शट डाउन",
            "ಶಟ್‌ಡೌನ್", "ಶಟ್ ಡೌನ್", "షట్‌డౌన్", "షట్ డౌన్"]
RESTART = ["restart", "reboot", "रीस्टार्ट", "ರೀಸ್ಟಾರ್ಟ್", "రీస్టార్ట్"]
CANCEL = ["cancel", "abort", "stop", "रद्द", "कैंसल", "कैंसिल", "रोको",
          "ಕ್ಯಾನ್ಸಲ್", "ರದ್ದು", "ನಿಲ್ಲಿಸ", "క్యాన్సిల్", "రద్దు", "ఆపు", "ఆపండి"]
SCROLL = ["scroll", "स्क्रॉल", "ಸ್ಕ್ರೋಲ್", "ಸ್ಕ್ರಾಲ್", "స్క్రోల్"]
UP = ["up", "ऊपर", "अप", "ಮೇಲೆ", "ಮೇಲಕ್ಕೆ", "ಅಪ್", "పైకి", "అప్"]
DOWN = ["down", "नीचे", "डाउन", "ಕೆಳಗೆ", "ಕೆಳಕ್ಕೆ", "ಡೌನ್", "కిందకి", "కిందికి", "క్రిందికి", "డౌన్"]
WINDOW = ["window", "विंडो", "ವಿಂಡೋ", "విండో"]
THIS = ["this", "it", "इसे", "इसको", "ಇದನ್ನು", "ಇದು", "దీన్ని", "ఇది"]
TAB = ["tab", "टैब", "ಟ್ಯಾಬ್", "ట్యాబ్"]
CHANGE = ["change", "बदल", "ಬದಲಿಸ", "ಬದಲಾಯಿಸ", "మార్చ"]

SIMPLE = [
    {"intent": "volume_up", "rules": [[VOLUME, MORE], [["louder", "turn it up"]]]},
    {"intent": "volume_down", "rules": [[VOLUME, LESS], [["quieter", "softer", "turn it down"]]]},
    {"intent": "mute", "rules": [[["mute", "unmute", "म्यूट", "ಮ್ಯೂಟ್", "మ్యూట్"]], [VOLUME, OFF]]},
    # next/previous come before play_pause so "play next song" = next track
    {"intent": "next_track", "rules": [[["next", "skip", "अगला", "अगले", "नेक्स्ट", "ಮುಂದಿನ", "ನೆಕ್ಸ್ಟ್",
                                          "తర్వాత", "తరువాత", "నెక్స్ట్"]]]},
    {"intent": "previous_track", "rules": [[["previous", "prev", "पिछला", "पिछले", "प्रीवियस", "ಹಿಂದಿನ",
                                              "ಪ್ರೀವಿಯಸ್", "మునుపటి", "ప్రీవియస్"]]]},
    {"intent": "play_pause", "rules": [[["play", "pause", "resume", "प्ले", "पॉज", "पोज", "रोको", "चलाओ", "बजाओ",
                                          "ಪ್ಲೇ", "ಪಾಜ್", "ಪಾಸ್", "ప్లే", "పాజ్"]]]},
    {"intent": "lock", "rules": [[["lock", "लॉक", "ಲಾಕ್", "లాక్"]]]},
    {"intent": "shutdown", "confirm": True, "rules": [[SHUTDOWN], [PC, OFF]]},
    {"intent": "restart", "confirm": True, "rules": [[RESTART]]},
    {"intent": "sleep", "confirm": True, "rules": [[["sleep", "स्लीप", "ಸ್ಲೀಪ್", "స్లీప్"]]]},
    {"intent": "cancel_shutdown", "rules": [[CANCEL, SHUTDOWN + RESTART]]},
    {"intent": "screenshot", "rules": [[["screenshot", "screen shot", "स्क्रीनशॉट", "स्क्रीन शॉट",
                                          "ಸ್ಕ್ರೀನ್‌ಶಾಟ್", "ಸ್ಕ್ರೀನ್ ಶಾಟ್", "స్క్రీన్‌షాట్", "స్క్రీన్ షాట్"]]]},
    {"intent": "show_desktop", "rules": [[["show desktop", "minimize all", "go to desktop", "desktop",
                                            "डेस्कटॉप", "ಡೆಸ್ಕ್‌ಟಾಪ್", "డెస్క్‌టాప్"]]]},
    {"intent": "minimize", "rules": [[["minimize", "minimise", "मिनिमाइज", "ಮಿನಿಮೈಸ್", "మినిమైజ్"]]]},
    {"intent": "maximize", "rules": [[["maximize", "maximise", "full screen", "fullscreen", "मैक्सिमाइज",
                                        "फुल स्क्रीन", "ಮ್ಯಾಕ್ಸಿಮೈಸ್", "ಫುಲ್ ಸ್ಕ್ರೀನ್", "మ్యాక్సిమైజ్", "ఫుల్ స్క్రీన్"]]]},
    {"intent": "close_tab", "priority": 1, "rules": [[CLOSE, TAB]]},
    {"intent": "close_window", "rules": [[CLOSE, WINDOW + THIS]]},
    {"intent": "switch_window", "rules": [[["switch window", "next window", "alt tab", "switch",
                                             "स्विच", "ಸ್ವಿಚ್", "స్విచ్"]], [WINDOW, CHANGE]]},
    {"intent": "new_tab", "rules": [[["new tab", "नया टैब", "न्यू टैब", "ಹೊಸ ಟ್ಯಾಬ್", "ನ್ಯೂ ಟ್ಯಾಬ್",
                                       "కొత్త ట్యాబ్", "న్యూ ట్యాబ్"]]]},
    {"intent": "refresh", "rules": [[["refresh", "reload", "रिफ्रेश", "ರಿಫ್ರೆಶ್", "రిఫ్రెష్"]]]},
    {"intent": "go_back", "rules": [[["go back", "back", "पीछे", "बैक", "ಹಿಂದೆ", "ಬ್ಯಾಕ್", "వెనక్కి", "బ్యాక్"]]]},
    {"intent": "copy", "rules": [[["copy", "कॉपी", "ಕಾಪಿ", "కాపీ"]]]},
    {"intent": "paste", "rules": [[["paste", "पेस्ट", "ಪೇಸ್ಟ್", "పేస్ట్"]]]},
    {"intent": "undo", "rules": [[["undo", "अनडू", "ಅನ್‌ಡೂ", "అన్‌డూ"]]]},
    {"intent": "select_all", "rules": [[["select all", "सब सेलेक्ट", "सेलेक्ट ऑल", "ಸೆಲೆಕ್ಟ್ ಆಲ್", "సెలెక్ట్ ఆల్"]]]},
    {"intent": "enter", "rules": [[["enter", "press enter", "एंटर", "ಎಂಟರ್", "ఎంటర్"]]]},
    {"intent": "scroll_up", "rules": [[SCROLL, UP]]},
    {"intent": "scroll_down", "rules": [[SCROLL, DOWN]]},
    {"intent": "double_click", "rules": [[["double click", "डबल क्लिक", "ಡಬಲ್ ಕ್ಲಿಕ್", "డబుల్ క్లిక్"]]]},
    {"intent": "right_click", "rules": [[["right click", "राइट क्लिक", "ರೈಟ್ ಕ್ಲಿಕ್", "రైట్ క్లిక్"]]]},
    {"intent": "click", "rules": [[["click", "क्लिक", "ಕ್ಲಿಕ್", "క్లిక్"]]]},
    {"intent": "help", "rules": [[["help", "what can you do", "commands", "मदद", "हेल्प",
                                    "ಸಹಾಯ", "ಹೆಲ್ಪ್", "సహాయం", "హెల్ప్"]]]},
    {"intent": "greeting", "rules": [[["hi", "hello", "hey", "नमस्ते", "हेलो", "हैलो",
                                        "ನಮಸ್ಕಾರ", "ಹಲೋ", "నమస్కారం", "హలో"]]]},
]
