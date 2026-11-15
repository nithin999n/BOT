# BOT 🤖: control your PC with your voice

Hold the button on your Android phone, speak a command in **English, हिंदी, ಕನ್ನಡ or తెలుగు**,
and your Windows PC does it over your home Wi-Fi.

```
📱 BOT app (Android)  ──── Wi-Fi / WebSocket + PIN ────►  💻 BOT agent (Python, Windows)
 hold mic → speech-to-text                                 understand → open apps, keys, mouse…
```

## 1. Start the PC agent

Needs Python 3.10+.

```bat
cd pc-agent
start_bot.bat
```

The window shows the **IP address**, **port** and **PIN**.
The first time, Windows Firewall asks for permission. Tick **Private networks** and click **Allow**.

## 2. Install the app on your phone

1. On GitHub, open **Actions → Build Android APK**, open the latest run, and download **BOT-apk**.
   (Or push a tag like `v0.1.0`; the APK then shows up under **Releases**, which you can open directly on the phone.)
2. Copy `BOT.apk` to your phone and open it. Allow "install unknown apps" when Android asks.
3. Open BOT, enter the IP, port and PIN from the PC, and allow microphone access.

The phone and PC must be on the **same Wi-Fi**.

## 3. Talk to it

| Language | Examples |
|---|---|
| English | open chrome · volume up · search weather in bangalore · play arijit singh on youtube · type hello · close chrome · screenshot · lock the computer · shutdown |
| हिंदी | क्रोम खोलो · आवाज़ बढ़ाओ · आवाज़ बंद करो · गूगल पर मौसम सर्च करो · कंप्यूटर लॉक करो |
| ಕನ್ನಡ | ಕ್ರೋಮ್ ತೆರೆ · ವಾಲ್ಯೂಮ್ ಹೆಚ್ಚಿಸು · ಗೂಗಲ್ ನಲ್ಲಿ ಹವಾಮಾನ ಹುಡುಕು · ಸ್ಕ್ರೀನ್‌ಶಾಟ್ ತೆಗೆ |
| తెలుగు | క్రోమ్ ఓపెన్ చేయి · సౌండ్ పెంచు · గూగుల్ లో వాతావరణం వెతుకు · లాక్ చేయి |

Shutdown, restart and sleep ask **"Are you sure?"** on the phone first.
Say **"cancel shutdown"** within 15 seconds to stop one.
Moving the mouse into a screen corner stops any running mouse or keyboard action (safety stop).

## Teach it new words

Everything BOT understands is in [`pc-agent/phrases.py`](pc-agent/phrases.py).
When BOT doesn't understand you, the exact text your phone heard is saved to `pc-agent/unmatched.txt`.
Add those words to `phrases.py`, then check nothing broke:

```bat
cd pc-agent
python -m unittest -v test_matcher
```

## Project layout

```
pc-agent/       Python agent: bot_agent.py (server), matcher.py (understanding),
                actions.py (doing), phrases.py (vocabulary), test_matcher.py
mobile-app/     Flutter app: lib/main.dart. The android/ folder is generated in CI.
.github/        GitHub Actions workflow that builds BOT.apk
```

## Roadmap

- [x] Phase 1: fixed voice commands in 4 languages, PIN pairing, APK build
- [ ] Phase 2: find the PC automatically on Wi-Fi (no typing the IP), QR pairing, start with Windows
- [ ] Phase 3: on-screen "ghost cursor" so you can watch BOT work; click buttons by name (UI Automation)
- [ ] Phase 4: AI brain for free-form multi-step tasks
