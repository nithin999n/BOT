import 'dart:async';
import 'dart:convert';
import 'dart:io';
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
  String mac = ''; // the PC's network card, for Wake-on-LAN
  String broadcast = '';
  List<Map<String, dynamic>> routines = [];
  bool petOn = true; // the little BOT on the PC desktop
  Map<String, dynamic> walkaway = {'enabled': false, 'minutes': 1};
  final health = ValueNotifier<Map<String, dynamic>?>(null); // cpu, ram, battery, charging, feeling
  final _fileEvents = StreamController<Map<String, dynamic>>.broadcast();

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
    mac = p.getString('mac') ?? '';
    broadcast = p.getString('broadcast') ?? '';
    notifyListeners();
  }

  Future<void> save() async {
    final p = await SharedPreferences.getInstance();
    await p.setString('host', host);
    await p.setInt('port', port);
    await p.setString('pin', pin);
    await p.setString('pcName', pcName);
    await p.setString('remoteHost', remoteHost);
    await p.setString('mac', mac);
    await p.setString('broadcast', broadcast);
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
        if ((msg['mac'] ?? '').toString().isNotEmpty) {
          mac = msg['mac'].toString();
          broadcast = (msg['broadcast'] ?? '').toString();
        }
        routines = _routinesFrom(msg['routines']);
        petOn = msg['pet'] != false;
        if (msg['walkaway'] is Map) walkaway = Map<String, dynamic>.from(msg['walkaway'] as Map);
        if (msg['health'] is Map) health.value = Map<String, dynamic>.from(msg['health'] as Map);
        final away = msg['away_alerts'];
        if (away is List && away.isNotEmpty) {
          final lines = [
            for (final a in away)
              if (a is Map) '${a['time'] ?? ''}  ${a['title'] ?? ''}: ${a['message'] ?? ''}'
          ];
          _events.add(BotEvent('away', lines.join('\n')));
        }
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
      case 'routines':
        routines = _routinesFrom(msg['items']);
        notifyListeners();
      case 'health':
        health.value = msg;
      case 'alert':
        _events.add(BotEvent('alert', text, id: (msg['title'] ?? 'BOT').toString()));
      case 'pet':
        petOn = msg['on'] == true;
        notifyListeners();
      case 'pet_event': // the desktop BOT was thrown / petted on the PC
        _events.add(BotEvent('pet_event', (msg['event'] ?? '').toString()));
      case 'walkaway':
        walkaway = {'enabled': msg['enabled'] == true, 'minutes': msg['minutes'] ?? 1};
        notifyListeners();
      case 'clip':
        _events.add(BotEvent('clip', (msg['text'] ?? '').toString()));
      case 'file_ack' || 'file_status':
        _fileEvents.add(msg);
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

  static List<Map<String, dynamic>> _routinesFrom(dynamic raw) {
    if (raw is! List) return [];
    return [
      for (final r in raw)
        if (r is Map)
          {
            'name': (r['name'] ?? '').toString(),
            'aliases': [for (final a in (r['aliases'] as List? ?? const [])) a.toString()],
            'steps': [for (final s in (r['steps'] as List? ?? const [])) s.toString()],
          },
    ];
  }

  void saveRoutines(List<Map<String, dynamic>> items) {
    routines = items;
    notifyListeners();
    send({'type': 'routines_set', 'routines': items});
  }

  /// Wake the PC from sleep with a "magic packet" (Wake-on-LAN). Only works on the same
  /// Wi-Fi, and only if the PC's network card supports it.
  Future<bool> wake() async {
    final parts = mac.split(':');
    if (parts.length != 6) return false;
    final macBytes = parts.map((h) => int.parse(h, radix: 16)).toList();
    final packet = Uint8List(102);
    packet.fillRange(0, 6, 0xFF);
    for (var i = 1; i <= 16; i++) {
      packet.setRange(i * 6, i * 6 + 6, macBytes);
    }
    final RawDatagramSocket sock;
    try {
      sock = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
    } catch (_) {
      return false;
    }
    sock.broadcastEnabled = true;
    final targets = <String>{'255.255.255.255', if (broadcast.isNotEmpty) broadcast};
    try {
      for (final iface in await NetworkInterface.list(type: InternetAddressType.IPv4)) {
        for (final a in iface.addresses) {
          final p = a.address.split('.');
          if (p.length == 4 && !a.isLoopback) targets.add('${p[0]}.${p[1]}.${p[2]}.255');
        }
      }
    } catch (_) {}
    for (var round = 0; round < 3; round++) {
      for (final t in targets) {
        for (final port in const [9, 7]) {
          try {
            sock.send(packet, InternetAddress(t), port);
          } catch (_) {}
        }
      }
      await Future<void>.delayed(const Duration(milliseconds: 200));
    }
    sock.close();
    _retryTimer?.cancel();
    _retryTimer = Timer(const Duration(seconds: 6), () {
      if (!_disposed && link == Link.offline && configured) connect();
    });
    return true;
  }

  /// Send a file to the PC (saved in Downloads\BOT). Returns the PC's message.
  Future<String> uploadFile(String name, int size, Stream<List<int>> data, void Function(double) onProgress) async {
    if (!online) throw Exception('Not connected to the PC');
    const chunkSize = 192 * 1024;
    final id = '${DateTime.now().microsecondsSinceEpoch}';

    Future<Map<String, dynamic>> nextEvent() => _fileEvents.stream
        .firstWhere((m) => m['id'] == id)
        .timeout(const Duration(seconds: 30));

    Future<void> expectAck(Future<Map<String, dynamic>> f) async {
      final r = await f;
      if (r['type'] == 'file_status' && r['ok'] != true) throw Exception(r['message'] ?? 'Transfer failed');
    }

    var f = nextEvent();
    send({'type': 'file_begin', 'id': id, 'name': name, 'size': size});
    await expectAck(f);

    var sent = 0;
    final pending = BytesBuilder(copy: false);
    Future<void> flush(Uint8List block) async {
      final ack = nextEvent();
      send({'type': 'file_chunk', 'id': id, 'data': base64Encode(block)});
      await expectAck(ack);
      sent += block.length;
      onProgress(size == 0 ? 1 : sent / size);
    }

    await for (final part in data) {
      pending.add(part);
      if (pending.length >= chunkSize) {
        final all = pending.takeBytes();
        var off = 0;
        while (all.length - off >= chunkSize) {
          await flush(Uint8List.sublistView(all, off, off + chunkSize));
          off += chunkSize;
        }
        if (off < all.length) pending.add(Uint8List.sublistView(all, off));
      }
    }
    if (pending.length > 0) await flush(pending.takeBytes());
    f = nextEvent();
    send({'type': 'file_end', 'id': id});
    final done = await f;
    if (done['ok'] != true) throw Exception(done['message'] ?? 'Transfer failed');
    return (done['message'] ?? 'Saved').toString();
  }

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
    _fileEvents.close();
    cursor.dispose();
    screenInfo.dispose();
    health.dispose();
    super.dispose();
  }
}
