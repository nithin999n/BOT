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

## Fun & handy extras

- **Pet BOT:** stroke its face and it purrs with hearts 🥰. **Shake your phone** and it gets dizzy 😵.
- **Quick buttons:** Mute, Volume −/+, Play/Pause, Screenshot, Send files, **Wake PC**, plus the big **Lock PC** button.
  (Unlocking isn't possible: Windows only unlocks with your password at the PC.)
- **Wake PC (Wake-on-LAN):** wakes the laptop from sleep when you're on the same Wi-Fi, if its network card supports it.
  The phone learns the PC's address automatically after connecting once.
- **Routines:** say "**good night**" (closes everything, then locks) or "**study mode**" (closes YouTube, opens VS Code).
  Make your own in ⋮ → **Routines**: one command per line, exactly what you'd say.
- **Name & colour:** ⋮ → **Name & colour**. Pink BOT 🎀? The PC bubble cursor changes colour too.
- **Phone ⇄ PC:** ⋮ → **Send files & clipboard**. Photos and files land in `Downloads\BOT`.
  The clipboard works both ways ("My clipboard → PC", "PC clipboard → me").

## BOT in the system tray

Look in the **^** area next to the clock (drag the icon onto the taskbar to keep it visible).
- **Left-click** the BOT icon to show or hide the desktop BOT.
- **Right-click** for: Bring BOT here (it drops in above your mouse) · Desktop BOT · BOT cursor · Walk-away lock ·
  Start with Windows · Show PIN · Open received files · **Quit BOT**.

## BOT on your PC desktop, controllers, health & safety

- **Desktop BOT:** a squishy blue cube-blob with big round black eyes lives in the bottom-right corner.
  - Its eyes follow your mouse. It gets **happy and bouncy while you type**, cheers you on, and asks cute
    questions in speech bubbles ("What are you doing? 👀", "Did you drink water today? 💧").
  - **Click it** and it feels loved: "Do you love me? 🥺". Click again: "Yay!! I love you too! 💖"
  - **Grab it and throw it!** It flies, spins and bounces, and gets dizzy after a hard throw (the phone BOT too).
  - It yawns when you're idle, sleeps after 5 minutes, and says "welcome back" when you return.
  - It sweats when the CPU is busy, looks worried on low battery, and sparkles while charging.
  - The blue bubble cursor flies out of it. Hide it from the tray, ⋮ → *BOT on PC desktop*, or say "hide the desktop bot".
  - **Care (⋮ → *Take care of BOT 🍪*):** food, happiness and a level that grow as you look after it.
    Feed it cookies, play **chase** (catch it with your mouse), start a **25-minute focus** timer, see
    **today's report**, and pick an **outfit** (bow, sunglasses, party hat and crown unlock at levels 2–5).
  - **Hungry BOT:** when its tummy gets low, it says "I'm hungry…" and a 🍪 **cookie pops up somewhere on the screen**.
    BOT can't stop looking at it. Drag the cookie onto BOT (puppy eyes: "Gimme gimme! 🤤") or just click it,
    and BOT munches it happily. A minute or two later, with a full tummy, it yawns and asks
    **"Can I sleep?"**: *Yes, sleep 😴* = a 4-minute nap (click it to wake it up early),
    *No, stay with me 🥺* = it stays awake with you for 15 minutes. No answer = it dozes off.
  - It **answers back**: some questions have buttons, and BOT remembers your answers.
  - It **dances** when music plays, plays **peek-a-boo** from the screen edge, and has day and night moods.
    It reminds you to drink water and stretch, and shows a **daily report** at 9 PM.
  - **Drop a file on BOT** and it swallows it and sends it to your phone (saved in *Download/BOT*).
  - Every now and then it begs for pats with puppy eyes 🥺. Ignore it for 10 seconds and it cries; click it to make up.
  - **Throw it too many times** and it gets angry, says "I'm going! You're being too hard on me 😤" and
    leaves. It comes back sulking and asks for a sorry. Tap the *Sorry* button, say "sorry", or use the Care page.
- **Control → Air mouse:** hold the pad and point your phone like a TV remote. Tap to click, and use ◀ ▶ for slides.
- **Control → Gamepad:** a landscape joystick (WASD or arrows) plus Jump/E/F/Q/R/Shift/Ctrl/Esc/Tab/Enter.
  Every key can be held, and the keys are sent as hardware key presses, so games notice them.
- **PC health:** the chip under BOT shows CPU, RAM and battery. Tap it for gauges. BOT's face follows the PC's mood.
- **Alerts:** "Battery low", "Download finished", and "Someone unlocked your PC while you were away".
  Alerts that happen while the app is closed show up as **"While you were away…"** next time.
- **Walk-away lock** (⋮ → *Walk-away lock*, off by default): when your phone leaves the Wi-Fi
  for 1–10 minutes, BOT locks the PC. It never locks while someone is using the keyboard or mouse.

## Smart mode: click anything & chain steps (free, offline)

BOT reads the words on your screen with Windows' built-in text reader (OCR), so you can click **anything that has a name**:

| Say | What happens |
|---|---|
| "select Gmail" · "click Sign in" · "जीमेल पर क्लिक करो" · "Gmail ಮೇಲೆ ಕ್ಲಿಕ್ ಮಾಡು" · "Gmail పై క్లిక్ చేయి" | finds the word, then the bubble glides there and clicks |
| "go to the **top right** and select Gmail" · "click Gmail at the bottom left" | picks the match in that area (top / bottom / left / right / corners / middle) |
| "double click Recycle Bin" · "right click Downloads" | double / right click |
| "open chrome **and** go to gmail **and** click compose" | runs the steps one after another (also *then*, और, फिर, ಮತ್ತು, ನಂತರ, మరియు …) |

| "in the text box say hello" · "type here hello" · "reply saying I'll call later" | types the text into the box you're in |
| "come down a little" · "go up a lot" · "नीचे जाओ" | scrolls a little / normal / a lot |
| "send it" · "delete it" · "delete it permanently" | presses Enter / Delete / Shift+Delete, **after your safety word** |
| "close notepad" · "close all notepads" | closes one window / every window of that app |
| "click that" · "open it" | clicks where the mouse is / opens the selected item |

When you say **click / select / go to / navigate to** something, BOT always clicks it on screen.
It never turns that into a built-in command like restart or shutdown.
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
