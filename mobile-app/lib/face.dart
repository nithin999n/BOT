import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

const botBlue = Color(0xFF4FC3FF);
const botBlueDeep = Color(0xFF2F7BFF);
const botLight = Color(0xFFB8ECFF);
const botNavy = Color(0xFF0C1430);
const _screenColor = Color(0xFF050A18);

Color _a(Color c, double opacity) => c.withAlpha((opacity.clamp(0.0, 1.0) * 255).round());

enum Mood { idle, listening, thinking, happy, sad, confused, sleepy, surprised, wink, love }

/// Target shape of the face for each mood; the face eases smoothly between them.
class _Shape {
  const _Shape({
    this.openL = 1,
    this.openR = 1,
    this.scale = 1,
    this.arc = 0,
    this.smile = 0.35,
    this.mouthOpen = 0,
    this.blush = 0,
    this.glow = 0.5,
    this.tilt = 0,
    this.sad = 0,
  });
  final double openL, openR, scale, arc, smile, mouthOpen, blush, glow, tilt, sad;
}

const _shapes = <Mood, _Shape>{
  Mood.idle: _Shape(),
  Mood.listening: _Shape(scale: 1.12, smile: 0.2, mouthOpen: 0.2, glow: 0.95),
  Mood.thinking: _Shape(openL: 0.8, openR: 0.55, scale: 0.95, smile: 0, glow: 0.7, tilt: 0.05),
  Mood.happy: _Shape(arc: 1, smile: 0.9, mouthOpen: 0.4, blush: 1, glow: 0.9),
  Mood.sad: _Shape(openL: 0.75, openR: 0.75, smile: -0.6, sad: 1, glow: 0.3),
  Mood.confused: _Shape(openL: 1, openR: 0.5, smile: -0.15, glow: 0.5, tilt: -0.08),
  Mood.sleepy: _Shape(openL: 0.1, openR: 0.1, smile: 0, mouthOpen: 0.18, glow: 0.15),
  Mood.surprised: _Shape(scale: 1.25, smile: 0, mouthOpen: 0.85, glow: 1),
  Mood.wink: _Shape(openL: 1, openR: 0.06, smile: 0.8, blush: 0.6, glow: 0.8),
  Mood.love: _Shape(arc: 1, smile: 1, mouthOpen: 0.2, blush: 1, glow: 1),
};

/// Current (animated) values, read by the painter every frame.
class _FaceState {
  double openL = 1, openR = 1, scale = 1, arc = 0, smile = 0.35, mouthOpen = 0, blush = 0;
  double glow = 0.5, tilt = 0, sad = 0, level = 0, blink = 0, t = 0, excite = 0;
  Offset look = Offset.zero;
  Mood mood = Mood.idle;
}

/// BOT's glowing robot face.
///  * [look]: where the eyes should look (-1..1 each axis), e.g. the PC mouse; null = look around.
///  * [lookStamp]: when [look] last changed; eyes go back to wandering after a few idle seconds.
///  * [level]: microphone loudness 0..1 (mouth and glow react while listening).
class RobotFace extends StatefulWidget {
  const RobotFace({
    super.key,
    required this.mood,
    this.look,
    this.lookStamp,
    this.level = 0,
    this.size = 260,
  });

  final Mood mood;
  final Offset? look;
  final DateTime? lookStamp;
  final double level;
  final double size;

  @override
  State<RobotFace> createState() => _RobotFaceState();
}

class _RobotFaceState extends State<RobotFace> with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  final _repaint = ValueNotifier<int>(0);
  final _s = _FaceState();
  final _rnd = math.Random();
  Duration _last = Duration.zero;
  double _t = 0;
  double _nextBlink = 1.5;
  double _blinkStart = -10;
  double _nextWander = 0;
  Offset _wander = Offset.zero;
  Offset _prevTarget = Offset.zero;

  @override
  void initState() {
    super.initState();
    _ticker = createTicker(_tick)..start();
  }

  @override
  void dispose() {
    _ticker.dispose();
    _repaint.dispose();
    super.dispose();
  }

  double _ease(double cur, double target, double k) => cur + (target - cur) * k;

  void _tick(Duration elapsed) {
    final dt = ((elapsed - _last).inMicroseconds / 1e6).clamp(0.0, 0.1);
    _last = elapsed;
    _t += dt;
    final s = _s;
    final shape = _shapes[widget.mood]!;
    final k = 1 - math.exp(-dt * 10);
    s
      ..mood = widget.mood
      ..openL = _ease(s.openL, shape.openL, k)
      ..openR = _ease(s.openR, shape.openR, k)
      ..arc = _ease(s.arc, shape.arc, k)
      ..smile = _ease(s.smile, shape.smile, k)
      ..mouthOpen = _ease(s.mouthOpen, shape.mouthOpen, k)
      ..blush = _ease(s.blush, shape.blush, k)
      ..glow = _ease(s.glow, shape.glow, k)
      ..tilt = _ease(s.tilt, shape.tilt, k)
      ..sad = _ease(s.sad, shape.sad, k)
      ..level = _ease(s.level, widget.level.clamp(0.0, 1.0), 1 - math.exp(-dt * 18));

    // Blink every few seconds (not while asleep or smiling with ^^ eyes).
    if (_t > _nextBlink) {
      _blinkStart = _t;
      _nextBlink = _t + 2.2 + _rnd.nextDouble() * 3.5;
    }
    final bp = (_t - _blinkStart) / 0.16;
    s.blink = (bp >= 0 && bp <= 1 && widget.mood != Mood.sleepy) ? math.sin(bp * math.pi) : 0;

    // Where to look: the PC mouse (if it moved recently), else look around.
    final stamp = widget.lookStamp;
    final fresh = widget.look != null &&
        stamp != null &&
        DateTime.now().difference(stamp) < const Duration(seconds: 8);
    Offset target;
    if (widget.mood == Mood.thinking) {
      target = Offset(0.55 + 0.25 * math.sin(_t * 1.4), -0.7);
    } else if (widget.mood == Mood.sleepy) {
      target = const Offset(0, 0.4);
    } else if (fresh) {
      target = widget.look!;
    } else {
      if (_t > _nextWander) {
        _wander = _rnd.nextDouble() < 0.35
            ? Offset.zero
            : Offset(_rnd.nextDouble() * 1.4 - 0.7, _rnd.nextDouble() * 1.0 - 0.5);
        _nextWander = _t + 1.5 + _rnd.nextDouble() * 2.5;
      }
      target = _wander;
    }
    // Fast mouse movement -> excited, wider eyes.
    final speed = dt > 0 ? (target - _prevTarget).distance / dt : 0.0;
    _prevTarget = target;
    s.excite = _ease(s.excite, fresh ? (speed / 6).clamp(0.0, 1.0) : 0, 1 - math.exp(-dt * 6));
    s.scale = _ease(s.scale, shape.scale + 0.18 * s.excite, k);
    s.look = Offset.lerp(s.look, target, 1 - math.exp(-dt * (fresh ? 14 : 6)))!;
    s.t = _t;
    _repaint.value++;
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: CustomPaint(painter: _FacePainter(_s, _repaint)),
    );
  }
}

class _FacePainter extends CustomPainter {
  _FacePainter(this.s, Listenable repaint) : super(repaint: repaint);
  final _FaceState s;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final happyBounce = s.arc > 0.5 ? -(math.sin(s.t * 9)).abs() * h * 0.02 : 0.0;
    final bob = math.sin(s.t * 2.0) * h * 0.012 + happyBounce;

    canvas.save();
    canvas.translate(w / 2, h / 2 + bob);
    canvas.rotate(s.tilt);

    final headRect = Rect.fromCenter(center: Offset(0, h * 0.07), width: w * 0.86, height: h * 0.70);
    final headR = RRect.fromRectAndRadius(headRect, Radius.circular(w * 0.24));

    // Antenna with a glowing tip (pulses while listening / thinking).
    final tip = Offset(0, headRect.top - h * 0.11);
    canvas.drawLine(Offset(0, headRect.top), tip,
        Paint()
          ..color = const Color(0xFF2A3A66)
          ..strokeWidth = w * 0.025
          ..strokeCap = StrokeCap.round);
    final pulse = 0.5 + 0.5 * math.sin(s.t * 4);
    final tipGlow = (s.glow * 0.6 + s.level * 0.8 + pulse * 0.2).clamp(0.0, 1.0);
    canvas.drawCircle(tip, w * 0.06,
        Paint()
          ..color = _a(botBlue, 0.45 * tipGlow)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, w * 0.04));
    canvas.drawCircle(tip, w * 0.028, Paint()..color = Color.lerp(const Color(0xFF2A3A66), botBlue, tipGlow)!);

    // Head: outer glow, body, rim.
    canvas.drawRRect(headR.inflate(w * 0.015),
        Paint()
          ..color = _a(botBlue, 0.2 + 0.35 * s.glow + 0.3 * s.level)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, w * 0.06));
    canvas.drawRRect(
        headR,
        Paint()
          ..shader = const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF1B2A55), botNavy],
          ).createShader(headRect));
    canvas.drawRRect(
        headR,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = w * 0.012
          ..color = _a(botBlue, 0.5 + 0.35 * s.glow));

    // Side "ears".
    for (final side in [-1.0, 1.0]) {
      final ear = RRect.fromRectAndRadius(
          Rect.fromCenter(
              center: Offset(side * (headRect.width / 2 + w * 0.025), headRect.center.dy),
              width: w * 0.05,
              height: h * 0.16),
          Radius.circular(w * 0.03));
      canvas.drawRRect(ear, Paint()..color = const Color(0xFF22325F));
    }

    // Screen (the face area).
    final screen = headRect.deflate(w * 0.075);
    final screenR = RRect.fromRectAndRadius(screen, Radius.circular(w * 0.17));
    canvas.drawRRect(screenR, Paint()..color = _screenColor);
    canvas.save();
    canvas.clipRRect(screenR);

    final sw = screen.width, sh = screen.height, c = screen.center;
    final look = Offset(s.look.dx.clamp(-1.0, 1.0) * sw * 0.13, s.look.dy.clamp(-1.0, 1.0) * sh * 0.14);
    final eyeW = sw * 0.15 * s.scale, eyeH = sh * 0.42 * s.scale;
    for (final side in [-1.0, 1.0]) {
      final open = (side < 0 ? s.openL : s.openR) * (1 - s.blink);
      _eye(canvas, Offset(c.dx + side * sw * 0.2, c.dy - sh * 0.08) + look, eyeW, eyeH, open, side);
    }

    // Blush.
    if (s.blush > 0.02) {
      for (final side in [-1.0, 1.0]) {
        canvas.drawOval(
            Rect.fromCenter(center: Offset(c.dx + side * sw * 0.33, c.dy + sh * 0.17), width: sw * 0.15, height: sh * 0.08),
            Paint()
              ..color = _a(const Color(0xFFFF6FA8), 0.45 * s.blush)
              ..maskFilter = MaskFilter.blur(BlurStyle.normal, sw * 0.02));
      }
    }

    _mouth(canvas, Offset(c.dx, c.dy + sh * 0.25) + look * 0.3, sw, sh);

    // Thinking dots.
    if (s.mood == Mood.thinking) {
      for (var i = 0; i < 3; i++) {
        final on = ((s.t * 3).floor() % 3) == i;
        canvas.drawCircle(Offset(c.dx + sw * (0.24 + i * 0.07), screen.top + sh * 0.13), sw * 0.018,
            Paint()..color = _a(botLight, on ? 1.0 : 0.3));
      }
    }

    // Faint scanlines for the "screen" look.
    final scan = Paint()..color = _a(botBlue, 0.04);
    for (var y = screen.top; y < screen.bottom; y += sh * 0.06) {
      canvas.drawRect(Rect.fromLTWH(screen.left, y, sw, sh * 0.015), scan);
    }
    canvas.restore(); // clip

    // Sleepy z's floating up.
    if (s.mood == Mood.sleepy) {
      for (var i = 0; i < 2; i++) {
        final p = ((s.t * 0.5) + i * 0.5) % 1.0;
        final tp = TextPainter(
          text: TextSpan(
              text: 'z',
              style: TextStyle(
                  color: _a(botLight, 1 - p), fontSize: w * (0.07 + 0.04 * i), fontWeight: FontWeight.bold)),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, Offset(headRect.right - w * 0.05 + p * w * 0.06, headRect.top - p * h * 0.12));
      }
    }
    canvas.restore();
  }

  void _eye(Canvas canvas, Offset ec, double ew, double eh, double open, double side) {
    if (s.arc > 0.5) {
      // Happy "^" eyes.
      final path = Path()
        ..moveTo(ec.dx - ew * 0.75, ec.dy + eh * 0.12)
        ..quadraticBezierTo(ec.dx, ec.dy - eh * 0.55, ec.dx + ew * 0.75, ec.dy + eh * 0.12);
      canvas.drawPath(
          path,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeCap = StrokeCap.round
            ..strokeWidth = ew * 0.45
            ..color = _a(botBlue, 0.6)
            ..maskFilter = MaskFilter.blur(BlurStyle.normal, ew * 0.3));
      canvas.drawPath(
          path,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeCap = StrokeCap.round
            ..strokeWidth = ew * 0.32
            ..color = botLight);
      return;
    }
    final eyeHeight = math.max(eh * open, ew * 0.26);
    final r = RRect.fromRectAndRadius(
        Rect.fromCenter(center: ec, width: ew, height: eyeHeight), Radius.circular(ew / 2));
    canvas.drawRRect(
        r.inflate(ew * 0.12),
        Paint()
          ..color = _a(botBlue, 0.55 + 0.3 * s.glow)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, ew * 0.35));
    canvas.drawRRect(
        r,
        Paint()
          ..shader = const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [botLight, botBlue],
          ).createShader(r.outerRect));
    if (open > 0.45) {
      canvas.drawCircle(Offset(ec.dx - ew * 0.17, ec.dy - eyeHeight * 0.25), ew * 0.14,
          Paint()..color = Colors.white.withAlpha(210));
    }
    if (s.sad > 0.05) {
      // Droopy outer corners.
      final top = ec.dy - eyeHeight / 2 - ew * 0.2;
      final outerX = ec.dx + side * ew * 0.75, innerX = ec.dx - side * ew * 0.75;
      final cut = Path()
        ..moveTo(outerX, top)
        ..lineTo(innerX, top)
        ..lineTo(outerX, top + eyeHeight * 0.55 * s.sad)
        ..close();
      canvas.drawPath(cut, Paint()..color = _screenColor);
    }
  }

  void _mouth(Canvas canvas, Offset mc, double sw, double sh) {
    final mw = sw * 0.2;
    final open = (s.mouthOpen + s.level * 0.7).clamp(0.0, 1.0);
    final glow = Paint()
      ..color = _a(botBlue, 0.5)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, sw * 0.02);
    if (open > 0.15 && s.smile > 0.5) {
      // Big "D" smile.
      final depth = sh * (0.06 + open * 0.14);
      final path = Path()
        ..moveTo(mc.dx - mw / 2, mc.dy - depth * 0.3)
        ..lineTo(mc.dx + mw / 2, mc.dy - depth * 0.3)
        ..quadraticBezierTo(mc.dx + mw / 2, mc.dy + depth, mc.dx, mc.dy + depth)
        ..quadraticBezierTo(mc.dx - mw / 2, mc.dy + depth, mc.dx - mw / 2, mc.dy - depth * 0.3)
        ..close();
      canvas.drawPath(path, glow);
      canvas.drawPath(path, Paint()..color = botLight);
    } else if (open > 0.15) {
      // Round "o" mouth (talking / surprised).
      final rect = Rect.fromCenter(center: mc, width: mw * (0.45 + 0.25 * open), height: sh * (0.04 + open * 0.16));
      final rr = RRect.fromRectAndRadius(rect, Radius.circular(rect.shortestSide / 2));
      canvas.drawRRect(rr.inflate(sw * 0.01), glow);
      canvas.drawRRect(rr, Paint()..color = botLight);
      canvas.drawRRect(rr.deflate(sw * 0.014), Paint()..color = const Color(0xFF0A2350));
    } else {
      // Line mouth that curves into a smile or frown.
      final path = Path()
        ..moveTo(mc.dx - mw / 2, mc.dy)
        ..quadraticBezierTo(mc.dx, mc.dy + s.smile * sh * 0.14, mc.dx + mw / 2, mc.dy);
      final stroke = Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round;
      canvas.drawPath(
          path,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeCap = StrokeCap.round
            ..strokeWidth = sw * 0.05
            ..color = _a(botBlue, 0.5)
            ..maskFilter = MaskFilter.blur(BlurStyle.normal, sw * 0.02));
      canvas.drawPath(
          path,
          stroke
            ..strokeWidth = sw * 0.03
            ..color = botLight);
    }
  }

  @override
  bool shouldRepaint(covariant _FacePainter old) => old.s != s;
}
