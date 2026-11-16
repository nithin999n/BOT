import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';

/// Phone as a game controller: joystick (WASD or arrows) + action buttons, all hold-able.
class GamepadPage extends StatefulWidget {
  const GamepadPage({super.key, required this.conn});
  final BotConnection conn;

  @override
  State<GamepadPage> createState() => _GamepadPageState();
}

class _GamepadPageState extends State<GamepadPage> {
  bool _wasd = true;
  final Set<String> _stickKeys = {};
  final Set<String> _held = {};
  Offset _knob = Offset.zero; // -1..1

  BotConnection get conn => widget.conn;

  @override
  void initState() {
    super.initState();
    SystemChrome.setPreferredOrientations([DeviceOrientation.landscapeLeft, DeviceOrientation.landscapeRight]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  }

  @override
  void dispose() {
    for (final k in _held) {
      conn.send({'type': 'key_state', 'key': k, 'down': false}); // never leave a key stuck
    }
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  void _key(String k, bool down) {
    if (down ? !_held.add(k) : !_held.remove(k)) return;
    conn.send({'type': 'key_state', 'key': k, 'down': down});
  }

  // ---- joystick ------------------------------------------------------------------
  void _stick(Offset local, double size) {
    final c = Offset(size / 2, size / 2);
    var v = (local - c) / (size / 2);
    if (v.distance > 1) v = v / v.distance;
    final want = <String>{};
    if (v.distance > 0.3) {
      if (v.dy < -0.38) want.add(_wasd ? 'w' : 'up');
      if (v.dy > 0.38) want.add(_wasd ? 's' : 'down');
      if (v.dx < -0.38) want.add(_wasd ? 'a' : 'left');
      if (v.dx > 0.38) want.add(_wasd ? 'd' : 'right');
    }
    for (final k in _stickKeys.difference(want)) {
      _key(k, false);
    }
    for (final k in want.difference(_stickKeys)) {
      _key(k, true);
      HapticFeedback.selectionClick();
    }
    _stickKeys
      ..clear()
      ..addAll(want);
    setState(() => _knob = v);
  }

  void _stickRelease() {
    for (final k in _stickKeys) {
      _key(k, false);
    }
    _stickKeys.clear();
    setState(() => _knob = Offset.zero);
  }

  Widget _joystick(double size) {
    final cs = Theme.of(context).colorScheme;
    return Listener(
      onPointerDown: (e) => _stick(e.localPosition, size),
      onPointerMove: (e) => _stick(e.localPosition, size),
      onPointerUp: (_) => _stickRelease(),
      onPointerCancel: (_) => _stickRelease(),
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: const Color(0xFF111B3A),
          border: Border.all(color: cs.primary.withAlpha(120), width: 2),
        ),
        child: Stack(children: [
          for (final (a, label) in [(Alignment.topCenter, '▲'), (Alignment.bottomCenter, '▼'),
            (Alignment.centerLeft, '◀'), (Alignment.centerRight, '▶')])
            Align(
              alignment: a,
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Text(label, style: TextStyle(color: cs.primary.withAlpha(150), fontSize: 18)),
              ),
            ),
          Align(
            alignment: Alignment(_knob.dx, _knob.dy),
            child: Container(
              width: size * 0.36,
              height: size * 0.36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: cs.primary,
                boxShadow: [BoxShadow(color: cs.primary.withAlpha(140), blurRadius: 16)],
              ),
            ),
          ),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF070C1C),
      body: SafeArea(
        child: LayoutBuilder(builder: (context, box) {
          final stick = math.min(box.maxHeight * 0.78, box.maxWidth * 0.36);
          final btn = math.min(box.maxHeight * 0.2, 78.0);
          return Stack(children: [
            // left: joystick
            Positioned(left: 24, bottom: 16, child: _joystick(stick)),
            // top middle: small keys + mode
            Positioned(
              top: 8,
              left: 0,
              right: 0,
              child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                IconButton(
                  tooltip: 'Back',
                  icon: const Icon(Icons.arrow_back, color: Colors.white70),
                  onPressed: () => Navigator.of(context).maybePop(),
                ),
                for (final (k, l) in [('esc', 'Esc'), ('tab', 'Tab'), ('enter', 'Enter')])
                  _GameButton(label: l, size: btn * 0.62, onChange: (d) => _key(k, d), small: true),
                const SizedBox(width: 8),
                SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: true, label: Text('WASD')),
                    ButtonSegment(value: false, label: Text('Arrows')),
                  ],
                  selected: {_wasd},
                  onSelectionChanged: (s) {
                    _stickRelease();
                    setState(() => _wasd = s.first);
                  },
                ),
              ]),
            ),
            // right: action buttons in a diamond + shift/ctrl
            Positioned(
              right: 24,
              bottom: 16,
              child: SizedBox(
                width: btn * 3.2,
                height: btn * 3.2,
                child: Stack(children: [
                  Align(alignment: Alignment.topCenter, child: _GameButton(label: 'Q', size: btn, onChange: (d) => _key('q', d))),
                  Align(alignment: Alignment.centerLeft, child: _GameButton(label: 'F', size: btn, onChange: (d) => _key('f', d))),
                  Align(alignment: Alignment.centerRight, child: _GameButton(label: 'E', size: btn, onChange: (d) => _key('e', d))),
                  Align(
                      alignment: Alignment.bottomCenter,
                      child: _GameButton(label: 'Jump', size: btn * 1.15, onChange: (d) => _key('space', d))),
                ]),
              ),
            ),
            Positioned(
              right: btn * 3.2 + 40,
              bottom: 16,
              child: Column(children: [
                _GameButton(label: 'R', size: btn * 0.8, onChange: (d) => _key('r', d)),
                const SizedBox(height: 10),
                _GameButton(label: 'Shift', size: btn * 0.8, onChange: (d) => _key('shift', d)),
                const SizedBox(height: 10),
                _GameButton(label: 'Ctrl', size: btn * 0.8, onChange: (d) => _key('ctrl', d)),
              ]),
            ),
          ]);
        }),
      ),
    );
  }
}

/// A round button that reports press and release (so keys can be held in games).
class _GameButton extends StatefulWidget {
  const _GameButton({required this.label, required this.size, required this.onChange, this.small = false});
  final String label;
  final double size;
  final void Function(bool down) onChange;
  final bool small;

  @override
  State<_GameButton> createState() => _GameButtonState();
}

class _GameButtonState extends State<_GameButton> {
  bool _down = false;

  void _set(bool down) {
    if (_down == down) return;
    setState(() => _down = down);
    if (down) HapticFeedback.lightImpact();
    widget.onChange(down);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: EdgeInsets.all(widget.small ? 4 : 0),
      child: Listener(
        onPointerDown: (_) => _set(true),
        onPointerUp: (_) => _set(false),
        onPointerCancel: (_) => _set(false),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 60),
          width: widget.size,
          height: widget.small ? widget.size * 0.7 : widget.size,
          decoration: BoxDecoration(
            shape: widget.small ? BoxShape.rectangle : BoxShape.circle,
            borderRadius: widget.small ? BorderRadius.circular(12) : null,
            color: _down ? cs.primary : const Color(0xFF16224D),
            border: Border.all(color: cs.primary.withAlpha(160), width: 2),
            boxShadow: _down ? [BoxShadow(color: cs.primary.withAlpha(150), blurRadius: 14)] : null,
          ),
          alignment: Alignment.center,
          child: Text(widget.label,
              style: TextStyle(
                  color: _down ? cs.onPrimary : Colors.white,
                  fontWeight: FontWeight.w700,
                  fontSize: widget.small ? 13 : 16)),
        ),
      ),
    );
  }
}
