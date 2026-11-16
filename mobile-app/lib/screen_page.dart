import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';
import 'face.dart';
import 'key_bar.dart';
import 'style.dart';
import 'voice.dart';

/// Live view of the PC's main monitor. Tap = click (BOT's bubble glides there first),
/// double-tap = double-click, long-press = right-click, pinch = zoom.
/// The little BOT in the corner: tap = cute reaction, hold = talk to it.
/// Turn the phone sideways for a full-screen view (keyboard only when you ask for it).
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
  bool _showKeys = false; // landscape: keyboard bar only when asked for
  bool? _immersive;
  Mood? _flash;
  Timer? _flashTimer;
  int _poke = 0;
  Timer? _holdTimer;
  bool _fingerDown = false, _holdFired = false;
  final _rnd = math.Random();

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
          _waiting = true;
          _showCaption(e.message, keep: true);
        case 'result' || 'error' || 'keyword_status':
          _waiting = false;
          _showCaption(e.message, ok: e.ok);
          _flashMood(e.ok ? (_rnd.nextBool() ? Mood.happy : Mood.excited) : Mood.sad);
      }
    });
    conn.addListener(_refresh);
    voice.addListener(_refresh);
    conn.startScreen(_quality);
  }

  @override
  void dispose() {
    _captionTimer?.cancel();
    _flashTimer?.cancel();
    _holdTimer?.cancel();
    voice.removeListener(_refresh);
    conn.removeListener(_refresh);
    conn.stopScreen();
    _frameSub?.cancel();
    _eventSub?.cancel();
    _zoom.dispose();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  void _refresh() {
    if (mounted) setState(() {});
  }

  void _setImmersive(bool on) {
    if (_immersive == on) return;
    _immersive = on;
    SystemChrome.setEnabledSystemUIMode(on ? SystemUiMode.immersiveSticky : SystemUiMode.edgeToEdge);
  }

  void _setQuality(String q) {
    setState(() => _quality = q);
    conn.startScreen(q);
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

  void _flashMood(Mood m) {
    _flashTimer?.cancel();
    setState(() => _flash = m);
    _flashTimer = Timer(const Duration(milliseconds: 1800), () {
      if (mounted) setState(() => _flash = null);
    });
  }

  void _tap(Offset local, Size size, String button) {
    final u = local.dx / size.width, v = local.dy / size.height;
    if (u < 0 || u > 1 || v < 0 || v > 1) return;
    HapticFeedback.selectionClick();
    conn.send({'type': 'tap', 'u': u, 'v': v, 'button': button});
  }

  // Mini BOT: tap = reaction, hold = talk.
  void _faceDown(PointerDownEvent _) {
    _fingerDown = true;
    _holdFired = false;
    _holdTimer?.cancel();
    _holdTimer = Timer(const Duration(milliseconds: 200), () {
      if (!_fingerDown) return;
      _holdFired = true;
      HapticFeedback.mediumImpact();
      voice.start(widget.locale, (text) {
        widget.onCommand(text);
        if (mounted) {
          _waiting = true;
          _showCaption('“$text”', keep: true);
        }
      });
    });
  }

  void _faceUp(PointerEvent _) {
    if (!_fingerDown) return;
    _fingerDown = false;
    _holdTimer?.cancel();
    if (voice.listening) {
      voice.stop();
    } else if (!_holdFired) {
      HapticFeedback.selectionClick();
      setState(() => _poke++);
      const moods = [Mood.happy, Mood.wink, Mood.love, Mood.shy, Mood.excited];
      _flashMood(moods[_rnd.nextInt(moods.length)]);
    }
  }

  Mood get _mood {
    if (voice.listening) return Mood.listening;
    final flash = _flash;
    if (flash != null) return flash;
    if (_waiting || conn.busy) return Mood.thinking;
    return conn.online ? Mood.idle : Mood.sleepy;
  }

  // ------------------------------------------------------------------ pieces

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

  Widget _overlayCaption() {
    final text = voice.listening ? (voice.heard.isEmpty ? 'Listening…' : voice.heard) : _caption;
    if (text.isEmpty && !conn.busy) return const SizedBox.shrink();
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (text.isNotEmpty)
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xE6111B3A),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                    color: (_captionOk || voice.listening ? botBlue : Colors.redAccent).withAlpha(200)),
              ),
              child: Text(text, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white)),
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

  Widget _miniFace(double size) {
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
          level: voice.listening ? voice.level : 0,
          size: size,
          poke: _poke,
          color: style.value.color,
        ),
      ),
    );
  }

  Widget _qualityMenu({Color? color}) {
    return PopupMenuButton<String>(
      tooltip: 'Quality',
      icon: Icon(Icons.high_quality, color: color),
      onSelected: _setQuality,
      itemBuilder: (_) => [
        CheckedPopupMenuItem(value: 'low', checked: _quality == 'low', child: const Text('Low · saves data')),
        CheckedPopupMenuItem(value: 'medium', checked: _quality == 'medium', child: const Text('Medium')),
        CheckedPopupMenuItem(value: 'high', checked: _quality == 'high', child: const Text('High · Wi-Fi')),
      ],
    );
  }

  Widget _roundButton(IconData icon, String tip, VoidCallback onTap, {bool active = false}) {
    return Padding(
      padding: const EdgeInsets.all(3),
      child: Material(
        color: active ? botBlue.withAlpha(200) : const Color(0x99000000),
        shape: const CircleBorder(),
        child: IconButton(tooltip: tip, icon: Icon(icon, color: Colors.white, size: 20), onPressed: onTap),
      ),
    );
  }

  // ------------------------------------------------------------------ layouts

  Widget _portrait() {
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
          _qualityMenu(),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Stack(
              children: [
                Positioned.fill(child: Center(child: _view())),
                Positioned(left: 10, right: 10, top: 8, child: _overlayCaption()),
                Positioned(right: 4, bottom: 2, child: _miniFace(96)),
              ],
            ),
          ),
          const Padding(
            padding: EdgeInsets.all(6),
            child: Text('Tap = click · long-press = right-click · pinch = zoom · turn sideways for full screen',
                textAlign: TextAlign.center, style: TextStyle(color: Colors.white54, fontSize: 12)),
          ),
          KeyBar(conn: conn),
        ],
      ),
    );
  }

  Widget _landscape() {
    final keyboard = MediaQuery.of(context).viewInsets.bottom;
    return Scaffold(
      backgroundColor: Colors.black,
      resizeToAvoidBottomInset: false, // the phone keyboard must not shrink the PC screen
      body: Stack(
        children: [
          Positioned.fill(child: Center(child: _view())),
          // top-left: back
          Positioned(
            left: 8,
            top: 8,
            child: _roundButton(Icons.arrow_back, 'Back', () => Navigator.of(context).maybePop()),
          ),
          // top-right: keyboard / zoom / quality
          Positioned(
            right: 8,
            top: 8,
            child: Row(children: [
              _roundButton(Icons.keyboard, 'Keyboard', () => setState(() => _showKeys = !_showKeys),
                  active: _showKeys),
              _roundButton(Icons.zoom_out_map, 'Reset zoom', () => _zoom.value = Matrix4.identity()),
              Material(
                color: const Color(0x99000000),
                shape: const CircleBorder(),
                child: _qualityMenu(color: Colors.white),
              ),
            ]),
          ),
          Positioned(left: 70, right: 200, top: 10, child: _overlayCaption()),
          // the cute mini BOT
          Positioned(right: 6, bottom: _showKeys ? 110 + keyboard : 4, child: _miniFace(104)),
          if (_showKeys)
            Positioned(
              left: 0,
              right: 0,
              bottom: keyboard,
              child: KeyBar(conn: conn),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final landscape = MediaQuery.of(context).orientation == Orientation.landscape;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _setImmersive(landscape);
    });
    return landscape ? _landscape() : _portrait();
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
