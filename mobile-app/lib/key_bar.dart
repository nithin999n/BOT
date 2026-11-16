import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';

/// Keyboard for the PC: type text (any language) and tap special keys.
class KeyBar extends StatefulWidget {
  const KeyBar({super.key, required this.conn});
  final BotConnection conn;

  @override
  State<KeyBar> createState() => _KeyBarState();
}

class _KeyBarState extends State<KeyBar> {
  final _ctrl = TextEditingController();

  static const _keys = <(String, String)>[
    ('enter', 'Enter'),
    ('backspace', '⌫'),
    ('space', 'Space'),
    ('esc', 'Esc'),
    ('tab', 'Tab'),
    ('left', '←'),
    ('right', '→'),
    ('up', '↑'),
    ('down', '↓'),
    ('win', 'Win'),
    ('delete', 'Del'),
    ('f5', 'F5'),
  ];

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  void _sendText() {
    final t = _ctrl.text;
    if (t.isEmpty) return;
    widget.conn.send({'type': 'type_text', 'text': t});
    _ctrl.clear();
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainer,
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              height: 48,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                children: [
                  for (final (key, label) in _keys)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 4),
                      child: ActionChip(
                        label: Text(label),
                        onPressed: () {
                          HapticFeedback.selectionClick();
                          widget.conn.send({'type': 'key', 'key': key});
                        },
                      ),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _ctrl,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _sendText(),
                      decoration: const InputDecoration(
                        hintText: 'Type on the PC…',
                        isDense: true,
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(onPressed: _sendText, icon: const Icon(Icons.keyboard_return)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
