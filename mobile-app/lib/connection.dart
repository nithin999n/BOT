import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'discovery.dart';

enum Link { offline, connecting, online }

/// Where the PC mouse (or BOT's bubble) is. vx/vy: 0..1 across all monitors (for the eyes).
/// mx/my: 0..1 on the main monitor (for the screen view).
class CursorPos {
  const CursorPos(this.vx, this.vy, this.mx, this.my, this.bot, this.at);
  final double vx, vy, mx, my;
  final bool bot;
  final DateTime at;
}

class ScreenInfo {
  const ScreenInfo(this.width, this.height);
  final int width, height;
}

class BotEvent {
  const BotEvent(this.type, this.message, {this.ok = true, this.id = '', this.keyword = false});
  final String type; // welcome, result, progress, confirm, error, log, screen_error, keyword_status
  final String message;
  final bool ok;
  final String id;
  final bool keyword; // confirm: needs the safety word (not just yes/no)
}

double _d(Map<String, dynamic> m, String k) => (m[k] as num?)?.toDouble() ?? 0;

/// One connection to the BOT PC agent, shared by every page of the app.
/// Tries home Wi-Fi first, then the Tailscale address when you're outside.
class BotConnection extends ChangeNotifier {
  String host = '';
  int port = 8765;
  String pin = '';
  String pcName = '';
  String remoteHost = ''; // Tailscale address, learned from the PC automatically

  Link link = Link.offline;
  bool viaRemote = false;
  bool bubbleOn = true;
  bool aiReady = false; // the PC has an Anthropic API key: "do anything" tasks work
  bool keywordSet = false; // a safety word is set on the PC
  bool busy = false; // the PC is working on an AI task right now

  final cursor = ValueNotifier<CursorPos?>(null);
  final screenInfo = ValueNotifier<ScreenInfo?>(null);
  final _frames = StreamController<Uint8List>.broadcast();
  final _events = StreamController<BotEvent>.broadcast();
  Stream<Uint8List> get frames => _frames.stream;
  Stream<BotEvent> get events => _events.stream;

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;
  bool _autoReconnect = false;
  Timer? _retryTimer;
  int _failures = 0;
  bool _rediscovering = false;
  bool _disposed = false;
  bool _foreground = true;
  String? _screenQuality; // set while the screen page is open

  bool get configured => (host.isNotEmpty || remoteHost.isNotEmpty) && pin.isNotEmpty;
  bool get online => link == Link.online;

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    host = p.getString('host') ?? '';
    port = p.getInt('port') ?? 8765;
    pin = p.getString('pin') ?? '';
    pcName = p.getString('pcName') ?? '';
    remoteHost = p.getString('remoteHost') ?? '';
    notifyListeners();
  }

  Future<void> save() async {
    final p = await SharedPreferences.getInstance();
    await p.setString('host', host);
    await p.setInt('port', port);
    await p.setString('pin', pin);
    await p.setString('pcName', pcName);
    await p.setString('remoteHost', remoteHost);
  }

  Future<void> updateSettings({
    required String host,
    required int port,
    required String pin,
    required String name,
    required String remoteHost,
  }) async {
    this.host = host;
    this.port = port;
    this.pin = pin;
    pcName = name;
    this.remoteHost = remoteHost;
    _failures = 0;
    await save();
    connect();
  }

  // ------------------------------------------------------------- connecting

  Future<void> connect() async {
    _retryTimer?.cancel();
    await _close();
    if (!configured || _disposed) return;
    _autoReconnect = true;
    _setLink(Link.connecting);
    final candidates = <(String, bool)>[
      if (host.isNotEmpty) (host, false),
      if (remoteHost.isNotEmpty && remoteHost != host) (remoteHost, true),
    ];
    for (final (h, remote) in candidates) {
      if (await _tryConnect(h, remote)) return;
      if (_disposed) return;
    }
    _failures++;
    _setLink(Link.offline);
    _scheduleRetry();
  }

  Future<bool> _tryConnect(String h, bool remote) async {
    WebSocketChannel? ch;
    try {
      ch = WebSocketChannel.connect(Uri(scheme: 'ws', host: h, port: port));
      await ch.ready.timeout(Duration(seconds: remote ? 7 : 3));
    } catch (_) {
      ch?.sink.close();
      return false;
    }
    final c = ch!;
    if (_disposed) {
      c.sink.close();
      return false;
    }
    _channel = c;
    viaRemote = remote;
    _sub = c.stream.listen(
      _onMessage,
      onDone: () => _onClosed(c),
      onError: (Object _) => _onClosed(c),
      cancelOnError: true,
    );
    c.sink.add(jsonEncode({'type': 'hello', 'pin': pin, 'device': 'android'}));
    return true;
  }

  Future<void> _close() async {
    final sub = _sub;
    final ch = _channel;
    _sub = null;
    _channel = null;
    await sub?.cancel();
    await ch?.sink.close();
  }

  void _onClosed(WebSocketChannel ch) {
    if (_channel != ch || _disposed) return;
    final wasOnline = online;
    _channel = null;
    _sub = null;
    _failures++;
    cursor.value = null;
    _setLink(Link.offline);
    if (wasOnline) _events.add(const BotEvent('log', 'Disconnected from PC', ok: false));
    _scheduleRetry();
  }

  void _scheduleRetry() {
    if (!_autoReconnect || _disposed) return;
    _retryTimer?.cancel();
    final delay = Duration(seconds: _failures < 5 ? 3 : 10);
    _retryTimer = Timer(delay, () async {
      if (_disposed || !_autoReconnect || link != Link.offline) return;
      if (_failures >= 2) await _rediscover();
      if (!_disposed && _autoReconnect && link == Link.offline) connect();
    });
  }

  /// The PC's IP can change (router restart). Look for it on Wi-Fi and follow it.
  Future<void> _rediscover() async {
    if (_rediscovering) return;
    _rediscovering = true;
    try {
      final pcs = await discoverPcs();
      if (_disposed || pcs.isEmpty) return;
      FoundPc? pick;
      for (final pc in pcs) {
        if (pc.name == pcName) pick = pc;
      }
      if (pick == null && pcs.length == 1) pick = pcs.first;
      final found = pick;
      if (found == null) return;
      final changed = found.host != host || found.port != port;
      host = found.host;
      port = found.port;
      pcName = found.name;
      if (found.tailscale.isNotEmpty) remoteHost = found.tailscale;
      await save();
      if (changed) _events.add(BotEvent('log', 'Found ${found.name} at its new address ${found.host}'));
    } finally {
      _rediscovering = false;
    }
  }

  void _setLink(Link l) {
    if (link == l) return;
    link = l;
    notifyListeners();
  }

  // --------------------------------------------------------------- messages

  void _onMessage(dynamic raw) {
    if (raw is! String) {
      // binary message = one JPEG frame of the PC screen
      final bytes = raw is Uint8List ? raw : Uint8List.fromList((raw as List).cast<int>());
      _frames.add(bytes);
      return;
    }
    final Map<String, dynamic> msg;
    try {
      msg = jsonDecode(raw) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    final text = (msg['message'] ?? '').toString();
    switch (msg['type']) {
      case 'cursor':
        cursor.value = CursorPos(_d(msg, 'vx'), _d(msg, 'vy'), _d(msg, 'mx'), _d(msg, 'my'),
            msg['bot'] == true, DateTime.now());
      case 'welcome':
        pcName = (msg['pc'] ?? 'PC').toString();
        final ts = (msg['tailscale'] ?? '').toString();
        if (ts.isNotEmpty) remoteHost = ts;
        bubbleOn = msg['bubble'] != false;
        aiReady = msg['ai'] == true;
        keywordSet = msg['keyword_set'] == true;
        busy = msg['busy'] == true;
        _failures = 0;
        _setLink(Link.online);
        save();
        _syncSubscriptions();
        _events.add(BotEvent('welcome',
            viaRemote ? 'Connected to $pcName from outside (Tailscale)' : 'Connected to $pcName'));
      case 'result':
        if (msg['busy'] == false && busy) {
          busy = false;
          notifyListeners();
        }
        _events.add(BotEvent('result', text, ok: msg['ok'] == true));
      case 'progress':
        if (!busy) {
          busy = true;
          notifyListeners();
        }
        _events.add(BotEvent('progress', text));
      case 'confirm':
        _events.add(BotEvent('confirm', text, id: (msg['id'] ?? '').toString(), keyword: msg['keyword'] == true));
      case 'keyword_status':
        keywordSet = msg['set'] == true;
        notifyListeners();
        _events.add(BotEvent('keyword_status', text, ok: msg['ok'] == true));
      case 'error':
        _events.add(BotEvent('error', text, ok: false));
        if (msg['fatal'] == true) _autoReconnect = false;
      case 'bubble':
        bubbleOn = msg['on'] == true;
        notifyListeners();
      case 'screen_info':
        screenInfo.value = ScreenInfo(
            (msg['width'] as num?)?.toInt() ?? 1920, (msg['height'] as num?)?.toInt() ?? 1080);
      case 'screen_error':
        _events.add(BotEvent('screen_error', text, ok: false));
    }
  }

  /// Tell the PC what we want streamed (mouse position for the eyes, screen frames).
  void _syncSubscriptions() {
    if (!online) return;
    send({'type': 'cursor_track', 'on': _foreground, 'hz': viaRemote ? 8 : 20});
    final q = _screenQuality;
    send({'type': 'screen', 'on': q != null && _foreground, 'quality': q ?? 'medium'});
  }

  void setForeground(bool fg) {
    _foreground = fg;
    _syncSubscriptions();
  }

  void startScreen(String quality) {
    _screenQuality = quality;
    _syncSubscriptions();
  }

  void stopScreen() {
    _screenQuality = null;
    _syncSubscriptions();
  }

  /// Stop the AI task that's running on the PC.
  void stopTask() => send({'type': 'stop'});

  void setBubble(bool on) {
    bubbleOn = on;
    notifyListeners();
    send({'type': 'set_bubble', 'on': on});
  }

  bool send(Map<String, Object?> msg) {
    final ch = _channel;
    if (ch == null) return false;
    ch.sink.add(jsonEncode(msg));
    return true;
  }

  @override
  void dispose() {
    _disposed = true;
    _retryTimer?.cancel();
    _close();
    _frames.close();
    _events.close();
    cursor.dispose();
    screenInfo.dispose();
    super.dispose();
  }
}
