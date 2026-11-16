import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';
import 'face.dart';
import 'key_bar.dart';

/// The phone becomes a laptop touchpad + keyboard for the PC.
class TouchpadPage extends StatefulWidget {
  const TouchpadPage({super.key, required this.conn});
  final BotConnection conn;

  @override
  State<TouchpadPage> createState() => _TouchpadPageState();
}

class _TouchpadPageState extends State<TouchpadPage> {
  final Map<int, Offset> _fingers = {};
  int _maxFingers = 0;
  DateTime _downAt = DateTime.now();
  double _travel = 0;
  Offset _pendingMove = Offset.zero;
  double _scrollAcc = 0;
  Timer? _flushTimer;
  double _speed = 1.6;
  bool _showKeys = false; // landscape: keyboard only when asked for

  BotConnection get conn => widget.conn;

  @override
  void dispose() {
    _flushTimer?.cancel();
    super.dispose();
  }

  void _down(PointerDownEvent e) {
    if (_fingers.isEmpty) {
      _maxFingers = 0;
      _travel = 0;
      _downAt = DateTime.now();
    }
    _fingers[e.pointer] = e.localPosition;
    _maxFingers = math.max(_maxFingers, _fingers.length);
  }

  void _move(PointerMoveEvent e) {
    final prev = _fingers[e.pointer];
    if (prev == null) return;
    _fingers[e.pointer] = e.localPosition;
    final d = e.localPosition - prev;
    _travel += d.distance;
    if (_fingers.length == 1) {
      final accel = 1 + math.min(d.distance / 12, 2.0); // faster swipe = further
      _pendingMove += d * (_speed * accel);
      _flushTimer ??= Timer(const Duration(milliseconds: 16), _flushMove);
    } else if (_fingers.length == 2) {
      _scrollAcc += d.dy / 2; // both fingers report, so halve
      final notches = (_scrollAcc / 22).truncate();
      if (notches != 0) {
        _scrollAcc -= notches * 22;
        conn.send({'type': 'scroll', 'notches': notches});
      }
    }
  }

  void _flushMove() {
    _flushTimer = null;
    final dx = _pendingMove.dx.round(), dy = _pendingMove.dy.round();
    if (dx == 0 && dy == 0) return;
    _pendingMove -= Offset(dx.toDouble(), dy.toDouble());
    conn.send({'type': 'mouse_move', 'dx': dx, 'dy': dy});
  }

  void _up(PointerEvent e) {
    _fingers.remove(e.pointer);
    if (_fingers.isNotEmpty) return;
    _scrollAcc = 0;
    final quick = DateTime.now().difference(_downAt) < const Duration(milliseconds: 250);
    if (quick && _travel < 14) {
      HapticFeedback.selectionClick();
      conn.send({'type': 'mouse_click', 'button': _maxFingers >= 2 ? 'right' : 'left'});
    }
  }

  Widget _button(String label, String name) {
    final cs = Theme.of(context).colorScheme;
    return Expanded(
      child: GestureDetector(
        onTapDown: (_) {
          HapticFeedback.lightImpact();
          conn.send({'type': 'mouse_button', 'button': name, 'down': true});
        },
        onTapUp: (_) => conn.send({'type': 'mouse_button', 'button': name, 'down': false}),
        onTapCancel: () => conn.send({'type': 'mouse_button', 'button': name, 'down': false}),
        child: Container(
          height: 64,
          margin: const EdgeInsets.all(4),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: cs.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Text(label, style: Theme.of(context).textTheme.titleMedium),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final landscape = MediaQuery.of(context).orientation == Orientation.landscape;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Touchpad'),
        toolbarHeight: landscape ? 44 : null,
        actions: [
          if (landscape)
            IconButton(
              tooltip: 'Keyboard',
              isSelected: _showKeys,
              icon: const Icon(Icons.keyboard),
              onPressed: () => setState(() => _showKeys = !_showKeys),
            ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 4),
              child: Listener(
                onPointerDown: _down,
                onPointerMove: _move,
                onPointerUp: _up,
                onPointerCancel: _up,
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(24),
                    color: const Color(0xFF0E1630),
                    border: Border.all(color: botBlue.withAlpha(120), width: 1.5),
                  ),
                  alignment: Alignment.center,
                  child: const Padding(
                    padding: EdgeInsets.all(24),
                    child: Text(
                      '1 finger: move\ntap: click\n2 fingers: scroll\n2-finger tap: right-click',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.white38, height: 1.6),
                    ),
                  ),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(children: [_button('Left', 'left'), _button('Right', 'right')]),
          ),
          if (!landscape)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(children: [
                const Icon(Icons.speed, size: 20),
                Expanded(
                  child: Slider(
                    value: _speed,
                    min: 0.6,
                    max: 3.5,
                    label: 'Speed',
                    onChanged: (v) => setState(() => _speed = v),
                  ),
                ),
              ]),
            ),
          if (!landscape || _showKeys) KeyBar(conn: conn),
        ],
      ),
    );
  }
}
