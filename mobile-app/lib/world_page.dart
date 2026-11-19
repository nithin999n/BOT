import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';
import 'face.dart';
import 'notify_bridge.dart';
import 'style.dart';

const _feelings = {'great': '😊', 'okay': '😐', 'sad': '😢', 'tired': '😴', 'angry': '😡'};
const _games = [
  ('fetch', '⚽', 'Fetch'),
  ('hide', '🙈', 'Hide & seek'),
  ('catch', '🍪', 'Cookie catch'),
  ('bubbles', '🫧', 'Bubbles'),
  ('rps', '✊', 'Rock paper scissors'),
  ('ttt', '❌', 'Tic-tac-toe'),
  ('photo', '📸', 'Photo with BOT'),
  ('chase', '🏃', 'Chase'),
];
const _months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
  'November', 'December'];

/// Everything about the desktop BOT's life: love, games, mood, diary, happy moments, reminders, badges.
class WorldPage extends StatefulWidget {
  const WorldPage({super.key, required this.conn});
  final BotConnection conn;

  @override
  State<WorldPage> createState() => _WorldPageState();
}

class _WorldPageState extends State<WorldPage> {
  BotConnection get conn => widget.conn;
  final _moment = TextEditingController();

  @override
  void initState() {
    super.initState();
    conn.requestWorld();
    conn.addListener(_changed);
  }

  @override
  void dispose() {
    conn.removeListener(_changed);
    _moment.dispose();
    super.dispose();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  bool _online() {
    if (conn.online) return true;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Not connected to the PC')));
    return false;
  }

  void _fun(String action, [Object? value]) {
    HapticFeedback.selectionClick();
    if (_online()) conn.petFun(action, value);
  }

  void _game(String id) {
    HapticFeedback.selectionClick();
    if (!_online()) return;
    if (id == 'chase') {
      conn.petAction('chase');
    } else {
      conn.petFun('game', id);
    }
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        duration: Duration(seconds: 2), content: Text('Look at your PC screen! 🎮')));
  }

  Future<void> _addReminder() async {
    final text = TextEditingController();
    var day = DateTime.now();
    TimeOfDay? time;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => AlertDialog(
          title: const Text('New reminder ⏰'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(
                controller: text,
                autofocus: true,
                decoration: const InputDecoration(hintText: 'e.g. Call mom')),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.calendar_today, size: 18),
                  label: Text('${day.day} ${_months[day.month - 1].substring(0, 3)}'),
                  onPressed: () async {
                    final d = await showDatePicker(
                        context: ctx,
                        initialDate: day,
                        firstDate: DateTime.now().subtract(const Duration(days: 1)),
                        lastDate: DateTime.now().add(const Duration(days: 365)));
                    if (d != null) setS(() => day = d);
                  },
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.schedule, size: 18),
                  label: Text(time == null ? 'Time' : time!.format(ctx)),
                  onPressed: () async {
                    final t = await showTimePicker(context: ctx, initialTime: TimeOfDay.now());
                    if (t != null) setS(() => time = t);
                  },
                ),
              ),
            ]),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
          ],
        ),
      ),
    );
    if (ok != true || time == null || text.text.trim().isEmpty || !_online()) return;
    var at = DateTime(day.year, day.month, day.day, time!.hour, time!.minute);
    if (at.isBefore(DateTime.now())) at = at.add(const Duration(days: 1));
    conn.send({'type': 'reminder_add', 'at': at.millisecondsSinceEpoch / 1000, 'text': text.text.trim()});
  }

  Future<void> _pickBirthday(String current) async {
    var init = DateTime(2000, 1, 1);
    if (RegExp(r'^\d{2}-\d{2}$').hasMatch(current)) {
      init = DateTime(2000, int.parse(current.substring(0, 2)), int.parse(current.substring(3)));
    }
    final d = await showDatePicker(
        context: context,
        initialDate: init,
        firstDate: DateTime(1950),
        lastDate: DateTime.now(),
        helpText: 'Your birthday 🎂');
    if (d == null || !_online()) return;
    conn.send({
      'type': 'set_birthday',
      'value': '${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}'
    });
  }

  String _prettyBirthday(String mmdd) {
    if (!RegExp(r'^\d{2}-\d{2}$').hasMatch(mmdd)) return 'Not set';
    return '${int.parse(mmdd.substring(3))} ${_months[int.parse(mmdd.substring(0, 2)) - 1]}';
  }

  String _when(num at) {
    final d = DateTime.fromMillisecondsSinceEpoch((at * 1000).round());
    final now = DateTime.now();
    final t = TimeOfDay.fromDateTime(d).format(context);
    if (d.year == now.year && d.month == now.month && d.day == now.day) return 'Today $t';
    final tm = now.add(const Duration(days: 1));
    if (d.year == tm.year && d.month == tm.month && d.day == tm.day) return 'Tomorrow $t';
    return '${d.day} ${_months[d.month - 1].substring(0, 3)} $t';
  }

  Widget _section(String title, List<Widget> children, {IconData? icon}) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            if (icon != null) ...[Icon(icon, size: 20), const SizedBox(width: 8)],
            Text(title, style: Theme.of(context).textTheme.titleMedium),
          ]),
          const SizedBox(height: 10),
          ...children,
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text("BOT's world 🌍"), actions: [
        IconButton(icon: const Icon(Icons.refresh), onPressed: conn.requestWorld),
      ]),
      body: ValueListenableBuilder<Map<String, dynamic>?>(
        valueListenable: conn.world,
        builder: (context, w, _) {
          if (!conn.online) return const Center(child: Text('Connect to the PC to see BOT\'s world'));
          if (w == null) return const Center(child: CircularProgressIndicator());
          final love = (w['love'] as num?)?.toInt() ?? 0;
          final hugs = (w['hugs'] as num?)?.toInt() ?? 0;
          final week = ((w['week'] as List?) ?? const []).cast<Map>();
          final diary = ((w['diary'] as List?) ?? const []).cast<Map>();
          final moments = ((w['moments'] as List?) ?? const []).cast<Map>();
          final reminders = ((w['reminders'] as List?) ?? const []).cast<Map>();
          final badges = ((w['badges'] as List?) ?? const []).cast<Map>();
          final opts = Map<String, dynamic>.from((w['options'] as Map?) ?? const {});
          final playing = (w['playing'] as Map?) ?? const {};
          final weather = (w['weather'] as Map?) ?? const {};
          final got = badges.where((b) => b['got'] == true).length;
          final bridge = NotifyBridge.instance;
          return ListView(
            padding: const EdgeInsets.all(14),
            children: [
              Center(child: RobotFace(mood: Mood.love, size: 120, color: style.value.color)),
              const SizedBox(height: 6),
              Center(
                child: Text('💖 You told BOT you love it $love time${love == 1 ? '' : 's'}',
                    style: Theme.of(context).textTheme.titleMedium),
              ),
              Center(child: Text('🤗 $hugs hug${hugs == 1 ? '' : 's'}', style: TextStyle(color: cs.onSurfaceVariant))),
              if (weather.isNotEmpty)
                Center(
                  child: Text('${weather['city'] ?? ''} ${weather['temp'] ?? ''}°C',
                      style: TextStyle(color: cs.onSurfaceVariant)),
                ),
              const SizedBox(height: 10),
              Wrap(alignment: WrapAlignment.center, spacing: 8, runSpacing: 8, children: [
                FilledButton.tonal(onPressed: () => _fun('love'), child: const Text('Ask me "do you love me?" 💖')),
                FilledButton.tonal(onPressed: () => _fun('hug'), child: const Text('Send a hug 🤗')),
                FilledButton.tonal(
                  onPressed: () => _fun('travel', conn.botOnPhone ? 'pc' : 'phone'),
                  child: Text(conn.botOnPhone ? 'Send BOT back to the PC 💻' : 'Call BOT to my phone 📱'),
                ),
              ]),
              const SizedBox(height: 14),
              _section('Games', icon: Icons.sports_esports, [
                GridView.count(
                  crossAxisCount: 4,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 8,
                  crossAxisSpacing: 8,
                  childAspectRatio: 0.9,
                  children: [
                    for (final g in _games)
                      InkWell(
                        borderRadius: BorderRadius.circular(14),
                        onTap: () => _game(g.$1),
                        child: Ink(
                          decoration: BoxDecoration(
                              color: cs.surfaceContainerHighest, borderRadius: BorderRadius.circular(14)),
                          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                            Text(g.$2, style: const TextStyle(fontSize: 26)),
                            const SizedBox(height: 4),
                            Text(g.$3, textAlign: TextAlign.center, style: const TextStyle(fontSize: 11)),
                          ]),
                        ),
                      ),
                  ],
                ),
                if ((w['catch_best'] as num? ?? 0) > 0)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text('🏆 Cookie catch best: ${w['catch_best']}', textAlign: TextAlign.center),
                  ),
              ]),
              if (playing['title'] != null && '${playing['title']}'.isNotEmpty && playing['playing'] == true)
                _section('Playing on the PC', icon: Icons.music_note, [
                  Text('${playing['title']}${'${playing['artist'] ?? ''}'.isEmpty ? '' : ' — ${playing['artist']}'}'),
                  Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    for (final a in const [('prev', Icons.skip_previous), ('toggle', Icons.pause), ('next', Icons.skip_next)])
                      IconButton(
                          icon: Icon(a.$2), onPressed: () => conn.send({'type': 'media', 'action': a.$1})),
                  ]),
                ]),
              _section('How are you feeling today?', icon: Icons.favorite_border, [
                Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
                  for (final f in _feelings.entries)
                    IconButton(
                      iconSize: 30,
                      onPressed: () => _fun('feel', f.key),
                      icon: Text(f.value, style: const TextStyle(fontSize: 28)),
                    ),
                ]),
                const SizedBox(height: 6),
                Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
                  for (final d in week)
                    Column(children: [
                      Text(_feelings['${d['mood']}'] ?? '·', style: const TextStyle(fontSize: 20)),
                      Text(const ['M', 'T', 'W', 'T', 'F', 'S', 'S'][DateTime.parse('${d['day']}').weekday - 1],
                          style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant)),
                    ]),
                ]),
              ]),
              _section("BOT's diary", icon: Icons.menu_book, [
                for (final d in diary.take(7))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('${d['day']}', style: TextStyle(fontSize: 12, color: cs.primary)),
                      Text('${d['text']}'),
                    ]),
                  ),
              ]),
              _section('Happy moments jar 🫙', icon: Icons.auto_awesome, [
                Text('Save little good moments. Once in a while BOT shows you one on the PC 😊',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                const SizedBox(height: 6),
                Row(children: [
                  Expanded(
                    child: TextField(
                      controller: _moment,
                      maxLength: 300,
                      decoration: const InputDecoration(hintText: 'A happy moment…', counterText: ''),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.add_circle),
                    onPressed: () {
                      final t = _moment.text.trim();
                      if (t.isEmpty || !_online()) return;
                      conn.send({'type': 'moment_add', 'text': t});
                      _moment.clear();
                    },
                  ),
                ]),
                for (final m in moments.take(30))
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: Text('${m['text']}'),
                    subtitle: Text('${m['date']}'),
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline, size: 20),
                      onPressed: () => conn.send({'type': 'moment_del', 'id': m['id']}),
                    ),
                  ),
              ]),
              _section('Reminders ⏰', icon: Icons.alarm, [
                Text('Or just say: "remind me at 5 to call mom"',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                for (final r in reminders)
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.alarm),
                    title: Text('${r['text']}'),
                    subtitle: Text(_when(r['at'] as num)),
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline, size: 20),
                      onPressed: () => conn.send({'type': 'reminder_del', 'id': r['id']}),
                    ),
                  ),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                      onPressed: _addReminder, icon: const Icon(Icons.add), label: const Text('Add reminder')),
                ),
              ]),
              _section('Badges 🏅  $got/${badges.length}', icon: Icons.emoji_events, [
                for (final b in badges)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Opacity(
                      opacity: b['got'] == true ? 1 : 0.55,
                      child: Row(children: [
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text('${b['got'] == true ? '' : '🔒 '}${b['name']}',
                                style: const TextStyle(fontWeight: FontWeight.w600)),
                            Text('${b['how']}', style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                            if (b['got'] != true)
                              Padding(
                                padding: const EdgeInsets.only(top: 4),
                                child: LinearProgressIndicator(
                                  value: ((b['progress'] as num? ?? 0) / (b['need'] as num? ?? 1)).clamp(0.0, 1.0),
                                  minHeight: 5,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                              ),
                          ]),
                        ),
                        if (b['got'] != true)
                          Padding(
                            padding: const EdgeInsets.only(left: 8),
                            child: Text('${b['progress']}/${b['need']}', style: const TextStyle(fontSize: 12)),
                          ),
                      ]),
                    ),
                  ),
              ]),
              _section('About you', icon: Icons.cake, [
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Text('🎂', style: TextStyle(fontSize: 24)),
                  title: const Text('Your birthday'),
                  subtitle: Text(_prettyBirthday('${w['birthday'] ?? ''}')),
                  trailing: const Icon(Icons.edit),
                  onTap: () => _pickBirthday('${w['birthday'] ?? ''}'),
                ),
              ]),
              _section('Desktop', icon: Icons.desktop_windows, [
                Wrap(spacing: 8, runSpacing: 8, children: [
                  OutlinedButton(onPressed: () => _fun('tidy'), child: const Text('Tidy my desktop 🧹')),
                  OutlinedButton(onPressed: () => _fun('untidy'), child: const Text('Undo tidy ↩️')),
                ]),
                const SizedBox(height: 6),
                Text('Tidy moves loose files into Desktop › BOT Tidy folders. Nothing is ever deleted.\n'
                    'Snip to phone: press Ctrl+Alt+P on the PC ✂️ (or use the tray menu).',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
              ]),
              _section('Settings', icon: Icons.tune, [
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Clap twice to call BOT 👏'),
                  subtitle: const Text('Uses the PC microphone (only loudness, nothing is recorded)'),
                  value: opts['clap'] != false,
                  onChanged: (v) => conn.send({'type': 'set_option', 'key': 'clap', 'value': v}),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Cursor prank 😆'),
                  subtitle: const Text('Now and then BOT runs off with your mouse for a second'),
                  value: opts['cursor_prank'] == true,
                  onChanged: (v) => conn.send({'type': 'set_option', 'key': 'cursor_prank', 'value': v}),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Photo when someone unlocks 📸'),
                  subtitle: const Text('Webcam photo if the PC is unlocked while you are away'),
                  value: opts['intruder_photo'] != false,
                  onChanged: (v) => conn.send({'type': 'set_option', 'key': 'intruder_photo', 'value': v}),
                ),
                if (bridge != null)
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Show my calls & messages on the PC 📞'),
                    subtitle: const Text('BOT holds up a sign: "📞 Mom is calling!" (needs Notification access)'),
                    value: bridge.enabled,
                    onChanged: (v) async {
                      final ok = await bridge.setEnabled(v);
                      if (!ok && context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                            content: Text('Allow "Notification access" for BOT, then switch this on again')));
                      }
                      if (mounted) setState(() {});
                    },
                  ),
              ]),
            ],
          );
        },
      ),
    );
  }
}
