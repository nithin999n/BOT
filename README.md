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

### Start BOT automatically with Windows (optional)

Double-click **`enable_autostart.bat`**. BOT then runs hidden in the background every time you log in.

| | |
|---|---|
| See the PIN / check it's running | `python autostart.py status` |
| Stop it | `python autostart.py stop` |
| Turn autostart off | double-click `disable_autostart.bat` |
| See what it heard and did | open `pc-agent/bot.log` |

## 2. Install the app on your phone

1. On GitHub, open **Actions → Build Android APK**, open the latest run, and download **BOT-apk**.
   (Or push a tag like `v0.1.0`; the APK then shows up under **Releases**, which you can open directly on the phone.)
2. Copy `BOT.apk` to your phone and open it. Allow "install unknown apps" when Android asks.
3. Open BOT. It **finds your PC on Wi-Fi automatically**. Tap your PC, enter the PIN, and allow microphone access.
   If your router later gives the PC a new IP, the app finds it again by itself.

The phone and PC must be on the **same Wi-Fi**. If auto-find doesn't work on your network,
type the IP under "Manual address".

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

## BOT's face, cursor and remote control

- **The face:** BOT is a glowing blue robot face. **Hold it** to talk, **tap it** to see a random mood.
  It falls asleep when the PC is offline, thinks while working, and smiles when a task is done.
  On the same network, **its eyes follow your PC mouse**. While BOT works, they follow its bubble.
- **The bubble cursor:** when BOT clicks or works on the PC, a **blue bubble with a pointer** glides there first.
  - **To cancel:** move your mouse or press **Esc** while the bubble is moving. BOT won't click.
  - **To turn it off or on:** use the app menu → *BOT cursor on PC*, or say "hide the cursor" / "show the cursor"
    (कर्सर बंद करो · ಕರ್ಸರ್ ಆಫ್ ಮಾಡು · కర్సర్ ఆఫ్ చేయి).
- **Screen:** a live view of the PC screen. Tap = click, double-tap = double-click, long-press = right-click,
  pinch = zoom. Use **Low** quality on mobile data.
- **Touchpad:** the phone becomes a touchpad and keyboard. Move with 1 finger, tap to click, scroll with 2 fingers,
  and 2-finger tap to right-click.

## Smart mode: click anything & chain steps (free, offline)

BOT reads the words on your screen with Windows' built-in text reader (OCR), so you can click **anything that has a name**:

| Say | What happens |
|---|---|
| "select Gmail" · "click Sign in" · "जीमेल पर क्लिक करो" · "Gmail ಮೇಲೆ ಕ್ಲಿಕ್ ಮಾಡು" · "Gmail పై క్లిక్ చేయి" | finds the word, then the bubble glides there and clicks |
| "go to the **top right** and select Gmail" · "click Gmail at the bottom left" | picks the match in that area (top / bottom / left / right / corners / middle) |
| "double click Recycle Bin" · "right click Downloads" | double / right click |
| "open chrome **and** go to gmail **and** click compose" | runs the steps one after another (also *then*, और, फिर, ಮತ್ತು, ನಂತರ, మరియు …) |

If the word isn't on screen yet (a page still loading), BOT keeps looking for up to 8 seconds.
Icons without text can't be clicked by name. Use the **Screen** page and tap them instead.

## "Do anything" tasks (optional paid AI brain)

Built-in commands, like "open chrome", run instantly and for free. For **anything else**, such as
"go to the top right and select Gmail" or "open my Downloads folder and sort by date",
BOT asks **Claude** (Anthropic's AI). Claude looks at your screen and tells BOT where to click and what to type,
step by step, and you watch the blue bubble do it.

1. Create an API key at https://console.anthropic.com (Settings → API Keys) and add some credit.
2. Double-click **`pc-agent\set_api_key.bat`** and paste the key. It's saved only in `pc-agent\config.json` on your PC.
3. Talk to BOT as usual, from the home screen or from the **Screen** page (hold the little face in the corner).

- **Cost:** a short task (3–6 steps) is usually a few US cents. Each reply shows an estimate, e.g. *(≈ $0.04)*.
  The model is `claude-opus-5-5` by default. To use a cheaper one, set `"ai_model": "claude-sonnet-5-5"` in `config.json`.
- **Stopping it:** tap **Stop** in the app, say "stop", or at the PC **move the mouse or press Esc**.
- **Be aware:** this is your real PC, not a sandbox. Claude is told to treat text on screen as information, not orders,
  never to type passwords or card details, and to ask for your safety word before risky steps. Still, keep an eye on it
  when it works in email, banking or other important accounts.

## Safety word

The first time you connect, the app asks you to choose a **safety word**. BOT asks for it (say it or type it)
before anything that **deletes, sends, shares, posts, uploads, pays or uninstalls**, both when your request
sounds like that and whenever the AI is about to take such a step. The PC stores only a scrambled (hashed) form of it,
never the word itself. Three wrong tries cancel the task. Change it from the ⋮ menu → *Change safety word*.

## Use BOT outside home (Tailscale)

1. Install **Tailscale** (free) on the PC: https://tailscale.com/download. Sign in.
2. Install **Tailscale** on the phone from the Play Store. Sign in with the **same account** and turn it on.
3. Connect to BOT once at home. The app learns the PC's Tailscale address by itself
   (you can see it under ⚙ → *Tailscale address of the PC*).
4. That's it. Away from home, the app tries Wi-Fi first and then goes through Tailscale. The status chip shows 🌐 *outside*.

The PC must be **on and awake**. BOT keeps it awake while it's charging. Also set
*Control Panel → Power Options → Choose what closing the lid does → Plugged in: Do nothing*
if you close the lid.

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
- [x] Phase 2: find the PC automatically on Wi-Fi, start with Windows, fixed signing key (APK updates install in place)
- [x] Phase 3: robot face with moods and mouse-tracking eyes, blue bubble cursor (cancel with mouse or Esc, on/off switch)
- [x] Phase 4: live screen view and touchpad + keyboard
- [x] Phase 5: use from outside home via Tailscale
- [x] Phase 6: AI brain for any task (Claude computer use), talk from the Screen page, safety word
- [ ] Next: routines ("good morning" = several actions), more languages
