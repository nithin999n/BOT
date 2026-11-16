import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

import 'connection.dart';
import 'face.dart';
import 'screen_page.dart';
import 'settings_dialog.dart';
import 'touchpad_page.dart';

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
  'English': [
    'open chrome',
    'volume up',
    'search weather in bangalore',
    'play arijit singh on youtube',
    'battery',
    'hide the cursor',
    'lock the computer',
  ],
  'हिंदी': ['क्रोम खोलो', 'आवाज़ बढ़ाओ', 'गूगल पर मौसम सर्च करो', 'बैटरी कितनी है', 'कर्सर बंद करो'],
  'ಕನ್ನಡ': ['ಕ್ರೋಮ್ ತೆರೆ', 'ವಾಲ್ಯೂಮ್ ಹೆಚ್ಚಿಸು', 'ಯೂಟ್ಯೂಬ್ ತೆರೆ', 'ಸ್ಕ್ರೀನ್‌ಶಾಟ್', 'ಕರ್ಸರ್ ಆಫ್ ಮಾಡು'],
  'తెలుగు': ['క్రోమ్ ఓపెన్ చేయి', 'సౌండ్ పెంచు', 'గూగుల్ లో వాతావరణం వెతుకు', 'లాక్ చేయి', 'కర్సర్ ఆఫ్ చేయి'],
};

const _tapMoods = [Mood.happy, Mood.wink, Mood.love, Mood.surprised, Mood.confused];

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
  StreamSubscription<BotEvent>? _eventSub;

  // Speech
  final SpeechToText _speech = SpeechToText();
  bool _speechReady = false;
  bool _listening = false;
  bool _sentThisTurn = true;
  String _heard = '';
  double _level = 0;
  Timer? _sendTimer;

  // Face
  Mood? _flash; // short-lived expression (tap, result…)
  Timer? _flashTimer;
  bool _waiting = false; // command sent, waiting for the PC
  Timer? _waitTimer;
  Timer? _holdTimer;
  bool _fingerDown = false;
  bool _holdFired = false;
  String _bubbleText = '';
  final _rnd = math.Random();

  int _lang = 0;
  final List<LogEntry> _log = [];
  final TextEditingController _input = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    conn.addListener(_onConn);
    _eventSub = conn.events.listen(_onEvent);
    _init();
    _initSpeech();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    conn.removeListener(_onConn);
    _eventSub?.cancel();
    for (final t in [_sendTimer, _flashTimer, _waitTimer, _holdTimer]) {
      t?.cancel();
    }
    _speech.cancel();
    _input.dispose();
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

  void _onConn() {
    if (mounted) setState(() {});
  }

  // ------------------------------------------------------------------ mood

  Mood get _mood {
    if (_listening) return Mood.listening;
    final flash = _flash;
    if (flash != null) return flash;
    if (_waiting) return Mood.thinking;
    return switch (conn.link) {
      Link.offline => Mood.sleepy,
      Link.connecting => Mood.thinking,
      Link.online => Mood.idle,
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
    _flashMood(options[_rnd.nextInt(options.length)]);
  }

  String get _caption {
    if (_listening) return _heard.isEmpty ? 'Listening…' : _heard;
    if (_waiting) return 'On it…';
    if (_bubbleText.isNotEmpty) return _bubbleText;
    return switch (conn.link) {
      Link.offline => conn.configured ? 'Zzz… PC is offline' : 'Tap ⚙ to connect your PC',
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
      case 'result':
        _stopWaiting();
        _addLog(e.message, ok: e.ok);
        _say(e.message);
        _flashMood(e.ok ? Mood.happy : Mood.sad, const Duration(seconds: 2));
        HapticFeedback.lightImpact();
      case 'confirm':
        _stopWaiting();
        _flashMood(Mood.surprised, const Duration(seconds: 3));
        _askConfirm(e.id, e.message);
      case 'error':
        _stopWaiting();
        _addLog(e.message, ok: false);
        _flashMood(Mood.sad);
      case 'log':
        _addLog(e.message, ok: e.ok);
    }
  }

  void _say(String text) {
    setState(() => _bubbleText = text);
    Timer(const Duration(seconds: 4), () {
      if (mounted && _bubbleText == text) setState(() => _bubbleText = '');
    });
  }

  void _stopWaiting() {
    _waitTimer?.cancel();
    if (_waiting) setState(() => _waiting = false);
  }

  Future<void> _askConfirm(String id, String message) async {
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

  void _sendCommand(String text) {
    _addLog(text, mine: true);
    if (!conn.online) {
      _addLog('Not connected to the PC. Tap the status chip to reconnect.', ok: false);
      _flashMood(Mood.sleepy);
      return;
    }
    conn.send({'type': 'command', 'text': text, 'lang': languages[_lang].code});
    setState(() => _waiting = true);
    _waitTimer?.cancel();
    _waitTimer = Timer(const Duration(seconds: 12), _stopWaiting);
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

  // ---------------------------------------------------------------- speech

  Future<void> _initSpeech() async {
    bool ok = false;
    try {
      ok = await _speech.initialize(onStatus: _onSpeechStatus, onError: _onSpeechError);
    } catch (_) {
      ok = false;
    }
    if (!mounted) return;
    setState(() => _speechReady = ok);
    if (!ok) {
      _addLog(
          'Voice is not available (microphone permission denied or no Google speech service). '
          'You can still type commands below.',
          ok: false);
    }
  }

  void _onSpeechStatus(String status) {
    if (!mounted) return;
    if (status == 'done' || status == 'notListening') {
      setState(() => _listening = false);
      _scheduleSend();
    }
  }

  void _onSpeechError(SpeechRecognitionError e) {
    if (!mounted) return;
    setState(() => _listening = false);
    if (_heard.trim().isNotEmpty) {
      _scheduleSend();
    } else if (e.errorMsg == 'error_no_match' || e.errorMsg == 'error_speech_timeout') {
      _say("Didn't catch that. Hold me and speak again.");
      _flashMood(Mood.confused);
    } else {
      _addLog('Mic error: ${e.errorMsg}', ok: false);
    }
  }

  void _onSpeechResult(SpeechRecognitionResult r) {
    if (!mounted) return;
    setState(() => _heard = r.recognizedWords);
    if (r.finalResult) _sendHeard();
  }

  Future<void> _startListening() async {
    if (!_speechReady) {
      _say('Voice is not available. Type the command below.');
      return;
    }
    HapticFeedback.mediumImpact();
    _sendTimer?.cancel();
    setState(() {
      _listening = true;
      _heard = '';
      _level = 0;
      _sentThisTurn = false;
    });
    try {
      await _speech.listen(
        onResult: _onSpeechResult,
        localeId: languages[_lang].locale,
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(seconds: 4),
        onSoundLevelChange: (l) {
          // Android reports roughly -2..10 dB
          if (mounted) setState(() => _level = ((l + 2) / 12).clamp(0.0, 1.0));
        },
        listenOptions: SpeechListenOptions(
          partialResults: true,
          cancelOnError: true,
          listenMode: ListenMode.dictation,
        ),
      );
    } catch (e) {
      if (mounted) setState(() => _listening = false);
      _addLog('Could not start the mic: $e', ok: false);
    }
  }

  Future<void> _stopListening() async {
    if (!_listening) return;
    setState(() => _listening = false);
    await _speech.stop();
    _scheduleSend();
  }

  void _scheduleSend() {
    if (_sentThisTurn) return;
    _sendTimer?.cancel();
    _sendTimer = Timer(const Duration(milliseconds: 1200), _sendHeard);
  }

  void _sendHeard() {
    if (_sentThisTurn) return;
    final t = _heard.trim();
    if (t.isEmpty) return;
    _sentThisTurn = true;
    _sendTimer?.cancel();
    _sendCommand(t);
  }

  // Face: short tap = expression, hold = talk.
  void _faceDown(PointerDownEvent _) {
    _fingerDown = true;
    _holdFired = false;
    _holdTimer?.cancel();
    _holdTimer = Timer(const Duration(milliseconds: 220), () {
      if (_fingerDown) {
        _holdFired = true;
        _startListening();
      }
    });
  }

  void _faceUp(PointerEvent _) {
    if (!_fingerDown) return;
    _fingerDown = false;
    _holdTimer?.cancel();
    if (_listening) {
      _stopListening();
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
            const Text('Hold my face to talk. Tap my face to see my moods. Tap a chip to try it.'),
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
            const Text('On the PC: move your mouse or press Esc while the blue bubble is moving to cancel it.'),
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
        onPointerUp: _faceUp,
        onPointerCancel: _faceUp,
        child: RobotFace(
          mood: _mood,
          look: c == null ? null : Offset(c.vx * 2 - 1, c.vy * 2 - 1),
          lookStamp: c?.at,
          level: _listening ? _level : 0,
          size: size,
        ),
      ),
    );
  }

  Widget _captionBubble(ColorScheme cs) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 200),
      child: Container(
        key: ValueKey(_caption),
        constraints: const BoxConstraints(maxWidth: 320),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: const Color(0xFF111B3A),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: botBlue.withAlpha(_listening ? 230 : 90)),
        ),
        child: Text(_caption,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(color: _listening ? botLight : Colors.white70, fontSize: 15)),
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
        title: const Text('BOT', style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: 3)),
        actions: [
          _statusChip(cs),
          PopupMenuButton<String>(
            onSelected: (v) {
              switch (v) {
                case 'bubble':
                  conn.setBubble(!conn.bubbleOn);
                case 'help':
                  _showHelp();
                case 'settings':
                  _openSettings();
              }
            },
            itemBuilder: (_) => [
              CheckedPopupMenuItem(
                value: 'bubble',
                checked: conn.bubbleOn,
                enabled: conn.online,
                child: const Text('BOT cursor on PC'),
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
        final faceSize = math.min(math.min(box.maxWidth * 0.66, box.maxHeight * 0.4), 270.0);
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
          _captionBubble(cs),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Row(children: [
              Expanded(
                child: FilledButton.tonalIcon(
                  onPressed: () => _open(ScreenPage(conn: conn)),
                  icon: const Icon(Icons.desktop_windows),
                  label: const Text('Screen'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.tonalIcon(
                  onPressed: () => _open(TouchpadPage(conn: conn)),
                  icon: const Icon(Icons.touch_app),
                  label: const Text('Touchpad'),
                ),
              ),
            ]),
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
