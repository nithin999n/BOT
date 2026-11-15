import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'discovery.dart';

void main() => runApp(const BotApp());

class BotApp extends StatelessWidget {
  const BotApp({super.key});

  @override
  Widget build(BuildContext context) {
    ThemeData theme(Brightness b) => ThemeData(
          useMaterial3: true,
          colorSchemeSeed: const Color(0xFF3F51B5),
          brightness: b,
        );
    return MaterialApp(
      title: 'BOT',
      debugShowCheckedModeBanner: false,
      theme: theme(Brightness.light),
      darkTheme: theme(Brightness.dark),
      home: const HomePage(),
    );
  }
}

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
  'English': ['open chrome', 'volume up', 'search weather in bangalore', 'play arijit singh on youtube', 'type hello', 'lock the computer'],
  'हिंदी': ['क्रोम खोलो', 'आवाज़ बढ़ाओ', 'गूगल पर मौसम सर्च करो', 'कंप्यूटर लॉक करो'],
  'ಕನ್ನಡ': ['ಕ್ರೋಮ್ ತೆರೆ', 'ವಾಲ್ಯೂಮ್ ಹೆಚ್ಚಿಸು', 'ಯೂಟ್ಯೂಬ್ ತೆರೆ', 'ಸ್ಕ್ರೀನ್‌ಶಾಟ್'],
  'తెలుగు': ['క్రోమ్ ఓపెన్ చేయి', 'సౌండ్ పెంచు', 'గూగుల్ లో వాతావరణం వెతుకు', 'లాక్ చేయి'],
};

enum Link { offline, connecting, online }

class LogEntry {
  LogEntry(this.text, {this.mine = false, this.ok = true});
  final String text;
  final bool mine;
  final bool ok;
}

class ConnSettings {
  const ConnSettings(this.host, this.port, this.pin, this.name);
  final String host;
  final int port;
  final String pin;
  final String name; // PC name, used to find it again if its IP changes
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with WidgetsBindingObserver {
  // Speech
  final SpeechToText _speech = SpeechToText();
  bool _speechReady = false;
  bool _listening = false;
  bool _sentThisTurn = true;
  String _heard = '';
  double _level = 0;
  Timer? _sendTimer;

  // Connection
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;
  Link _link = Link.offline;
  bool _autoReconnect = false;
  Timer? _retryTimer;
  int _failures = 0;
  bool _rediscovering = false;
  String _pcName = '';

  // Settings
  String _host = '';
  int _port = 8765;
  String _pin = '';
  int _lang = 0;

  final List<LogEntry> _log = [];
  final TextEditingController _input = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loadSettings();
    _initSpeech();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _sendTimer?.cancel();
    _retryTimer?.cancel();
    _sub?.cancel();
    _channel?.sink.close();
    _speech.cancel();
    _input.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed &&
        _link == Link.offline &&
        _host.isNotEmpty &&
        _pin.isNotEmpty) {
      _connect();
    }
  }

  // ---------------------------------------------------------------- settings

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    final lang = prefs.getInt('lang') ?? 0;
    setState(() {
      _host = prefs.getString('host') ?? '';
      _port = prefs.getInt('port') ?? 8765;
      _pin = prefs.getString('pin') ?? '';
      _pcName = prefs.getString('pcName') ?? '';
      _lang = (lang >= 0 && lang < languages.length) ? lang : 0;
    });
    if (_host.isEmpty || _pin.isEmpty) {
      _openSettings();
    } else {
      _connect();
    }
  }

  Future<void> _openSettings() async {
    final result = await showDialog<ConnSettings>(
      context: context,
      builder: (_) => SettingsDialog(initial: ConnSettings(_host, _port, _pin, _pcName)),
    );
    if (result == null || !mounted) return;
    setState(() {
      _host = result.host;
      _port = result.port;
      _pin = result.pin;
      _pcName = result.name;
      _failures = 0;
    });
    await _saveConnection();
    _connect();
  }

  Future<void> _saveConnection() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('host', _host);
    await prefs.setInt('port', _port);
    await prefs.setString('pin', _pin);
    await prefs.setString('pcName', _pcName);
  }

  /// The PC's IP can change (router restart). Look for it on Wi-Fi and follow it.
  Future<void> _rediscover() async {
    if (_rediscovering) return;
    _rediscovering = true;
    try {
      final pcs = await discoverPcs();
      if (!mounted || pcs.isEmpty) return;
      FoundPc? pick;
      for (final pc in pcs) {
        if (pc.name == _pcName) pick = pc;
      }
      if (pick == null && pcs.length == 1) pick = pcs.first;
      final found = pick;
      if (found == null || (found.host == _host && found.port == _port)) return;
      setState(() {
        _host = found.host;
        _port = found.port;
        _pcName = found.name;
      });
      await _saveConnection();
      _addLog('Found ${found.name} at its new address ${found.host}');
    } finally {
      _rediscovering = false;
    }
  }

  Future<void> _setLang(int i) async {
    setState(() => _lang = i);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('lang', i);
  }

  // -------------------------------------------------------------- connection

  Future<void> _closeChannel() async {
    final sub = _sub;
    final ch = _channel;
    _sub = null;
    _channel = null;
    await sub?.cancel();
    await ch?.sink.close();
  }

  Future<void> _connect() async {
    _retryTimer?.cancel();
    await _closeChannel();
    if (_host.isEmpty || !mounted) return;
    _autoReconnect = true;
    setState(() => _link = Link.connecting);
    try {
      final ch = WebSocketChannel.connect(Uri(scheme: 'ws', host: _host, port: _port));
      _channel = ch;
      await ch.ready.timeout(const Duration(seconds: 5));
      if (!mounted || _channel != ch) {
        ch.sink.close();
        return;
      }
      _sub = ch.stream.listen(
        _onMessage,
        onDone: () => _onClosed(ch),
        onError: (Object _) => _onClosed(ch),
        cancelOnError: true,
      );
      ch.sink.add(jsonEncode({'type': 'hello', 'pin': _pin, 'device': 'android'}));
    } catch (_) {
      final dead = _channel;
      _channel = null;
      dead?.sink.close();
      if (!mounted) return;
      _failures++;
      setState(() => _link = Link.offline);
      _scheduleRetry();
    }
  }

  void _onClosed(WebSocketChannel ch) {
    if (_channel != ch || !mounted) return;
    final wasOnline = _link == Link.online;
    _channel = null;
    _sub = null;
    _failures++;
    setState(() => _link = Link.offline);
    if (wasOnline) _addLog('Disconnected from PC', ok: false);
    _scheduleRetry();
  }

  void _scheduleRetry() {
    if (!_autoReconnect) return;
    _retryTimer?.cancel();
    final delay = Duration(seconds: _failures < 5 ? 3 : 10);
    _retryTimer = Timer(delay, () async {
      if (!mounted || !_autoReconnect || _link != Link.offline) return;
      if (_failures >= 2) await _rediscover();
      if (mounted && _autoReconnect && _link == Link.offline) _connect();
    });
  }

  void _send(Map<String, Object?> msg) {
    _channel?.sink.add(jsonEncode(msg));
  }

  void _onMessage(dynamic raw) {
    final Map<String, dynamic> msg;
    try {
      msg = jsonDecode(raw as String) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    final text = (msg['message'] ?? '').toString();
    switch (msg['type']) {
      case 'welcome':
        setState(() {
          _link = Link.online;
          _failures = 0;
          _pcName = (msg['pc'] ?? 'PC').toString();
        });
        _saveConnection();
        _addLog('Connected to $_pcName');
      case 'result':
        _addLog(text, ok: msg['ok'] == true);
        HapticFeedback.lightImpact();
      case 'confirm':
        _askConfirm((msg['id'] ?? '').toString(), text);
      case 'error':
        _addLog(text, ok: false);
        if (msg['fatal'] == true) _autoReconnect = false;
    }
  }

  Future<void> _askConfirm(String id, String message) async {
    if (!mounted) return;
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
    _send({'type': 'confirm_reply', 'id': id, 'yes': yes == true});
  }

  void _sendCommand(String text) {
    _addLog(text, mine: true);
    if (_link != Link.online) {
      _addLog('Not connected to the PC. Tap the status chip to reconnect.', ok: false);
      return;
    }
    _send({'type': 'command', 'text': text, 'lang': languages[_lang].code});
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

  // ------------------------------------------------------------------ speech

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
      _addLog('Voice is not available (microphone permission denied or no Google speech service). '
          'You can still type commands below.', ok: false);
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
      _addLog("Didn't catch that. Hold the button and speak again.", ok: false);
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
      _snack('Voice is not available. Type the command instead.');
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
          if (mounted) setState(() => _level = l);
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

  /// Wait briefly for the final transcript; send whatever we heard if it never comes.
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

  void _snack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  // ---------------------------------------------------------------------- UI

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
            const SizedBox(height: 8),
            for (final e in examples.entries) ...[
              const SizedBox(height: 12),
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
          ],
        ),
      ),
    );
  }

  Widget _statusChip(ColorScheme cs) {
    final (Color color, String label) = switch (_link) {
      Link.online => (Colors.green, _pcName.isEmpty ? 'Online' : _pcName),
      Link.connecting => (Colors.orange, 'Connecting…'),
      Link.offline => (cs.error, 'Offline · tap'),
    };
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 170),
      child: ActionChip(
        avatar: Icon(Icons.circle, size: 12, color: color),
        label: Text(label, overflow: TextOverflow.ellipsis),
        onPressed: _link == Link.offline
            ? (_host.isEmpty ? _openSettings : _connect)
            : null,
      ),
    );
  }

  Widget _bubble(LogEntry e, ColorScheme cs) {
    final bg = e.mine ? cs.primaryContainer : (e.ok ? cs.surfaceContainerHighest : cs.errorContainer);
    final fg = e.mine ? cs.onPrimaryContainer : (e.ok ? cs.onSurface : cs.onErrorContainer);
    return Align(
      alignment: e.mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: const BoxConstraints(maxWidth: 300),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(16)),
        child: Text(e.text, style: TextStyle(color: fg, fontSize: 15)),
      ),
    );
  }

  Widget _micButton(ColorScheme cs) {
    final active = _listening;
    final base = active ? cs.error : cs.primary;
    final size = 116.0 + (active ? _level.clamp(0, 10) * 3 : 0);
    return Listener(
      onPointerDown: (_) => _startListening(),
      onPointerUp: (_) => _stopListening(),
      onPointerCancel: (_) => _stopListening(),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: base,
          boxShadow: [
            BoxShadow(
              color: base.withAlpha(90),
              blurRadius: active ? 30 : 12,
              spreadRadius: active ? 6 : 1,
            ),
          ],
        ),
        child: Icon(
          active ? Icons.graphic_eq : Icons.mic,
          size: 52,
          color: active ? cs.onError : cs.onPrimary,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('BOT', style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: 2)),
        actions: [
          _statusChip(cs),
          IconButton(tooltip: 'What can I say?', icon: const Icon(Icons.help_outline), onPressed: _showHelp),
          IconButton(tooltip: 'Connection settings', icon: const Icon(Icons.settings), onPressed: _openSettings),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 4, 12, 4),
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
          Expanded(
            child: _log.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(
                        'Hold the mic and say a command\n"open chrome" · "क्रोम खोलो" · "ಕ್ರೋಮ್ ತೆರೆ" · "క్రోమ్ ఓపెన్ చేయి"',
                        textAlign: TextAlign.center,
                        style: text.bodyLarge?.copyWith(color: cs.onSurfaceVariant),
                      ),
                    ),
                  )
                : ListView.builder(
                    reverse: true,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    itemCount: _log.length,
                    itemBuilder: (_, i) => _bubble(_log[i], cs),
                  ),
          ),
          SizedBox(
            height: 28,
            child: Text(
              _listening ? (_heard.isEmpty ? 'Listening…' : _heard) : '',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: text.titleMedium?.copyWith(color: cs.primary),
            ),
          ),
          SizedBox(height: 160, child: Center(child: _micButton(cs))),
          Text(_speechReady ? 'Hold to talk · ${languages[_lang].label}' : 'Voice unavailable',
              style: text.labelMedium?.copyWith(color: cs.onSurfaceVariant)),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
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
      ),
    );
  }
}

class SettingsDialog extends StatefulWidget {
  const SettingsDialog({super.key, required this.initial});
  final ConnSettings initial;

  @override
  State<SettingsDialog> createState() => _SettingsDialogState();
}

class _SettingsDialogState extends State<SettingsDialog> {
  late final TextEditingController _host = TextEditingController(text: widget.initial.host);
  late final TextEditingController _port = TextEditingController(text: widget.initial.port.toString());
  late final TextEditingController _pin = TextEditingController(text: widget.initial.pin);
  late String _name = widget.initial.name;
  String? _error;
  bool _searching = true; // a search starts as soon as the dialog opens
  List<FoundPc> _found = const [];

  @override
  void initState() {
    super.initState();
    _search();
  }

  Future<void> _search() async {
    if (!_searching) setState(() => _searching = true);
    final pcs = await discoverPcs();
    if (!mounted) return;
    setState(() {
      _searching = false;
      _found = pcs;
    });
    if (pcs.length == 1 && _host.text.trim().isEmpty) _pick(pcs.first);
  }

  void _pick(FoundPc pc) {
    setState(() {
      _host.text = pc.host;
      _port.text = pc.port.toString();
      _name = pc.name;
      _error = null;
    });
  }

  @override
  void dispose() {
    _host.dispose();
    _port.dispose();
    _pin.dispose();
    super.dispose();
  }

  void _save() {
    var host = _host.text.trim().replaceFirst(RegExp(r'^wss?://'), '');
    var port = int.tryParse(_port.text.trim()) ?? 0;
    if (host.contains(':')) {
      final parts = host.split(':');
      host = parts.first;
      port = int.tryParse(parts.last) ?? port;
    }
    final pin = _pin.text.trim();
    if (host.isEmpty || port <= 0 || port > 65535 || pin.isEmpty) {
      setState(() => _error = host.isEmpty
          ? 'Pick your PC from the list (or type its IP address).'
          : 'Please enter the PIN shown on the PC.');
      return;
    }
    // Keep the remembered PC name only if it still belongs to this address.
    final name = (host == widget.initial.host || _found.any((p) => p.host == host && p.name == _name)) ? _name : '';
    Navigator.pop(context, ConnSettings(host, port, pin, name));
  }

  Widget _foundList(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    if (_searching) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 8),
        child: Row(children: [
          SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
          SizedBox(width: 12),
          Text('Looking for your PC on Wi-Fi…'),
        ]),
      );
    }
    if (_found.isEmpty) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('No PC found. Check that BOT is running on the PC and both are on the same Wi-Fi, '
              'or type the IP address below.',
              style: TextStyle(color: cs.onSurfaceVariant)),
          TextButton.icon(onPressed: _search, icon: const Icon(Icons.refresh), label: const Text('Search again')),
        ],
      );
    }
    return Column(
      children: [
        for (final pc in _found)
          Card(
            margin: const EdgeInsets.symmetric(vertical: 4),
            color: _host.text.trim() == pc.host ? cs.primaryContainer : null,
            child: ListTile(
              leading: const Icon(Icons.computer),
              title: Text(pc.name),
              subtitle: Text('${pc.host}:${pc.port}'),
              trailing: _host.text.trim() == pc.host ? const Icon(Icons.check_circle) : null,
              onTap: () => _pick(pc),
            ),
          ),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(onPressed: _search, icon: const Icon(Icons.refresh), label: const Text('Search again')),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Connect to your PC'),
      content: SizedBox(
        width: double.maxFinite,
        child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _foundList(context),
            const SizedBox(height: 8),
            const Text('Then enter the PIN shown on the PC (or run "python autostart.py status").'),
            TextField(
              controller: _pin,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'PIN'),
              onSubmitted: (_) => _save(),
            ),
            const SizedBox(height: 16),
            Text('Manual address', style: Theme.of(context).textTheme.labelLarge),
            TextField(
              controller: _host,
              keyboardType: TextInputType.url,
              decoration: const InputDecoration(labelText: 'PC IP address', hintText: '192.168.1.10'),
            ),
            TextField(
              controller: _port,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Port'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
          ],
        ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _save, child: const Text('Connect')),
      ],
    );
  }
}
