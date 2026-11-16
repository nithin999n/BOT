import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';
import 'face.dart';
import 'key_bar.dart';

/// Live view of the PC's main monitor. Tap = click (BOT's bubble glides there first),
/// double-tap = double-click, long-press = right-click, pinch = zoom.
class ScreenPage extends StatefulWidget {
  const ScreenPage({super.key, required this.conn});
  final BotConnection conn;

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

  BotConnection get conn => widget.conn;

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
      if (e.type == 'screen_error' && mounted) setState(() => _error = e.message);
    });
    conn.addListener(_onConn);
    conn.startScreen(_quality);
  }

  @override
  void dispose() {
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
          Expanded(child: Center(child: _view())),
          const Padding(
            padding: EdgeInsets.all(6),
            child: Text('Tap = click · double-tap = double-click · long-press = right-click · pinch = zoom',
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
