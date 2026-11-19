import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:sensors_plus/sensors_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'air_mouse_page.dart';
import 'care_page.dart';
import 'connection.dart';
import 'dashboard_page.dart';
import 'face.dart';
import 'find_phone.dart';
import 'gamepad_page.dart';
import 'routines_page.dart';
import 'safety_word.dart';
import 'screen_page.dart';
import 'settings_dialog.dart';
import 'style.dart';
import 'touchpad_page.dart';
import 'transfer.dart';
import 'voice.dart';
import 'world_page.dart';

class Lang {
  const Lang(this.code, this.locale, this.label);
  final String code;
  final String locale;
  final String label;
}

const languages = <Lang>[
  Lang('en', 'en_IN', 'English'),
  Lang('hi', 'hi_IN', 'हिंदी'),
  Lang('kn', 'kn_IN', 'ಕನ್ನಡ'),
  Lang('te', 'te_IN', 'తెలుగు'),
];

const examples = <String, List<String>>{
  'Click anything & chain steps (free)': [
    'go to the top right and select Gmail',
    'open chrome and go to gmail and click compose',
    'click Sign in',
    'double click Recycle Bin',
    'open youtube and search lofi songs',
    'come down a little and select Settings',
    'in the text box say hello there',
    'type hello and send it',
    'delete it',
    'close all notepads',
    'जीमेल पर क्लिक करो',
    'Gmail ಮೇಲೆ ಕ್ಲಿಕ್ ಮಾಡು',
    'Gmail పై క్లిక్ చేయి',
  ],
  'English': ['open chrome', 'volume up', 'search cricket score', 'play arijit singh on youtube', 'battery'],
  'हिंदी': ['क्रोम खोलो', 'आवाज़ बढ़ाओ', 'गूगल पर मौसम सर्च करो', 'बैटरी कितनी है', 'कर्सर बंद करो'],
  'ಕನ್ನಡ': ['ಕ್ರೋಮ್ ತೆರೆ', 'ವಾಲ್ಯೂಮ್ ಹೆಚ್ಚಿಸು', 'ಯೂಟ್ಯೂಬ್ ತೆರೆ', 'ಸ್ಕ್ರೀನ್‌ಶಾಟ್', 'ಕರ್ಸರ್ ಆಫ್ ಮಾಡು'],
  'తెలుగు': ['క్రోమ్ ఓపెన్ చేయి', 'సౌండ్ పెంచు', 'గూగుల్ లో వాతావరణం వెతుకు', 'లాక్ చేయి', 'కర్సర్ ఆఫ్ చేయి'],
};

const _tapMoods = [Mood.happy, Mood.wink, Mood.love, Mood.shy, Mood.excited, Mood.surprised];

class LogEntry {
  LogEntry(this.text, {this.mine = false, this.ok = true});
  final String text;
  final bool mine;
  final bool ok;
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with WidgetsBindingObserver {
  final BotConnection conn = BotConnection();
  final Voice voice = Voice();
  StreamSubscription<BotEvent>? _eventSub;

  // Face
  Mood? _flash; // short-lived expression (tap, result…)
  Timer? _flashTimer;
  bool _waiting = false; // command sent, waiting for the PC
  Timer? _waitTimer;
  Timer? _holdTimer;
  bool _fingerDown = false;
  bool _holdFired = false;
  String _bubbleText = '';
  String _progress = '';
  bool _askedForKeyword = false;
  int _poke = 0; // tap = squish
  final _rnd = math.Random();
  // petting (stroke the face) and shaking the phone
  bool _petting = false;
  double _petTravel = 0, _petTick = 0;
  Offset? _lastPetPos;
  StreamSubscription<UserAccelerometerEvent>? _accelSub;
  final List<DateTime> _shakes = [];
  DateTime _lastDizzy = DateTime(2000);

  int _lang = 0;
  final List<LogEntry> _log = [];
  final TextEditingController _input = TextEditingController();

  String get _locale => languages[_lang].locale;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    conn.addListener(_onChange);
    voice.addListener(_onChange);
    voice.onProblem = (m) {
      _say(m);
      _flashMood(Mood.confused);
    };
    _eventSub = conn.events.listen(_onEvent);
    style.addListener(_onChange);
    conn.health.addListener(_onChange);
    conn.nowPlaying.addListener(_onChange);
    loadStyle();
    try {
      _accelSub = userAccelerometerEventStream().listen(_onAccel, onError: (Object _) {});
    } catch (_) {
      // no motion sensor: no shake reaction
    }
    _init();
    voice.init().then((ok) {
      if (!ok) {
        _addLog(
            'Voice is not available (microphone permission denied or no Google speech service). '
            'You can still type commands below.',
            ok: false);
      }
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    conn.removeListener(_onChange);
    voice.removeListener(_onChange);
    style.removeListener(_onChange);
    conn.health.removeListener(_onChange);
    conn.nowPlaying.removeListener(_onChange);
    _accelSub?.cancel();
    _eventSub?.cancel();
    for (final t in [_flashTimer, _waitTimer, _holdTimer]) {
      t?.cancel();
    }
    _input.dispose();
    voice.dispose();
    conn.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      conn.setForeground(true);
      if (conn.link == Link.offline && conn.configured) conn.connect();
    } else if (state == AppLifecycleState.paused) {
      conn.setForeground(false);
    }
  }

  Future<void> _init() async {
    await conn.load();
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    final lang = prefs.getInt('lang') ?? 0;
    setState(() => _lang = (lang >= 0 && lang < languages.length) ? lang : 0);
    if (conn.configured) {
      conn.connect();
    } else {
      _openSettings();
    }
  }

  void _onChange() {
    if (mounted) setState(() {});
  }

  // ------------------------------------------------------------------ mood

  Mood get _mood {
    if (voice.listening) return Mood.listening;
    if (_petting) return Mood.purr;
    final flash = _flash;
    if (flash != null) return flash;
    if (_waiting || conn.busy) return Mood.thinking;
    return switch (conn.link) {
      Link.offline => Mood.sleepy,
      Link.connecting => Mood.thinking,
      Link.online => moodForHealth(conn.health.value), // sweaty / worried / charging / idle
    };
  }

  void _flashMood(Mood m, [Duration d = const Duration(milliseconds: 1800)]) {
    _flashTimer?.cancel();
    setState(() => _flash = m);
    _flashTimer = Timer(d, () {
      if (mounted) setState(() => _flash = null);
    });
  }

  void _tapFace() {
    HapticFeedback.selectionClick();
    final options = _tapMoods.where((m) => m != _flash).toList();
    setState(() => _poke++);
    final m = options[_rnd.nextInt(options.length)];
    _flashMood(m);
    // the little BOT on the PC desktop reacts too
    conn.send({'type': 'pet_react', 'mood': m == Mood.love || m == Mood.shy ? 'love' : (m == Mood.surprised ? 'surprised' : 'happy')});
  }

  void _openControl() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(
            leading: const Icon(Icons.touch_app),
            title: const Text('Touchpad'),
            subtitle: const Text('Your phone screen is a laptop touchpad'),
            onTap: () {
              Navigator.pop(ctx);
              _open(TouchpadPage(conn: conn));
            },
          ),
          ListTile(
            leading: const Icon(Icons.ads_click),
            title: const Text('Air mouse'),
            subtitle: const Text('Point your phone like a TV remote'),
            onTap: () {
              Navigator.pop(ctx);
              _open(AirMousePage(conn: conn));
            },
          ),
          ListTile(
            leading: const Icon(Icons.sports_esports),
            title: const Text('Gamepad'),
            subtitle: const Text('Play PC games with your phone'),
            onTap: () {
              Navigator.pop(ctx);
              _open(GamepadPage(conn: conn));
            },
          ),
        ]),
      ),
    );
  }

  Future<void> _walkawaySettings() async {
    var enabled = conn.walkaway['enabled'] == true;
    var minutes = ((conn.walkaway['minutes'] as num?) ?? 1).toDouble();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setD) => AlertDialog(
          icon: const Icon(Icons.directions_walk),
          title: const Text('Walk-away lock'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('When your phone leaves the Wi-Fi (you walk away), BOT locks your PC. '
                'It never locks while someone is using the keyboard or mouse.'),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Turn on'),
              value: enabled,
              onChanged: (v) => setD(() => enabled = v),
            ),
            Text('Lock after ${minutes.round()} min away'),
            Slider(value: minutes, min: 1, max: 10, divisions: 9, onChanged: (v) => setD(() => minutes = v)),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
          ],
        ),
      ),
    );
    if (ok == true) conn.send({'type': 'set_walkaway', 'enabled': enabled, 'minutes': minutes.round()});
  }

  void _showAlert(String title, String message) {
    HapticFeedback.heavyImpact();
    _flashMood(Mood.surprised, const Duration(seconds: 2));
    _addLog('🔔 $title: $message', ok: !title.contains('unlocked'));
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      behavior: SnackBarBehavior.floating,
      duration: const Duration(seconds: 6),
      content: Text('$title\n$message'),
    ));
  }

  Widget _healthChip() {
    final h = conn.health.value;
    if (h == null || !conn.online) return const SizedBox.shrink();
    final battery = h['battery'];
    final text = 'CPU ${h['cpu']}% · RAM ${h['ram']}%'
        '${battery == null ? '' : ' · 🔋$battery%${h['charging'] == true ? '⚡' : ''}'}';
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: ActionChip(
        avatar: const Icon(Icons.monitor_heart, size: 16),
        label: Text(text, style: const TextStyle(fontSize: 12)),
        visualDensity: VisualDensity.compact,
        onPressed: () => _open(DashboardPage(conn: conn)),
      ),
    );
  }

  /// Music playing on the PC: title + ⏮ ⏯ ⏭
  Widget _musicCard() {
    final m = conn.nowPlaying.value;
    if (m == null || !conn.online || m['playing'] != true || '${m['title'] ?? ''}'.isEmpty) {
      return const SizedBox.shrink();
    }
    final artist = '${m['artist'] ?? ''}';
    return Padding(
      padding: const EdgeInsets.only(top: 6, left: 24, right: 24),
      child: Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
          child: Row(children: [
            const Text('🎵 '),
            Expanded(
              child: Text('${m['title']}${artist.isEmpty ? '' : ' — $artist'}',
                  maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12)),
            ),
            for (final a in const [('prev', Icons.skip_previous), ('toggle', Icons.pause), ('next', Icons.skip_next)])
              IconButton(
                visualDensity: VisualDensity.compact,
                iconSize: 20,
                icon: Icon(a.$2),
                onPressed: () {
                  HapticFeedback.selectionClick();
                  conn.send({'type': 'media', 'action': a.$1});
                },
              ),
          ]),
        ),
      ),
    );
  }

  /// Shake the phone -> BOT gets dizzy.
  void _onAccel(UserAccelerometerEvent e) {
    final g = math.sqrt(e.x * e.x + e.y * e.y + e.z * e.z);
    if (g < 17) return;
    final now = DateTime.now();
    _shakes.add(now);
    _shakes.removeWhere((t) => now.difference(t) > const Duration(milliseconds: 900));
    if (_shakes.length >= 3 && now.difference(_lastDizzy) > const Duration(seconds: 3) && mounted) {
      _lastDizzy = now;
      _shakes.clear();
      HapticFeedback.heavyImpact();
      setState(() => _poke++);
      _flashMood(Mood.dizzy, const Duration(milliseconds: 2600));
      _say(_rnd.nextBool() ? 'Whoaaa… everything is spinning! 😵' : 'Stop shaking meee! 😵‍💫');
    }
  }

  /// One-tap actions on the PC.
  void _quick(String action, String label) {
    HapticFeedback.selectionClick();
    if (!conn.online) {
      _say('Not connected to the PC');
      _flashMood(Mood.sleepy);
      return;
    }
    conn.send({'type': 'quick', 'action': action});
    _addLog(label, mine: true);
  }

  Future<void> _wakePc() async {
    HapticFeedback.mediumImpact();
    if (conn.online) {
      _say('The PC is already awake 🙂');
      return;
    }
    if (conn.mac.isEmpty) {
      _say('Connect to the PC once first, so I can learn how to wake it.');
      return;
    }
    final ok = await conn.wake();
    _say(ok
        ? 'Wake signal sent! If your laptop supports it, it wakes in a few seconds.'
        : 'Couldn\'t send the wake signal.');
    _flashMood(ok ? Mood.excited : Mood.sad);
  }

  Future<void> _personalize() async {
    final s = await showPersonalize(context);
    if (s == null) return;
    await saveStyle(s);
    conn.send({'type': 'set_style', 'name': s.name, 'color': colorHex(s.color)});
    _flashMood(Mood.love);
    _say('Hi, I\'m ${s.name}! 💕');
  }

  void _lockPc() {
    HapticFeedback.mediumImpact();
    if (!conn.online) {
      _say('Not connected to the PC');
      _flashMood(Mood.sleepy);
      return;
    }
    conn.send({'type': 'quick', 'action': 'lock'});
    _addLog('🔒 Lock PC', mine: true);
    _flashMood(Mood.wink);
  }

  String get _caption {
    if (voice.listening) return voice.heard.isEmpty ? 'Listening…' : voice.heard;
    if ((_waiting || conn.busy) && _progress.isNotEmpty) return _progress;
    if (_waiting) return 'On it…';
    if (_bubbleText.isNotEmpty) return _bubbleText;
    return switch (conn.link) {
      Link.offline => conn.configured ? 'Zzz… PC is offline' : 'Tap ⋮ → Connection settings',
      Link.connecting => 'Waking up…',
      Link.online => 'Hold me to talk · tap me to play',
    };
  }

  // ---------------------------------------------------------------- events

  void _onEvent(BotEvent e) {
    if (!mounted) return;
    switch (e.type) {
      case 'welcome':
        _addLog(e.message);
        _flashMood(Mood.happy);
        if (!conn.keywordSet && !_askedForKeyword) {
          _askedForKeyword = true;
          Future.delayed(const Duration(milliseconds: 600), () {
            if (mounted && conn.online && !conn.keywordSet) setSafetyWord(context, conn, firstTime: true);
          });
        }
      case 'progress':
        setState(() {
          _waiting = true;
          _progress = e.message;
        });
        _waitTimer?.cancel();
        _waitTimer = Timer(const Duration(seconds: 90), _stopWaiting);
      case 'result':
        _stopWaiting();
        _addLog(e.message, ok: e.ok);
        _say(e.message);
        final mood = e.ok
            ? (_rnd.nextBool() ? Mood.happy : Mood.excited)
            : (e.message.contains("couldn't find") ? Mood.confused : (_rnd.nextBool() ? Mood.sad : Mood.dizzy));
        _flashMood(mood, const Duration(seconds: 2));
        HapticFeedback.lightImpact();
      case 'confirm':
        _flashMood(Mood.surprised, const Duration(seconds: 3));
        if (e.keyword) {
          _confirmWithSafetyWord(e.id, e.message);
        } else {
          _stopWaiting();
          _askYesNo(e.id, e.message);
        }
      case 'keyword_status':
        _addLog(e.message, ok: e.ok);
        _say(e.message);
        _flashMood(e.ok ? Mood.happy : Mood.sad);
      case 'error':
        _stopWaiting();
        _addLog(e.message, ok: false);
        _flashMood(Mood.sad);
      case 'log':
        _addLog(e.message, ok: e.ok);
      case 'alert':
        _showAlert(e.id, e.message);
      case 'clip_push':
        HapticFeedback.mediumImpact();
        final short = e.message.length > 60 ? '${e.message.substring(0, 60)}…' : e.message;
        _addLog('📋 From the PC (copied): $short');
        _say('Copied from your PC! 📋 Paste it anywhere');
        _flashMood(Mood.happy);
      case 'find_phone':
        _flashMood(Mood.excited, const Duration(seconds: 3));
        showFindPhone(context);
      case 'travel':
        if (e.message == 'phone') {
          HapticFeedback.mediumImpact();
          setState(() => _poke++);
          _flashMood(Mood.love, const Duration(seconds: 3));
          _say(_rnd.nextBool() ? 'I followed you! 🥰📱 The PC was lonely without you' : 'Hiii! I came to your phone! 🥰');
          _addLog('📱 BOT followed you to your phone');
        } else if (e.message == 'pc') {
          _flashMood(Mood.wink);
          _say('Bye! I went back to the PC 👋💻');
        }
      case 'file_received':
        final name = e.message.split('/').last;
        final where = e.message.contains('/Download/') ? 'Download/BOT' : 'the BOT app folder';
        HapticFeedback.mediumImpact();
        _flashMood(Mood.excited, const Duration(seconds: 2));
        _addLog('📥 Got $name from the PC (saved in $where)');
        _say('Delivery! 📦 $name is in $where');
      case 'pet_event':
        if (e.message == 'dizzy') {
          HapticFeedback.heavyImpact();
          setState(() => _poke++);
          _flashMood(Mood.dizzy, const Duration(milliseconds: 3000));
          _say(_rnd.nextBool() ? 'Ouch! Someone threw me on the PC! 😵' : 'Wheee… *bonk* 😵‍💫 my head is spinning!');
        } else if (e.message == 'hug') {
          HapticFeedback.mediumImpact();
          _flashMood(Mood.love, const Duration(milliseconds: 2500));
          _say('You hugged me on the PC! 🤗💙');
        } else if (e.message == 'petted') {
          _flashMood(Mood.love, const Duration(milliseconds: 2000));
          _say('Hehe, someone petted me on the PC 🥰');
        }
      case 'away':
        showDialog<void>(
          context: context,
          builder: (ctx) => AlertDialog(
            icon: const Icon(Icons.notifications_active),
            title: const Text('While you were away…'),
            content: Text(e.message),
            actions: [FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK'))],
          ),
        );
    }
  }

  void _say(String text) {
    if (!mounted) return;
    setState(() => _bubbleText = text);
    Timer(const Duration(seconds: 5), () {
      if (mounted && _bubbleText == text) setState(() => _bubbleText = '');
    });
  }

  void _stopWaiting() {
    _waitTimer?.cancel();
    if (_waiting || _progress.isNotEmpty) {
      setState(() {
        _waiting = false;
        _progress = '';
      });
    }
  }

  Future<void> _askYesNo(String id, String message) async {
    HapticFeedback.heavyImpact();
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Are you sure?'),
        content: Text(message),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('No')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Yes')),
        ],
      ),
    );
    conn.send({'type': 'confirm_reply', 'id': id, 'yes': yes == true});
  }

  Future<void> _confirmWithSafetyWord(String id, String message) async {
    final word = await askSafetyWord(context, voice: voice, locale: _locale, message: message);
    conn.send({
      'type': 'confirm_reply',
      'id': id,
      'yes': word != null && word.isNotEmpty,
      'keyword': word ?? '',
    });
  }

  void _sendCommand(String text) {
    _addLog(text, mine: true);
    if (!conn.online) {
      _addLog('Not connected to the PC. Tap the status chip to reconnect.', ok: false);
      _flashMood(Mood.sleepy);
      return;
    }
    conn.send({'type': 'command', 'text': text, 'lang': languages[_lang].code});
    setState(() {
      _waiting = true;
      _progress = '';
    });
    _waitTimer?.cancel();
    _waitTimer = Timer(const Duration(seconds: 15), _stopWaiting);
  }

  void _sendTyped() {
    final t = _input.text.trim();
    if (t.isEmpty) return;
    _input.clear();
    _sendCommand(t);
  }

  void _addLog(String text, {bool mine = false, bool ok = true}) {
    if (!mounted || text.isEmpty) return;
    setState(() {
      _log.insert(0, LogEntry(text, mine: mine, ok: ok));
      if (_log.length > 100) _log.removeLast();
    });
  }

  // -------------------------------------------------------------- settings

  Future<void> _openSettings() async {
    final result = await showDialog<ConnSettings>(
      context: context,
      builder: (_) => SettingsDialog(
          initial: ConnSettings(conn.host, conn.port, conn.pin, conn.pcName, conn.remoteHost)),
    );
    if (result == null) return;
    await conn.updateSettings(
      host: result.host,
      port: result.port,
      pin: result.pin,
      name: result.name,
      remoteHost: result.remoteHost,
    );
  }

  Future<void> _setLang(int i) async {
    setState(() => _lang = i);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('lang', i);
  }

  // Face: short tap = expression, hold = talk.
  /// Stroking the face = petting: BOT purrs with hearts.
  void _faceMove(PointerMoveEvent e) {
    if (!_fingerDown || voice.listening) return;
    final last = _lastPetPos;
    _lastPetPos = e.localPosition;
    if (last == null) return;
    _petTravel += (e.localPosition - last).distance;
    if (!_petting && _petTravel > 22) {
      _holdTimer?.cancel(); // moving finger = petting, not talking
      _holdFired = true;
      setState(() => _petting = true);
    }
    if (_petting && _petTravel - _petTick > 70) {
      _petTick = _petTravel;
      HapticFeedback.selectionClick(); // purr tick
    }
  }

  void _faceDown(PointerDownEvent e) {
    _lastPetPos = e.localPosition;
    _petTravel = 0;
    _petTick = 0;
    _fingerDown = true;
    _holdFired = false;
    _holdTimer?.cancel();
    _holdTimer = Timer(const Duration(milliseconds: 220), () {
      if (_fingerDown) {
        _holdFired = true;
        HapticFeedback.mediumImpact();
        voice.start(_locale, _sendCommand);
      }
    });
  }

  void _faceUp(PointerEvent _) {
    if (!_fingerDown) return;
    _fingerDown = false;
    _holdTimer?.cancel();
    if (_petting) {
      setState(() => _petting = false);
      _flashMood(Mood.love, const Duration(milliseconds: 2200));
      conn.send({'type': 'pet_react', 'mood': 'love'});
      _say(_rnd.nextBool() ? 'Hehe, that tickles! 💕' : 'Purrrr… I love you too 🥰');
      return;
    }
    if (voice.listening) {
      voice.stop();
    } else if (!_holdFired) {
      _tapFace();
    }
  }

  // -------------------------------------------------------------------- UI

  void _showHelp() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (ctx) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          children: [
            Text('Things you can say', style: Theme.of(ctx).textTheme.titleLarge),
            const SizedBox(height: 4),
            const Text('Hold my face to talk · tap me for a mood · stroke me to pet me 🥰 · '
                'shake your phone to make me dizzy 😵 · say a routine name like "good night".'),
            for (final e in examples.entries) ...[
              const SizedBox(height: 14),
              Text(e.key, style: Theme.of(ctx).textTheme.titleSmall),
              const SizedBox(height: 6),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final s in e.value)
                    ActionChip(
                      label: Text(s),
                      onPressed: () {
                        Navigator.pop(ctx);
                        _sendCommand(s);
                      },
                    ),
                ],
              ),
            ],
            const SizedBox(height: 16),
            const Text('To stop BOT: tap Stop, say "stop", or on the PC move the mouse or press Esc.'),
          ],
        ),
      ),
    );
  }

  Widget _statusChip(ColorScheme cs) {
    final (Color color, String label) = switch (conn.link) {
      Link.online => (Colors.greenAccent, conn.viaRemote ? '${conn.pcName} · outside' : conn.pcName),
      Link.connecting => (Colors.orangeAccent, 'Connecting…'),
      Link.offline => (cs.error, 'Offline · tap'),
    };
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 170),
      child: ActionChip(
        avatar: Icon(conn.viaRemote && conn.online ? Icons.public : Icons.circle, size: 12, color: color),
        label: Text(label.isEmpty ? 'Online' : label, overflow: TextOverflow.ellipsis),
        onPressed: conn.link == Link.offline ? (conn.configured ? conn.connect : _openSettings) : null,
      ),
    );
  }

  Widget _bubble(LogEntry e, ColorScheme cs) {
    final bg = e.mine ? cs.primaryContainer : (e.ok ? cs.surfaceContainerHighest : cs.errorContainer);
    final fg = e.mine ? cs.onPrimaryContainer : (e.ok ? cs.onSurface : cs.onErrorContainer);
    return Align(
      alignment: e.mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 3),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        constraints: const BoxConstraints(maxWidth: 300),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(14)),
        child: Text(e.text, style: TextStyle(color: fg, fontSize: 14)),
      ),
    );
  }

  Widget _face(double size) {
    return ValueListenableBuilder<CursorPos?>(
      valueListenable: conn.cursor,
      builder: (context, c, _) => Listener(
        onPointerDown: _faceDown,
        onPointerMove: _faceMove,
        onPointerUp: _faceUp,
        onPointerCancel: _faceUp,
        child: RobotFace(
          mood: _mood,
          look: c == null ? null : Offset(c.vx * 2 - 1, c.vy * 2 - 1),
          lookStamp: c?.at,
          level: voice.listening ? voice.level : 0,
          size: size,
          poke: _poke,
          color: style.value.color,
        ),
      ),
    );
  }

  Widget _captionBubble() {
    final listening = voice.listening;
    return Column(mainAxisSize: MainAxisSize.min, children: [
      AnimatedSwitcher(
        duration: const Duration(milliseconds: 200),
        child: Container(
          key: ValueKey(_caption),
          constraints: const BoxConstraints(maxWidth: 320),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0xFF111B3A),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: botBlue.withAlpha(listening ? 230 : 90)),
          ),
          child: Text(_caption,
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: listening ? botLight : Colors.white70, fontSize: 15)),
        ),
      ),
      if (conn.busy)
        Padding(
          padding: const EdgeInsets.only(top: 6),
          child: FilledButton.tonalIcon(
            onPressed: () {
              HapticFeedback.mediumImpact();
              conn.stopTask();
            },
            icon: const Icon(Icons.stop_circle_outlined),
            label: const Text('Stop'),
          ),
        ),
    ]);
  }

  Widget _quickButton(IconData icon, String tip, VoidCallback onTap, {bool highlight = false}) {
    return IconButton.filledTonal(
      tooltip: tip,
      visualDensity: VisualDensity.compact,
      style: highlight ? IconButton.styleFrom(backgroundColor: Colors.amber.withAlpha(90)) : null,
      icon: Icon(icon, size: 20),
      onPressed: onTap,
    );
  }

  Widget _actionButton(IconData icon, String label, VoidCallback onTap) {
    return Expanded(
      child: FilledButton.tonal(
        onPressed: onTap,
        style: FilledButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 4),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 22),
          const SizedBox(height: 3),
          Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)),
        ]),
      ),
    );
  }

  void _open(Widget page) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: Text(style.value.name,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w800, letterSpacing: 2)),
        actions: [
          _statusChip(cs),
          PopupMenuButton<String>(
            onSelected: (v) {
              switch (v) {
                case 'bubble':
                  conn.setBubble(!conn.bubbleOn);
                case 'keyword':
                  setSafetyWord(context, conn);
                case 'routines':
                  _open(RoutinesPage(conn: conn, lang: languages[_lang].code));
                case 'pet':
                  conn.petOn = !conn.petOn;
                  conn.send({'type': 'set_pet', 'on': conn.petOn});
                  setState(() {});
                case 'walkaway':
                  _walkawaySettings();
                case 'health':
                  _open(DashboardPage(conn: conn));
                case 'care':
                  _open(CarePage(conn: conn));
                case 'world':
                  _open(WorldPage(conn: conn));
                case 'transfer':
                  showTransfer(context, conn);
                case 'style':
                  _personalize();
                case 'help':
                  _showHelp();
                case 'settings':
                  _openSettings();
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(value: 'routines', child: Text('Routines')),
              const PopupMenuItem(value: 'world', child: Text("BOT's world 🌍")),
              const PopupMenuItem(value: 'care', child: Text('Take care of BOT 🍪')),
              const PopupMenuItem(value: 'health', child: Text('PC health')),
              CheckedPopupMenuItem(
                value: 'pet',
                checked: conn.petOn,
                enabled: conn.online,
                child: const Text('BOT on PC desktop'),
              ),
              PopupMenuItem(
                value: 'walkaway',
                enabled: conn.online,
                child: Text('Walk-away lock${conn.walkaway['enabled'] == true ? ' (on)' : ''}'),
              ),
              const PopupMenuItem(value: 'transfer', child: Text('Send files & clipboard')),
              const PopupMenuItem(value: 'style', child: Text('Name & colour')),
              CheckedPopupMenuItem(
                value: 'bubble',
                checked: conn.bubbleOn,
                enabled: conn.online,
                child: const Text('BOT cursor on PC'),
              ),
              PopupMenuItem(
                value: 'keyword',
                enabled: conn.online,
                child: Text(conn.keywordSet ? 'Change safety word' : 'Set safety word'),
              ),
              const PopupMenuItem(value: 'help', child: Text('What can I say?')),
              const PopupMenuItem(value: 'settings', child: Text('Connection settings')),
            ],
          ),
        ],
      ),
      body: LayoutBuilder(builder: (context, box) {
        // While the keyboard is open, hide the face so the text box has room.
        final keyboardOpen = MediaQuery.of(context).viewInsets.bottom > 0;
        final faceSize = math.min(math.min(box.maxWidth * 0.58, box.maxHeight * 0.29), 240.0);
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 2, 12, 2),
              child: Wrap(
                spacing: 8,
                alignment: WrapAlignment.center,
                children: [
                  for (var i = 0; i < languages.length; i++)
                    ChoiceChip(
                      label: Text(languages[i].label),
                      selected: _lang == i,
                      onSelected: (_) => _setLang(i),
                    ),
                ],
              ),
            ),
            if (!keyboardOpen) ...[
              _face(faceSize),
              _captionBubble(),
              _healthChip(),
              _musicCard(),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Row(children: [
                  _actionButton(Icons.desktop_windows, 'Screen', () => _open(ScreenPage(
                        conn: conn,
                        voice: voice,
                        locale: _locale,
                        onCommand: _sendCommand,
                      ))),
                  const SizedBox(width: 8),
                  _actionButton(Icons.sports_esports, 'Control', _openControl),
                  const SizedBox(width: 8),
                  _actionButton(Icons.lock, 'Lock PC', _lockPc),
                ]),
              ),
              const SizedBox(height: 6),
              // quick buttons
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    _quickButton(Icons.volume_off, 'Mute', () => _quick('mute', '🔇 Mute')),
                    _quickButton(Icons.volume_down, 'Volume down', () => _quick('volume_down', '🔉 Volume down')),
                    _quickButton(Icons.volume_up, 'Volume up', () => _quick('volume_up', '🔊 Volume up')),
                    _quickButton(Icons.play_arrow, 'Play / pause', () => _quick('play_pause', '⏯ Play / pause')),
                    _quickButton(Icons.screenshot_monitor, 'Screenshot', () => _quick('screenshot', '📸 Screenshot')),
                    _quickButton(Icons.upload_file, 'Send files', () => showTransfer(context, conn)),
                    _quickButton(Icons.power_settings_new, 'Wake PC', _wakePc,
                        highlight: conn.link == Link.offline && conn.mac.isNotEmpty),
                  ],
                ),
              ),
            ],
            Expanded(
              child: ListView.builder(
                reverse: true,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                itemCount: _log.length,
                itemBuilder: (_, i) => _bubble(_log[i], cs),
              ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 4, 12, 10),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _input,
                        textInputAction: TextInputAction.send,
                        onSubmitted: (_) => _sendTyped(),
                        decoration: const InputDecoration(
                          hintText: 'Or type a command…',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton.filled(onPressed: _sendTyped, icon: const Icon(Icons.send)),
                  ],
                ),
              ),
            ),
          ],
        );
      }),
    );
  }
}
