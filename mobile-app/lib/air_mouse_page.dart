import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:sensors_plus/sensors_plus.dart';

import 'connection.dart';

/// Point the phone like a TV remote: hold the pad and the PC cursor follows your phone.
/// Quick tap on the pad = click. Great for presentations or from the bed.
class AirMousePage extends StatefulWidget {
  const AirMousePage({super.key, required this.conn});
  final BotConnection conn;

  @override
  State<AirMousePage> createState() => _AirMousePageState();
}

class _AirMousePageState extends State<AirMousePage> {
  StreamSubscription<GyroscopeEvent>? _gyro;
  bool _aiming = false;
  bool _flipY = false;
  double _speed = 22;
  Offset _pending = Offset.zero;
  Timer? _flush;
  DateTime _downAt = DateTime.now();
  double _moved = 0;
  String? _error;

  BotConnection get conn => widget.conn;

  @override
  void initState() {
    super.initState();
    try {
      _gyro = gyroscopeEventStream(samplingPeriod: SensorInterval.gameInterval).listen(
        _onGyro,
        onError: (Object _) => setState(() => _error = 'This phone has no gyroscope, so Air Mouse can\'t work.'),
      );
    } catch (_) {
      _error = 'This phone has no gyroscope, so Air Mouse can\'t work.';
    }
  }

  @override
  void dispose() {
    _gyro?.cancel();
    _flush?.cancel();
    super.dispose();
  }

  void _onGyro(GyroscopeEvent e) {
    if (!_aiming) return;
    // turn left/right = yaw (z), tilt up/down = pitch (x); ignore tiny hand shake
    final yaw = e.z.abs() < 0.03 ? 0.0 : e.z;
    final pitch = e.x.abs() < 0.03 ? 0.0 : e.x;
    final d = Offset(-yaw * _speed, (_flipY ? pitch : -pitch) * _speed);
    _pending += d;
    _moved += d.distance;
    _flush ??= Timer(const Duration(milliseconds: 16), _send);
  }

  void _send() {
    _flush = null;
    final dx = _pending.dx.round(), dy = _pending.dy.round();
    if (dx == 0 && dy == 0) return;
    _pending -= Offset(dx.toDouble(), dy.toDouble());
    conn.send({'type': 'mouse_move', 'dx': dx, 'dy': dy});
  }

  void _down(PointerDownEvent _) {
    HapticFeedback.lightImpact();
    _downAt = DateTime.now();
    _moved = 0;
    _pending = Offset.zero;
    setState(() => _aiming = true);
  }

  void _up(PointerEvent _) {
    setState(() => _aiming = false);
    final quick = DateTime.now().difference(_downAt) < const Duration(milliseconds: 220);
    if (quick && _moved < 25) {
      HapticFeedback.selectionClick();
      conn.send({'type': 'mouse_click', 'button': 'left'});
    }
  }

  Widget _btn(String label, IconData icon, VoidCallback onTap) {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.all(4),
        child: FilledButton.tonalIcon(
          style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16)),
          onPressed: () {
            HapticFeedback.selectionClick();
            onTap();
          },
          icon: Icon(icon),
          label: Text(label),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Air mouse')),
      body: SafeArea(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 4, 16, 8),
              child: Text('Hold the phone like a TV remote. Press and hold the pad, then point and move. '
                  'Quick tap = click.', textAlign: TextAlign.center),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Listener(
                  onPointerDown: _down,
                  onPointerUp: _up,
                  onPointerCancel: _up,
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 120),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(32),
                      color: _aiming ? cs.primary.withAlpha(70) : const Color(0xFF0E1630),
                      border: Border.all(color: cs.primary.withAlpha(_aiming ? 255 : 110), width: 2),
                    ),
                    alignment: Alignment.center,
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Icon(_aiming ? Icons.near_me : Icons.ads_click, size: 64, color: cs.primary),
                      const SizedBox(height: 8),
                      Text(_error ?? (_aiming ? 'Pointing…' : 'Hold here to aim'),
                          textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium),
                    ]),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Row(children: [
                _btn('Left', Icons.mouse, () => conn.send({'type': 'mouse_click', 'button': 'left'})),
                _btn('Right', Icons.more_horiz, () => conn.send({'type': 'mouse_click', 'button': 'right'})),
              ]),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Row(children: [
                _btn('Slide', Icons.chevron_left, () => conn.send({'type': 'key', 'key': 'left'})),
                _btn('Slide', Icons.chevron_right, () => conn.send({'type': 'key', 'key': 'right'})),
              ]),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(children: [
                const Icon(Icons.speed, size: 20),
                Expanded(
                  child: Slider(value: _speed, min: 8, max: 45, onChanged: (v) => setState(() => _speed = v)),
                ),
                const Text('Flip ↕'),
                Switch(value: _flipY, onChanged: (v) => setState(() => _flipY = v)),
              ]),
            ),
          ],
        ),
      ),
    );
  }
}
