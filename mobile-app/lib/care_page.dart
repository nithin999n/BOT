import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';
import 'face.dart';
import 'style.dart';
import 'world_page.dart';

const _outfits = <String, String>{
  'auto': '✨ Auto',
  'none': '🚫 None',
  'bow': '🎀 Bow',
  'sunglasses': '😎 Sunglasses',
  'party': '🥳 Party hat',
  'crown': '👑 Crown',
  'santa': '🎅 Santa hat',
  'headband': '🎧 Headband',
  'cap': '🧢 Cap',
  'flower': '🌸 Flower crown',
  'grad': '🎓 Grad cap',
  'halo': '😇 Halo',
};

/// Take care of the desktop BOT: food, happiness, level, games, focus timer, outfits.
class CarePage extends StatelessWidget {
  const CarePage({super.key, required this.conn});
  final BotConnection conn;

  void _do(BuildContext context, String action, [Object? value]) {
    HapticFeedback.selectionClick();
    if (!conn.online) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Not connected to the PC')));
      return;
    }
    conn.petAction(action, value);
  }

  Mood _mood(Map<String, dynamic> s) {
    final hunger = (s['hunger'] as num?) ?? 100, happy = (s['happy'] as num?) ?? 100;
    if (hunger < 25) return Mood.worried;
    if (happy < 30) return Mood.sad;
    if (happy > 80) return Mood.love;
    return Mood.happy;
  }

  String _caption(Map<String, dynamic> s) {
    final hunger = (s['hunger'] as num?) ?? 100, happy = (s['happy'] as num?) ?? 100;
    if (hunger < 25) return 'I\'m so hungry… a cookie please? 🥺';
    if (happy < 30) return 'I feel lonely… play with me? 🥺';
    if (happy > 80 && hunger > 60) return 'I\'m the happiest BOT ever! 💕';
    return 'Thanks for taking care of me 😊';
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Take care of BOT')),
      body: ValueListenableBuilder<Map<String, dynamic>?>(
        valueListenable: conn.petStats,
        builder: (context, s, _) {
          if (s == null || !conn.online) {
            return const Center(child: Text('Connect to the PC to see the desktop BOT'));
          }
          final level = (s['level'] as num?)?.toInt() ?? 1;
          final xp = (s['xp'] as num?)?.toInt() ?? 0;
          final hunger = ((s['hunger'] as num?) ?? 0).toDouble();
          final happy = ((s['happy'] as num?) ?? 0).toDouble();
          final outfit = (s['outfit'] ?? 'auto').toString();
          final unlocked = ((s['unlocked'] as List?) ?? const []).map((e) => e.toString()).toSet();
          final unlockAt = Map<String, dynamic>.from((s['unlock_at'] as Map?) ?? const {});
          final focusLeft = (s['focus_left'] as num?)?.toInt() ?? 0;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Center(child: RobotFace(mood: _mood(s), size: 140, color: style.value.color)),
              Center(child: Text(_caption(s), style: Theme.of(context).textTheme.titleMedium)),
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Text('⭐ Level $level', style: Theme.of(context).textTheme.titleLarge),
                      const Spacer(),
                      Text('${xp % 100}/100 XP', style: TextStyle(color: cs.onSurfaceVariant)),
                    ]),
                    const SizedBox(height: 6),
                    _Bar(value: (xp % 100) / 100, color: Colors.amber),
                    const SizedBox(height: 14),
                    Text('🍪 Food ${hunger.round()}%'),
                    const SizedBox(height: 4),
                    _Bar(value: hunger / 100, color: hunger < 25 ? Colors.redAccent : Colors.orangeAccent),
                    const SizedBox(height: 12),
                    Text('💖 Happiness ${happy.round()}%'),
                    const SizedBox(height: 4),
                    _Bar(value: happy / 100, color: happy < 30 ? Colors.redAccent : Colors.pinkAccent),
                  ]),
                ),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                alignment: WrapAlignment.center,
                children: [
                  FilledButton.tonalIcon(
                      onPressed: () => _do(context, 'feed'),
                      icon: const Text('🍪'),
                      label: const Text('Feed a cookie')),
                  FilledButton.tonalIcon(
                      onPressed: () => _do(context, 'chase'),
                      icon: const Text('🏃'),
                      label: const Text('Play chase')),
                  if (focusLeft > 0)
                    FilledButton.tonalIcon(
                        onPressed: () => _do(context, 'focus_stop'),
                        icon: const Text('🍅'),
                        label: Text('Stop focus (${(focusLeft / 60).ceil()} min left)'))
                  else
                    FilledButton.tonalIcon(
                        onPressed: () => _do(context, 'focus', 25),
                        icon: const Text('🍅'),
                        label: const Text('Focus 25 min')),
                  FilledButton.tonalIcon(
                      onPressed: () => _do(context, 'report'),
                      icon: const Text('📊'),
                      label: const Text('Today\'s report')),
                  FilledButton.tonalIcon(
                      onPressed: () => _do(context, 'sorry'),
                      icon: const Text('💕'),
                      label: const Text('Say sorry')),
                ],
              ),
              const SizedBox(height: 20),
              Text('Outfits', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final o in _outfits.entries)
                    ChoiceChip(
                      label: Text(unlocked.contains(o.key) || !unlockAt.containsKey(o.key)
                          ? o.value
                          : unlockAt[o.key] is num
                              ? '🔒 ${o.value} (level ${unlockAt[o.key]})'
                              : '🔒 ${o.value} (badge: ${unlockAt[o.key]})'),
                      selected: outfit == o.key,
                      onSelected: unlocked.contains(o.key) || !unlockAt.containsKey(o.key)
                          ? (_) => _do(context, 'outfit', o.key)
                          : null,
                    ),
                ],
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => WorldPage(conn: conn))),
                icon: const Text('🌍'),
                label: const Text("Games, love, diary, badges… BOT's world"),
              ),
              const SizedBox(height: 16),
              Text(
                'Tip: pet BOT on the PC by clicking it, drop a file on it to send it to this phone, '
                'and don\'t throw it too hard… it gets angry and leaves! 😤',
                textAlign: TextAlign.center,
                style: TextStyle(color: cs.onSurfaceVariant, fontSize: 12),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _Bar extends StatelessWidget {
  const _Bar({required this.value, required this.color});
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value.clamp(0.0, 1.0)),
      duration: const Duration(milliseconds: 600),
      curve: Curves.easeOutCubic,
      builder: (context, v, _) => ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: LinearProgressIndicator(value: v, minHeight: 12, color: color, backgroundColor: Colors.white12),
      ),
    );
  }
}
