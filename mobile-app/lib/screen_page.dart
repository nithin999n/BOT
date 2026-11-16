import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';
import 'face.dart';
import 'key_bar.dart';
import 'voice.dart';

/// Live view of the PC's main monitor. Tap = click (BOT's bubble glides there first),
/// double-tap = double-click, long-press = right-click, pinch = zoom.
/// Hold the little BOT face in the corner to give it a task while you watch.
class ScreenPage extends StatefulWidget {
  const ScreenPage({
    super.key,
    required this.conn,
    required this.voice,
    required this.locale,
    required this.onCommand,
  });
  final BotConnection conn;
  final Voice voice;
  final String locale;
  final void Function(String text) onCommand;

  @override
  State<ScreenPage> createState() => _ScreenPageState();
}

class _ScreenPageState extends State<ScreenPage> {
  Uint8List? _frame;
  String? _error;
  late String _quality;
  Offset? _doubleTapAt;
  StreamSubscription<Uint8List>? _frameSub;
  StreamSubscription<BotEvent>? _eventSub;
  final _zoom = TransformationController();
  String _caption = '';
  bool _captionOk = true;
  Timer? _captionTimer;
  bool _waiting = false;

  BotConnection get conn => widget.conn;
  Voice get voice => widget.voice;

  @override
  void initState() {
    super.initState();
    _quality = conn.viaRemote ? 'low' : 'medium';
    _frameSub = conn.frames.listen((bytes) {
      conn.send({'type': 'frame_ack'});
      if (mounted) {
        setState(() {
          _frame = bytes;
          _error = null;
        });
      }
    });
    _eventSub = conn.events.listen((e) {
      if (!mounted) return;
      switch (e.type) {
        case 'screen_error':
          setState(() => _error = e.message);
        case 'progress':
          _showCaption(e.message, keep: true);
          _waiting = true;
        case 'result' || 'error' || 'keyword_status':
          _waiting = false;
          _showCaption(e.message, ok: e.ok);
      }
    });
    conn.addListener(_onConn);
    voice.addListener(_onConn);
    conn.startScreen(_quality);
  }

  void _showCaption(String text, {bool ok = true, bool keep = false}) {
    _captionTimer?.cancel();
    setState(() {
      _caption = text;
      _captionOk = ok;
    });
    if (!keep) {
      _captionTimer = Timer(const Duration(seconds: 5), () {
        if (mounted) setState(() => _caption = '');
      });
    }
  }

  void _talkDown(PointerDownEvent _) {
    HapticFeedback.mediumImpact();
    voice.start(widget.locale, (text) {
      widget.onCommand(text);
      if (mounted) {
        _waiting = true;
        _showCaption('“$text”', keep: true);
      }
    });
  }

  void _talkUp(PointerEvent _) => voice.stop();

  Mood get _mood {
    if (voice.listening) return Mood.listening;
    if (_waiting || conn.busy) return Mood.thinking;
    if (_caption.isNotEmpty) return _captionOk ? Mood.happy : Mood.sad;
    return conn.online ? Mood.idle : Mood.sleepy;
  }

  Widget _overlayCaption() {
    final text = voice.listening ? (voice.heard.isEmpty ? 'Listening…' : voice.heard) : _caption;
    if (text.isEmpty && !conn.busy) return const SizedBox.shrink();
    return Row(
      children: [
        if (text.isNotEmpty)
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xE6111B3A),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: (_captionOk || voice.listening ? botBlue : Colors.redAccent).withAlpha(200)),
              ),
              child: Text(text,
                  maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white)),
            ),
          ),
        if (conn.busy) ...[
          const SizedBox(width: 8),
          FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () {
              HapticFeedback.mediumImpact();
              conn.stopTask();
            },
            icon: const Icon(Icons.stop),
            label: const Text('Stop'),
          ),
        ],
      ],
    );
  }

  Widget _miniFace() {
    return ValueListenableBuilder<CursorPos?>(
      valueListenable: conn.cursor,
      builder: (context, c, _) => Listener(
        onPointerDown: _talkDown,
        onPointerUp: _talkUp,
        onPointerCancel: _talkUp,
        child: RobotFace(
          mood: _mood,
          look: c == null ? null : Offset(c.vx * 2 - 1, c.vy * 2 - 1),
          lookStamp: c?.at,
          level: voice.listening ? voice.level : 0,
          size: 84,
        ),
      ),
    );
  }

  @override
  void dispose() {
    _captionTimer?.cancel();
    voice.removeListener(_onConn);
    conn.removeListener(_onConn);
    conn.stopScreen();
    _frameSub?.cancel();
    _eventSub?.cancel();
    _zoom.dispose();
    super.dispose();
  }

  void _onConn() {
    if (mounted) setState(() {});
  }

  void _setQuality(String q) {
    setState(() => _quality = q);
    conn.startScreen(q);
  }

  void _tap(Offset local, Size size, String button) {
    final u = local.dx / size.width, v = local.dy / size.height;
    if (u < 0 || u > 1 || v < 0 || v > 1) return;
    HapticFeedback.selectionClick();
    conn.send({'type': 'tap', 'u': u, 'v': v, 'button': button});
  }

  Widget _view() {
    final frame = _frame;
    if (!conn.online) {
      return const Text('Not connected to the PC', style: TextStyle(color: Colors.white70));
    }
    if (frame == null) {
      return Column(mainAxisSize: MainAxisSize.min, children: [
        if (_error == null) const CircularProgressIndicator(),
        const SizedBox(height: 12),
        Text(_error ?? 'Waiting for the PC screen…', style: const TextStyle(color: Colors.white70)),
      ]);
    }
    return ValueListenableBuilder<ScreenInfo?>(
      valueListenable: conn.screenInfo,
      builder: (context, info, _) {
        final aspect = info == null ? 16 / 9 : info.width / info.height;
        return InteractiveViewer(
          transformationController: _zoom,
          maxScale: 5,
          child: Center(
            child: AspectRatio(
              aspectRatio: aspect,
              child: LayoutBuilder(builder: (context, box) {
                final size = box.biggest;
                return GestureDetector(
                  onTapUp: (d) => _tap(d.localPosition, size, 'left'),
                  onDoubleTapDown: (d) => _doubleTapAt = d.localPosition,
                  onDoubleTap: () {
                    final at = _doubleTapAt;
                    if (at != null) _tap(at, size, 'double');
                  },
                  onLongPressStart: (d) => _tap(d.localPosition, size, 'right'),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.memory(frame, gaplessPlayback: true, fit: BoxFit.fill),
                      ValueListenableBuilder<CursorPos?>(
                        valueListenable: conn.cursor,
                        builder: (context, c, _) {
                          if (c == null || c.mx < 0 || c.mx > 1 || c.my < 0 || c.my > 1) {
                            return const SizedBox.shrink();
                          }
                          return Positioned(
                            left: c.mx * size.width - 9,
                            top: c.my * size.height - 9,
                            child: IgnorePointer(child: _CursorDot(bot: c.bot)),
                          );
                        },
                      ),
                    ],
                  ),
                );
              }),
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: Text(conn.viaRemote ? 'PC screen · outside' : 'PC screen'),
        actions: [
          IconButton(
            tooltip: 'Reset zoom',
            icon: const Icon(Icons.zoom_out_map),
            onPressed: () => _zoom.value = Matrix4.identity(),
          ),
          PopupMenuButton<String>(
            tooltip: 'Quality',
            icon: const Icon(Icons.high_quality),
            onSelected: _setQuality,
            itemBuilder: (_) => [
              CheckedPopupMenuItem(value: 'low', checked: _quality == 'low', child: const Text('Low · saves data')),
              CheckedPopupMenuItem(value: 'medium', checked: _quality == 'medium', child: const Text('Medium')),
              CheckedPopupMenuItem(value: 'high', checked: _quality == 'high', child: const Text('High · Wi-Fi')),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Stack(
              children: [
                Positioned.fill(child: Center(child: _view())),
                Positioned(left: 10, right: 10, top: 8, child: _overlayCaption()),
                Positioned(right: 6, bottom: 4, child: _miniFace()),
              ],
            ),
          ),
          const Padding(
            padding: EdgeInsets.all(6),
            child: Text('Tap = click · long-press = right-click · pinch = zoom · hold BOT to talk',
                textAlign: TextAlign.center, style: TextStyle(color: Colors.white54, fontSize: 12)),
          ),
          KeyBar(conn: conn),
        ],
      ),
    );
  }
}

class _CursorDot extends StatelessWidget {
  const _CursorDot({required this.bot});
  final bool bot;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 18,
      height: 18,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: bot ? botBlue.withAlpha(170) : Colors.white,
        border: Border.all(color: bot ? Colors.white : Colors.black, width: 2),
        boxShadow: bot ? [BoxShadow(color: botBlue.withAlpha(150), blurRadius: 10)] : null,
      ),
    );
  }
}
