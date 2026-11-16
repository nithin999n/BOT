import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

const botBlue = Color(0xFF4FC3FF);
const botBlueDeep = Color(0xFF2F7BFF);
const botLight = Color(0xFFB8ECFF);
const botNavy = Color(0xFF0C1430);
const botPink = Color(0xFFFF7EB6);
const _screenColor = Color(0xFF060B1E);

Color _a(Color c, double opacity) => c.withAlpha((opacity.clamp(0.0, 1.0) * 255).round());

enum Mood { idle, listening, thinking, happy, sad, confused, sleepy, surprised, wink, love, shy, excited, dizzy }

/// Target shape of the face for each mood; the face eases smoothly between them.
class _Shape {
  const _Shape({
    this.openL = 1,
    this.openR = 1,
    this.scale = 1,
    this.arc = 0,
    this.heart = 0,
    this.star = 0,
    this.spiral = 0,
    this.smile = 0.45,
    this.mouthOpen = 0,
    this.cat = 0,
    this.blush = 0,
    this.shy = 0,
    this.glow = 0.55,
    this.tilt = 0,
    this.sad = 0,
  });
  final double openL, openR, scale, arc, heart, star, spiral, smile, mouthOpen, cat, blush, shy, glow, tilt, sad;
}

const _shapes = <Mood, _Shape>{
  Mood.idle: _Shape(cat: 1),
  Mood.listening: _Shape(scale: 1.12, smile: 0.3, mouthOpen: 0.22, glow: 1, blush: 0.3),
  Mood.thinking: _Shape(openL: 0.85, openR: 0.6, scale: 0.95, smile: 0.05, glow: 0.7, tilt: 0.06),
  Mood.happy: _Shape(arc: 1, smile: 0.9, mouthOpen: 0.45, blush: 0.9, glow: 0.95),
  Mood.sad: _Shape(openL: 0.8, openR: 0.8, smile: -0.6, sad: 1, glow: 0.3, scale: 0.95),
  Mood.confused: _Shape(openL: 1.05, openR: 0.5, smile: -0.15, glow: 0.5, tilt: -0.1),
  Mood.sleepy: _Shape(openL: 0.1, openR: 0.1, smile: 0.1, mouthOpen: 0.18, glow: 0.15),
  Mood.surprised: _Shape(scale: 1.25, smile: 0, mouthOpen: 0.85, glow: 1),
  Mood.wink: _Shape(openL: 1, openR: 0.06, smile: 0.85, blush: 0.8, glow: 0.85, cat: 1),
  Mood.love: _Shape(heart: 1, smile: 0.8, cat: 1, blush: 1, glow: 1),
  Mood.shy: _Shape(openL: 0.6, openR: 0.6, smile: 0.3, blush: 1, shy: 1, glow: 0.6, tilt: 0.08),
  Mood.excited: _Shape(star: 1, smile: 1, mouthOpen: 0.6, blush: 0.8, glow: 1, scale: 1.05),
  Mood.dizzy: _Shape(spiral: 1, smile: -0.1, mouthOpen: 0.12, glow: 0.45, tilt: 0.05),
};

class _Particle {
  _Particle(this.kind, this.x, this.y, this.vx, this.vy, this.life, this.size, this.spin)
      : max = life;
  final String kind; // heart, sparkle, q, ex, z, note
  double x, y; // relative to the face centre, in face widths
  final double vx, vy, size, spin, max;
  double life;
}

/// Current (animated) values, read by the painter every frame.
class _FaceState {
  double openL = 1, openR = 1, scale = 1, arc = 0, heart = 0, star = 0, spiral = 0, smile = 0.45;
  double mouthOpen = 0, cat = 1, blush = 0, shy = 0, glow = 0.55, tilt = 0, sad = 0, level = 0;
  double blink = 0, t = 0, excite = 0, squish = 0, hop = 0, antenna = 0, yawn = 0, sparkle = 0;
  Offset look = Offset.zero;
  Mood mood = Mood.idle;
  final particles = <_Particle>[];
}

/// BOT's glowing robot face.
///  * [look]: where the eyes should look (-1..1 each axis), e.g. the PC mouse; null = look around.
///  * [lookStamp]: when [look] last changed; eyes go back to wandering after a few idle seconds.
///  * [level]: microphone loudness 0..1 (mouth and glow react while listening).
///  * [poke]: increase it to make BOT squish (on tap).
class RobotFace extends StatefulWidget {
  const RobotFace({
    super.key,
    required this.mood,
    this.look,
    this.lookStamp,
    this.level = 0,
    this.size = 260,
    this.poke = 0,
  });

  final Mood mood;
  final Offset? look;
  final DateTime? lookStamp;
  final double level;
  final double size;
  final int poke;

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
  double _nextBlink = 1.5, _blinkStart = -10, _secondBlink = -1;
  double _nextWander = 0;
  Offset _wander = Offset.zero;
  Offset _prevTarget = Offset.zero;
  // idle habits
  String _habit = '';
  double _habitUntil = 0, _nextHabit = 4, _lastActive = 0, _nextParticle = 0;
  // springs
  double _hopV = 0, _antV = 0;

  @override
  void initState() {
    super.initState();
    _ticker = createTicker(_tick)..start();
  }

  @override
  void didUpdateWidget(covariant RobotFace old) {
    super.didUpdateWidget(old);
    if (old.poke != widget.poke) {
      _s.squish = 1;
      _antV += 9;
      _hopV -= 1.2;
      _lastActive = _t;
    }
    if (old.mood != widget.mood) {
      _lastActive = _t;
      _onMood(widget.mood);
    }
  }

  @override
  void dispose() {
    _ticker.dispose();
    _repaint.dispose();
    super.dispose();
  }

  double _ease(double cur, double target, double k) => cur + (target - cur) * k;
  double _r(double a, double b) => a + _rnd.nextDouble() * (b - a);

  void _burst(String kind, int n, {double speed = 0.35, double size = 0.07}) {
    for (var i = 0; i < n; i++) {
      final angle = _r(-math.pi * 0.95, -math.pi * 0.05); // upwards fan
      final v = _r(speed * 0.5, speed);
      _s.particles.add(_Particle(kind, _r(-0.25, 0.25), _r(-0.2, 0.05), math.cos(angle) * v * 0.6,
          math.sin(angle) * v, _r(1.2, 2.0), _r(size * 0.7, size * 1.2), _r(-2, 2)));
    }
  }

  void _onMood(Mood m) {
    switch (m) {
      case Mood.love:
        _burst('heart', 6);
        _antV += 6;
      case Mood.happy || Mood.excited:
        _burst('sparkle', 7);
        _hopV -= 1.6;
        _antV += 5;
      case Mood.wink:
        _burst('heart', 1);
        _burst('sparkle', 2);
      case Mood.shy:
        _burst('heart', 2, size: 0.05);
      case Mood.confused || Mood.dizzy:
        _burst('q', 2, speed: 0.25, size: 0.09);
      case Mood.surprised:
        _burst('ex', 1, speed: 0.3, size: 0.11);
        _hopV -= 2.2;
      default:
        break;
    }
  }

  void _tick(Duration elapsed) {
    final dt = ((elapsed - _last).inMicroseconds / 1e6).clamp(0.0, 0.1);
    _last = elapsed;
    _t += dt;
    final s = _s;
    final mood = widget.mood;
    final shape = _shapes[mood]!;
    final k = 1 - math.exp(-dt * 10);

    // ---- idle habits (only when nothing else is going on) -----------------------
    final stamp = widget.lookStamp;
    final fresh = widget.look != null &&
        stamp != null &&
        DateTime.now().difference(stamp) < const Duration(seconds: 8);
    if (fresh) _lastActive = _t;
    if (mood == Mood.idle && !fresh) {
      if (_habit.isEmpty && _t > _nextHabit) {
        final idleFor = _t - _lastActive;
        const habits = ['glance', 'doubleblink', 'tilt', 'wiggle', 'hop', 'sparkle', 'smile'];
        _habit = idleFor > 40 && _rnd.nextDouble() < 0.5 ? 'yawn' : habits[_rnd.nextInt(habits.length)];
        _habitUntil = _t + (_habit == 'yawn' ? 2.2 : 1.6);
        switch (_habit) {
          case 'doubleblink':
            _blinkStart = _t;
            _secondBlink = _t + 0.28;
          case 'wiggle':
            _antV += 10;
          case 'hop':
            _hopV -= 1.8;
          case 'sparkle':
            _burst('sparkle', 3, speed: 0.2, size: 0.05);
          case 'yawn':
            _lastActive = _t;
        }
      }
      if (_habit.isNotEmpty && _t > _habitUntil) {
        _habit = '';
        _nextHabit = _t + _r(4, 8);
      }
    } else {
      _habit = '';
      _nextHabit = _t + _r(3, 6);
    }

    double smileT = shape.smile, tiltT = shape.tilt, openBias = 1, yawnT = 0;
    if (_habit == 'tilt') tiltT += 0.13 * math.sin(math.min(1.0, _habitUntil - _t) * math.pi);
    if (_habit == 'smile' || _habit == 'glance') smileT = 0.75;
    if (_habit == 'yawn') {
      yawnT = 1;
      openBias = 0.35;
    }

    s
      ..mood = mood
      ..openL = _ease(s.openL, shape.openL * openBias, k)
      ..openR = _ease(s.openR, shape.openR * openBias, k)
      ..arc = _ease(s.arc, shape.arc, k)
      ..heart = _ease(s.heart, shape.heart, k)
      ..star = _ease(s.star, shape.star, k)
      ..spiral = _ease(s.spiral, shape.spiral, k)
      ..smile = _ease(s.smile, smileT, k)
      ..mouthOpen = _ease(s.mouthOpen, shape.mouthOpen, k)
      ..cat = _ease(s.cat, shape.cat, k)
      ..blush = _ease(s.blush, shape.blush, k)
      ..shy = _ease(s.shy, shape.shy, k)
      ..glow = _ease(s.glow, shape.glow, k)
      ..tilt = _ease(s.tilt, tiltT, 1 - math.exp(-dt * 6))
      ..sad = _ease(s.sad, shape.sad, k)
      ..yawn = _ease(s.yawn, yawnT, 1 - math.exp(-dt * 5))
      ..level = _ease(s.level, widget.level.clamp(0.0, 1.0), 1 - math.exp(-dt * 18));

    // ---- blinking ------------------------------------------------------------------
    if (_t > _nextBlink) {
      _blinkStart = _t;
      _nextBlink = _t + _r(2.2, 5.5);
      if (_rnd.nextDouble() < 0.2) _secondBlink = _t + 0.28;
    }
    if (_secondBlink > 0 && _t > _secondBlink) {
      _blinkStart = _t;
      _secondBlink = -1;
    }
    final bp = (_t - _blinkStart) / 0.16;
    s.blink = (bp >= 0 && bp <= 1 && mood != Mood.sleepy) ? math.sin(bp * math.pi) : 0;

    // ---- where to look -------------------------------------------------------------
    Offset target;
    if (mood == Mood.thinking) {
      target = Offset(0.55 + 0.25 * math.sin(_t * 1.4), -0.7);
    } else if (mood == Mood.sleepy) {
      target = const Offset(0, 0.4);
    } else if (mood == Mood.shy) {
      target = Offset(-0.5, 0.6 + 0.1 * math.sin(_t * 2));
    } else if (fresh) {
      target = widget.look!;
    } else if (_habit == 'glance' || _habit == 'smile') {
      target = Offset.zero; // look at you
    } else {
      if (_t > _nextWander) {
        _wander = _rnd.nextDouble() < 0.35 ? Offset.zero : Offset(_r(-0.7, 0.7), _r(-0.5, 0.5));
        _nextWander = _t + _r(1.5, 4);
      }
      target = _wander;
    }
    final speed = dt > 0 ? (target - _prevTarget).distance / dt : 0.0;
    _prevTarget = target;
    s.excite = _ease(s.excite, fresh ? (speed / 6).clamp(0.0, 1.0) : 0, 1 - math.exp(-dt * 6));
    s.scale = _ease(s.scale, shape.scale + 0.18 * s.excite, k);
    s.look = Offset.lerp(s.look, target, 1 - math.exp(-dt * (fresh ? 14 : 6)))!;

    // ---- springs: squish, hop, antenna ---------------------------------------------
    s.squish = math.max(0, s.squish - dt * 3.5);
    _hopV += (-s.hop * 60 - _hopV * 9) * dt;
    s.hop += _hopV * dt;
    final antTarget = math.sin(_t * 1.3) * 0.06 + (mood == Mood.listening ? s.level * 0.2 : 0);
    _antV += (-(s.antenna - antTarget) * 120 - _antV * 7) * dt;
    s.antenna += _antV * dt;
    s.sparkle = 0.5 + 0.5 * math.sin(_t * 3.1);

    // ---- particles ------------------------------------------------------------------
    if (_t > _nextParticle) {
      _nextParticle = _t + 1.1;
      if (mood == Mood.sleepy) _burst('z', 1, speed: 0.12, size: 0.07);
      if (mood == Mood.love) _burst('heart', 1, speed: 0.2, size: 0.05);
      if (mood == Mood.excited) _burst('sparkle', 1, speed: 0.2, size: 0.05);
    }
    for (final p in s.particles) {
      p.life -= dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
    }
    s.particles.removeWhere((p) => p.life <= 0);

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

// ---- shapes -----------------------------------------------------------------------

Path _heartPath(Offset c, double s) {
  return Path()
    ..moveTo(c.dx, c.dy + s * 0.42)
    ..cubicTo(c.dx - s * 1.05, c.dy - s * 0.2, c.dx - s * 0.5, c.dy - s * 0.95, c.dx, c.dy - s * 0.42)
    ..cubicTo(c.dx + s * 0.5, c.dy - s * 0.95, c.dx + s * 1.05, c.dy - s * 0.2, c.dx, c.dy + s * 0.42)
    ..close();
}

Path _sparklePath(Offset c, double r) {
  return Path()
    ..moveTo(c.dx, c.dy - r)
    ..quadraticBezierTo(c.dx + r * 0.16, c.dy - r * 0.16, c.dx + r, c.dy)
    ..quadraticBezierTo(c.dx + r * 0.16, c.dy + r * 0.16, c.dx, c.dy + r)
    ..quadraticBezierTo(c.dx - r * 0.16, c.dy + r * 0.16, c.dx - r, c.dy)
    ..quadraticBezierTo(c.dx - r * 0.16, c.dy - r * 0.16, c.dx, c.dy - r)
    ..close();
}

Path _starPath(Offset c, double r, double rotation) {
  final p = Path();
  for (var i = 0; i < 10; i++) {
    final rr = i.isEven ? r : r * 0.45;
    final ang = -math.pi / 2 + i * math.pi / 5 + rotation;
    final pt = Offset(c.dx + math.cos(ang) * rr, c.dy + math.sin(ang) * rr);
    if (i == 0) {
      p.moveTo(pt.dx, pt.dy);
    } else {
      p.lineTo(pt.dx, pt.dy);
    }
  }
  return p..close();
}

class _FacePainter extends CustomPainter {
  _FacePainter(this.s, Listenable repaint) : super(repaint: repaint);
  final _FaceState s;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final breathe = 1 + 0.012 * math.sin(s.t * 1.7);
    final happyBounce = s.arc > 0.5 || s.star > 0.5 ? -(math.sin(s.t * 9)).abs() * h * 0.015 : 0.0;

    canvas.save();
    canvas.translate(w / 2, h / 2 + s.hop * h * 0.05 + happyBounce + math.sin(s.t * 2) * h * 0.01);
    canvas.rotate(s.tilt);
    canvas.scale(breathe * (1 + 0.08 * s.squish), breathe * (1 - 0.1 * s.squish));

    // Listening: sound rings behind the head.
    if (s.mood == Mood.listening) {
      for (var i = 0; i < 3; i++) {
        final p = ((s.t * 0.9) + i / 3) % 1.0;
        canvas.drawCircle(
            Offset(0, h * 0.06),
            w * (0.42 + p * 0.16 + s.level * 0.05),
            Paint()
              ..style = PaintingStyle.stroke
              ..strokeWidth = w * 0.012
              ..color = _a(botBlue, (1 - p) * (0.25 + s.level * 0.5)));
      }
    }

    final headRect = Rect.fromCenter(center: Offset(0, h * 0.08), width: w * 0.82, height: h * 0.68);
    final headR = RRect.fromRectAndRadius(headRect, Radius.circular(w * 0.3));

    _antennaAndEars(canvas, headRect, w, h);

    // Head: glow, body, gloss, rim.
    canvas.drawRRect(
        headR.inflate(w * 0.015),
        Paint()
          ..color = _a(botBlue, 0.22 + 0.35 * s.glow + 0.3 * s.level)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, w * 0.06));
    canvas.drawRRect(
        headR,
        Paint()
          ..shader = const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF2C4386), Color(0xFF16224D), Color(0xFF101839)],
          ).createShader(headRect));
    canvas.save();
    canvas.clipRRect(headR);
    canvas.drawOval(
        Rect.fromLTWH(headRect.left + w * 0.08, headRect.top + h * 0.02, w * 0.42, h * 0.12),
        Paint()..color = Colors.white.withAlpha(22));
    canvas.restore();
    canvas.drawRRect(
        headR,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = w * 0.013
          ..color = _a(botBlue, 0.55 + 0.35 * s.glow));

    // Screen (the face area).
    final screen = headRect.deflate(w * 0.07);
    final screenR = RRect.fromRectAndRadius(screen, Radius.circular(w * 0.22));
    canvas.drawRRect(
        screenR,
        Paint()
          ..shader = const RadialGradient(colors: [Color(0xFF0B1430), _screenColor])
              .createShader(screen));
    canvas.save();
    canvas.clipRRect(screenR);

    final sw = screen.width, sh = screen.height, c = screen.center;
    final look = Offset(s.look.dx.clamp(-1.0, 1.0) * sw * 0.12, s.look.dy.clamp(-1.0, 1.0) * sh * 0.13);
    final eyeW = sw * 0.18 * s.scale, eyeH = sh * 0.44 * s.scale;
    for (final side in [-1.0, 1.0]) {
      final open = (side < 0 ? s.openL : s.openR) * (1 - s.blink);
      _eye(canvas, Offset(c.dx + side * sw * 0.21, c.dy - sh * 0.07) + look, eyeW, eyeH, open, side);
    }

    _cheeks(canvas, c, sw, sh, look);
    _mouth(canvas, Offset(c.dx, c.dy + sh * 0.26) + look * 0.3, sw, sh);

    if (s.mood == Mood.thinking) {
      for (var i = 0; i < 3; i++) {
        final on = ((s.t * 3).floor() % 3) == i;
        canvas.drawCircle(Offset(c.dx + sw * (0.25 + i * 0.07), screen.top + sh * 0.13), sw * 0.02,
            Paint()..color = _a(botLight, on ? 1.0 : 0.3));
      }
    }
    final scan = Paint()..color = _a(botBlue, 0.035);
    for (var y = screen.top; y < screen.bottom; y += sh * 0.06) {
      canvas.drawRect(Rect.fromLTWH(screen.left, y, sw, sh * 0.014), scan);
    }
    canvas.restore(); // screen clip

    _particles(canvas, w);
    canvas.restore();
  }

  void _antennaAndEars(Canvas canvas, Rect headRect, double w, double h) {
    // Bouncy antenna with a glowing tip (a heart when BOT is happy / in love).
    canvas.save();
    canvas.translate(0, headRect.top + h * 0.01);
    canvas.rotate(s.antenna);
    final tip = Offset(0, -h * 0.12);
    canvas.drawLine(
        Offset.zero,
        tip,
        Paint()
          ..color = const Color(0xFF2E4278)
          ..strokeWidth = w * 0.025
          ..strokeCap = StrokeCap.round);
    final pulse = 0.5 + 0.5 * math.sin(s.t * 4);
    final tipGlow = (s.glow * 0.6 + s.level * 0.8 + pulse * 0.2).clamp(0.0, 1.0);
    final lovey = math.max(s.heart, math.max(s.arc, s.star));
    final tipColor = Color.lerp(botBlue, botPink, lovey)!;
    canvas.drawCircle(tip, w * 0.065,
        Paint()
          ..color = _a(tipColor, 0.45 * tipGlow)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, w * 0.04));
    if (lovey > 0.5) {
      canvas.drawPath(_heartPath(tip, w * 0.045 * (1 + 0.1 * pulse)), Paint()..color = tipColor);
    } else {
      canvas.drawCircle(tip, w * 0.03, Paint()..color = Color.lerp(const Color(0xFF2E4278), tipColor, tipGlow)!);
      canvas.drawCircle(tip + Offset(-w * 0.009, -w * 0.009), w * 0.009, Paint()..color = Colors.white70);
    }
    canvas.restore();

    // Round ears with a glowing ring.
    for (final side in [-1.0, 1.0]) {
      final ec = Offset(side * (headRect.width / 2 + w * 0.01), headRect.center.dy);
      canvas.drawCircle(ec, w * 0.07, Paint()..color = const Color(0xFF1E2E5E));
      canvas.drawCircle(
          ec,
          w * 0.045,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = w * 0.012
            ..color = _a(botBlue, 0.5 + 0.4 * s.glow));
    }
  }

  void _eye(Canvas canvas, Offset ec, double ew, double eh, double open, double side) {
    final glow = Paint()
      ..color = _a(botBlue, 0.55 + 0.3 * s.glow)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, ew * 0.35);

    if (s.spiral > 0.5) {
      // Dizzy spiral eyes.
      final path = Path();
      for (var i = 0; i <= 60; i++) {
        final th = i / 60 * math.pi * 4;
        final r = ew * 0.55 * i / 60;
        final pt = Offset(ec.dx + math.cos(th + s.t * 5 * side) * r, ec.dy + math.sin(th + s.t * 5 * side) * r);
        if (i == 0) {
          path.moveTo(pt.dx, pt.dy);
        } else {
          path.lineTo(pt.dx, pt.dy);
        }
      }
      canvas.drawPath(
          path,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = ew * 0.14
            ..strokeCap = StrokeCap.round
            ..color = botLight);
      return;
    }
    if (s.star > 0.5) {
      final r = ew * 0.75 * (1 + 0.08 * s.sparkle);
      canvas.drawPath(_starPath(ec, r * 1.1, 0), glow);
      canvas.drawPath(_starPath(ec, r, 0), Paint()..color = const Color(0xFFFFE27A));
      canvas.drawCircle(ec + Offset(-r * 0.2, -r * 0.25), r * 0.14, Paint()..color = Colors.white);
      return;
    }
    if (s.heart > 0.5) {
      final r = ew * 0.85 * (1 + 0.1 * math.sin(s.t * 6));
      canvas.drawPath(
          _heartPath(ec, r * 1.1),
          Paint()
            ..color = _a(botPink, 0.7)
            ..maskFilter = MaskFilter.blur(BlurStyle.normal, ew * 0.3));
      canvas.drawPath(_heartPath(ec, r), Paint()..color = botPink);
      canvas.drawCircle(ec + Offset(-r * 0.3, -r * 0.3), r * 0.13, Paint()..color = Colors.white);
      return;
    }
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

    final eyeHeight = math.max(eh * open, ew * 0.24);
    final r = RRect.fromRectAndRadius(Rect.fromCenter(center: ec, width: ew, height: eyeHeight), Radius.circular(ew / 2));
    canvas.drawRRect(r.inflate(ew * 0.12), glow);
    canvas.drawRRect(
        r,
        Paint()
          ..shader = const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFFDDF6FF), botBlue, Color(0xFF3A8DF5)],
          ).createShader(r.outerRect));
    if (open > 0.4) {
      // Two sparkly highlights that twinkle.
      final twinkle = 0.85 + 0.15 * s.sparkle;
      canvas.drawCircle(Offset(ec.dx - ew * 0.16, ec.dy - eyeHeight * 0.22), ew * 0.19 * twinkle,
          Paint()..color = Colors.white.withAlpha(235));
      canvas.drawCircle(Offset(ec.dx + ew * 0.15, ec.dy + eyeHeight * 0.18), ew * 0.08,
          Paint()..color = Colors.white.withAlpha(200));
      if (s.sparkle > 0.92) {
        canvas.drawPath(_sparklePath(Offset(ec.dx + ew * 0.2, ec.dy - eyeHeight * 0.35), ew * 0.16),
            Paint()..color = Colors.white);
      }
    }
    if (s.sad > 0.05) {
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

  void _cheeks(Canvas canvas, Offset c, double sw, double sh, Offset look) {
    final amount = 0.28 + 0.6 * s.blush; // always a little blushy
    for (final side in [-1.0, 1.0]) {
      final cc = Offset(c.dx + side * sw * 0.33, c.dy + sh * 0.17) + look * 0.5;
      canvas.drawOval(
          Rect.fromCenter(center: cc, width: sw * 0.17, height: sh * 0.09),
          Paint()
            ..color = _a(botPink, 0.5 * amount)
            ..maskFilter = MaskFilter.blur(BlurStyle.normal, sw * 0.025));
      if (s.shy > 0.3 || s.blush > 0.85) {
        // "///" shy lines
        final line = Paint()
          ..color = _a(const Color(0xFFFFB3D4), 0.8 * math.max(s.shy, (s.blush - 0.85) * 6))
          ..strokeWidth = sw * 0.012
          ..strokeCap = StrokeCap.round;
        for (var i = -1; i <= 1; i++) {
          final x = cc.dx + i * sw * 0.035;
          canvas.drawLine(Offset(x + sw * 0.012, cc.dy - sh * 0.03), Offset(x - sw * 0.012, cc.dy + sh * 0.03), line);
        }
      }
    }
  }

  void _mouth(Canvas canvas, Offset mc, double sw, double sh) {
    final mw = sw * 0.2;
    final open = (s.mouthOpen + s.level * 0.7 + s.yawn * 0.8).clamp(0.0, 1.0);
    final glow = Paint()
      ..color = _a(botBlue, 0.5)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, sw * 0.02);
    final strokeGlow = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = sw * 0.05
      ..color = _a(botBlue, 0.45)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, sw * 0.02);
    final stroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..strokeWidth = sw * 0.028
      ..color = botLight;

    if (open > 0.15 && s.smile > 0.5) {
      // Big open smile with a little tongue.
      final depth = sh * (0.06 + open * 0.14);
      final path = Path()
        ..moveTo(mc.dx - mw / 2, mc.dy - depth * 0.3)
        ..lineTo(mc.dx + mw / 2, mc.dy - depth * 0.3)
        ..quadraticBezierTo(mc.dx + mw / 2, mc.dy + depth, mc.dx, mc.dy + depth)
        ..quadraticBezierTo(mc.dx - mw / 2, mc.dy + depth, mc.dx - mw / 2, mc.dy - depth * 0.3)
        ..close();
      canvas.drawPath(path, glow);
      canvas.drawPath(path, Paint()..color = const Color(0xFF0E2A5C));
      canvas.save();
      canvas.clipPath(path);
      canvas.drawOval(Rect.fromCenter(center: Offset(mc.dx, mc.dy + depth * 0.85), width: mw * 0.6, height: depth * 0.8),
          Paint()..color = botPink);
      canvas.restore();
      canvas.drawPath(path, stroke);
    } else if (open > 0.15) {
      // Round "o" mouth (talking / surprised / yawning).
      final rect = Rect.fromCenter(center: mc, width: mw * (0.42 + 0.25 * open), height: sh * (0.04 + open * 0.17));
      final rr = RRect.fromRectAndRadius(rect, Radius.circular(rect.shortestSide / 2));
      canvas.drawRRect(rr.inflate(sw * 0.01), glow);
      canvas.drawRRect(rr, Paint()..color = botLight);
      canvas.drawRRect(rr.deflate(sw * 0.014), Paint()..color = const Color(0xFF0A2350));
    } else if (s.cat > 0.5 && s.smile > 0.2) {
      // Cute cat mouth "ω".
      final q = mw * 0.24;
      final path = Path()
        ..moveTo(mc.dx - q * 2, mc.dy - q * 0.3)
        ..quadraticBezierTo(mc.dx - q, mc.dy + q * 1.3, mc.dx, mc.dy - q * 0.1)
        ..quadraticBezierTo(mc.dx + q, mc.dy + q * 1.3, mc.dx + q * 2, mc.dy - q * 0.3);
      canvas.drawPath(path, strokeGlow);
      canvas.drawPath(path, stroke);
    } else if (s.shy > 0.5) {
      // Tiny wavy shy mouth.
      final q = mw * 0.14;
      final path = Path()..moveTo(mc.dx - q * 2, mc.dy);
      for (var i = 0; i < 4; i++) {
        path.quadraticBezierTo(mc.dx - q * 2 + q * (i + 0.5), mc.dy + (i.isEven ? -q * 0.6 : q * 0.6),
            mc.dx - q * 2 + q * (i + 1), mc.dy);
      }
      canvas.drawPath(path, stroke);
    } else {
      // Line mouth that curves into a smile or frown.
      final path = Path()
        ..moveTo(mc.dx - mw / 2, mc.dy)
        ..quadraticBezierTo(mc.dx, mc.dy + s.smile * sh * 0.14, mc.dx + mw / 2, mc.dy);
      canvas.drawPath(path, strokeGlow);
      canvas.drawPath(path, stroke);
    }
  }

  void _particles(Canvas canvas, double w) {
    for (final p in s.particles) {
      final fade = (p.life / p.max).clamp(0.0, 1.0);
      final grow = 1 + (1 - fade) * 0.4;
      final pos = Offset(p.x * w, p.y * w);
      final sz = p.size * w * grow;
      switch (p.kind) {
        case 'heart':
          canvas.save();
          canvas.translate(pos.dx, pos.dy);
          canvas.rotate(p.spin * 0.15 * (1 - fade));
          canvas.drawPath(_heartPath(Offset.zero, sz), Paint()..color = _a(botPink, fade));
          canvas.restore();
        case 'sparkle':
          canvas.drawPath(_sparklePath(pos, sz), Paint()..color = _a(botLight, fade));
        default:
          final text = {'q': '?', 'ex': '!', 'z': 'z', 'note': '♪'}[p.kind] ?? '';
          final tp = TextPainter(
            text: TextSpan(
                text: text,
                style: TextStyle(color: _a(botLight, fade), fontSize: sz * 1.6, fontWeight: FontWeight.w800)),
            textDirection: TextDirection.ltr,
          )..layout();
          tp.paint(canvas, pos - Offset(tp.width / 2, tp.height / 2));
      }
    }
  }

  @override
  bool shouldRepaint(covariant _FacePainter old) => old.s != s;
}
