import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'connection.dart';
import 'face.dart';
import 'style.dart';

Mood moodForHealth(Map<String, dynamic>? h) {
  switch (h?['feeling']) {
    case 'hot':
      return Mood.sweaty;
    case 'low_battery':
      return Mood.worried;
    case 'charging':
      return Mood.charging;
    default:
      return Mood.idle;
  }
}

String healthCaption(Map<String, dynamic>? h) {
  switch (h?['feeling']) {
    case 'hot':
      return 'Phew, the PC is working hard! 😅';
    case 'low_battery':
      return 'Battery is low… please plug me in 🥺';
    case 'charging':
      return 'Charging… yummy electricity ⚡';
    default:
      return 'All good! 😊';
  }
}

/// Live PC health: CPU, RAM, battery, uptime, and BOT's mood about it.
class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key, required this.conn});
  final BotConnection conn;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('PC health')),
      body: ValueListenableBuilder<Map<String, dynamic>?>(
        valueListenable: conn.health,
        builder: (context, h, _) {
          if (h == null || !conn.online) {
            return const Center(child: Text('Connect to the PC to see its health'));
          }
          final cpu = (h['cpu'] as num?)?.toDouble() ?? 0;
          final ram = (h['ram'] as num?)?.toDouble() ?? 0;
          final battery = (h['battery'] as num?)?.toDouble();
          final charging = h['charging'] == true;
          final up = (h['uptime'] as num?)?.toInt() ?? 0;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Center(child: RobotFace(mood: moodForHealth(h), size: 150, color: style.value.color)),
              Center(child: Text(healthCaption(h), style: Theme.of(context).textTheme.titleMedium)),
              const SizedBox(height: 16),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                children: [
                  _Gauge(label: 'CPU', value: cpu, icon: Icons.memory, hotIsBad: true),
                  _Gauge(label: 'RAM', value: ram, icon: Icons.storage, hotIsBad: true),
                  if (battery != null)
                    _Gauge(
                      label: charging ? 'Battery ⚡' : 'Battery',
                      value: battery,
                      icon: charging ? Icons.battery_charging_full : Icons.battery_std,
                      hotIsBad: false,
                    )
                  else
                    const _InfoCard(label: 'Power', text: 'Plugged in', icon: Icons.power),
                  _InfoCard(
                    label: 'Turned on for',
                    text: up >= 86400 ? '${up ~/ 86400}d ${(up % 86400) ~/ 3600}h' : '${up ~/ 3600}h ${(up % 3600) ~/ 60}m',
                    icon: Icons.timer,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text('Temperature needs admin rights on Windows, so BOT uses CPU load to tell if the PC is working hard.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12)),
            ],
          );
        },
      ),
    );
  }
}

class _Gauge extends StatelessWidget {
  const _Gauge({required this.label, required this.value, required this.icon, required this.hotIsBad});
  final String label;
  final double value; // 0..100
  final IconData icon;
  final bool hotIsBad; // CPU/RAM: high = red. Battery: low = red.

  @override
  Widget build(BuildContext context) {
    final bad = hotIsBad ? value / 100 : 1 - value / 100;
    final color = bad > 0.85 ? Colors.redAccent : (bad > 0.65 ? Colors.orangeAccent : Colors.greenAccent);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: value.clamp(0, 100) / 100),
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOutCubic,
          builder: (context, v, _) => CustomPaint(
            painter: _ArcPainter(v, color),
            child: Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(icon, size: 20, color: color),
                Text('${(v * 100).round()}%', style: Theme.of(context).textTheme.headlineSmall),
                Text(label, style: Theme.of(context).textTheme.labelMedium),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

class _ArcPainter extends CustomPainter {
  _ArcPainter(this.v, this.color);
  final double v;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final r = math.min(size.width, size.height) / 2 - 6;
    final c = size.center(Offset.zero);
    final rect = Rect.fromCircle(center: c, radius: r);
    const start = math.pi * 0.75, sweep = math.pi * 1.5;
    final base = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..strokeCap = StrokeCap.round
      ..color = Colors.white12;
    canvas.drawArc(rect, start, sweep, false, base);
    canvas.drawArc(rect, start, sweep * v, false, base..color = color);
  }

  @override
  bool shouldRepaint(covariant _ArcPainter old) => old.v != v || old.color != color;
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.label, required this.text, required this.icon});
  final String label, text;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 28),
          const SizedBox(height: 6),
          Text(text, style: Theme.of(context).textTheme.titleLarge),
          Text(label, style: Theme.of(context).textTheme.labelMedium),
        ]),
      ),
    );
  }
}
