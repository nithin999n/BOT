import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';

/// Routines: one phrase runs several commands ("good night" -> close everything, lock).
class RoutinesPage extends StatefulWidget {
  const RoutinesPage({super.key, required this.conn, required this.lang});
  final BotConnection conn;
  final String lang;

  @override
  State<RoutinesPage> createState() => _RoutinesPageState();
}

class _RoutinesPageState extends State<RoutinesPage> {
  BotConnection get conn => widget.conn;

  @override
  void initState() {
    super.initState();
    conn.addListener(_refresh);
  }

  @override
  void dispose() {
    conn.removeListener(_refresh);
    super.dispose();
  }

  void _refresh() {
    if (mounted) setState(() {});
  }

  List<Map<String, dynamic>> get _items => [for (final r in conn.routines) Map<String, dynamic>.from(r)];

  void _run(Map<String, dynamic> r) {
    HapticFeedback.mediumImpact();
    conn.send({'type': 'routine_run', 'name': r['name'], 'lang': widget.lang});
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Running “${r['name']}”…')));
  }

  Future<void> _edit({int? index}) async {
    final current = index == null ? null : _items[index];
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _RoutineDialog(initial: current),
    );
    if (result == null) return;
    final items = _items;
    if (result['delete'] == true) {
      if (index != null) items.removeAt(index);
    } else if (index == null) {
      items.add(result);
    } else {
      items[index] = result;
    }
    conn.saveRoutines(items);
  }

  @override
  Widget build(BuildContext context) {
    final items = conn.routines;
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Routines')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: conn.online ? () => _edit() : null,
        icon: const Icon(Icons.add),
        label: const Text('New routine'),
      ),
      body: !conn.online && items.isEmpty
          ? const Center(child: Text('Connect to the PC to see your routines'))
          : ListView(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 96),
              children: [
                Padding(
                  padding: const EdgeInsets.all(8),
                  child: Text('Say a routine\'s name (or tap ▶) and BOT runs all its steps.',
                      style: TextStyle(color: cs.onSurfaceVariant)),
                ),
                for (var i = 0; i < items.length; i++)
                  Card(
                    child: ListTile(
                      title: Text(items[i]['name'].toString()),
                      subtitle: Text((items[i]['steps'] as List).join('  →  ')),
                      onTap: conn.online ? () => _edit(index: i) : null,
                      trailing: IconButton.filledTonal(
                        tooltip: 'Run',
                        icon: const Icon(Icons.play_arrow),
                        onPressed: conn.online ? () => _run(items[i]) : null,
                      ),
                    ),
                  ),
              ],
            ),
    );
  }
}

class _RoutineDialog extends StatefulWidget {
  const _RoutineDialog({this.initial});
  final Map<String, dynamic>? initial;

  @override
  State<_RoutineDialog> createState() => _RoutineDialogState();
}

class _RoutineDialogState extends State<_RoutineDialog> {
  late final TextEditingController _name = TextEditingController(text: widget.initial?['name']?.toString() ?? '');
  late final TextEditingController _aliases =
      TextEditingController(text: ((widget.initial?['aliases'] as List?) ?? const []).join(', '));
  late final TextEditingController _steps =
      TextEditingController(text: ((widget.initial?['steps'] as List?) ?? const []).join('\n'));
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _aliases.dispose();
    _steps.dispose();
    super.dispose();
  }

  void _save() {
    final name = _name.text.trim();
    final steps = _steps.text.split('\n').map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
    if (name.isEmpty || steps.isEmpty) {
      setState(() => _error = 'Give it a name and at least one step.');
      return;
    }
    final aliases = _aliases.text.split(',').map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
    Navigator.pop(context, {'name': name, 'aliases': aliases, 'steps': steps});
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.initial == null ? 'New routine' : 'Edit routine'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _name,
              decoration: const InputDecoration(labelText: 'Name (what you say)', hintText: 'movie time'),
            ),
            TextField(
              controller: _aliases,
              decoration: const InputDecoration(
                  labelText: 'Other names (optional, comma separated)', hintText: 'फिल्म टाइम, ಸಿನಿಮಾ ಸಮಯ'),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _steps,
              minLines: 4,
              maxLines: 10,
              decoration: const InputDecoration(
                labelText: 'Steps: one command per line',
                hintText: 'close everything\nopen netflix\nvolume up',
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
          ],
        ),
      ),
      actions: [
        if (widget.initial != null)
          TextButton(
            onPressed: () => Navigator.pop(context, {'delete': true}),
            child: Text('Delete', style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ),
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _save, child: const Text('Save')),
      ],
    );
  }
}
