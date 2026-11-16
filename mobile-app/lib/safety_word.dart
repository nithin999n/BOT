import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';
import 'face.dart';
import 'voice.dart';

/// Asks for the safety word (typed, or spoken by holding the mic). Returns null if cancelled.
Future<String?> askSafetyWord(
  BuildContext context, {
  required Voice voice,
  required String locale,
  required String message,
}) {
  HapticFeedback.heavyImpact();
  return showDialog<String>(
    context: context,
    barrierDismissible: false,
    builder: (_) => _AskDialog(voice: voice, locale: locale, message: message),
  );
}

class _AskDialog extends StatefulWidget {
  const _AskDialog({required this.voice, required this.locale, required this.message});
  final Voice voice;
  final String locale;
  final String message;

  @override
  State<_AskDialog> createState() => _AskDialogState();
}

class _AskDialogState extends State<_AskDialog> {
  final _word = TextEditingController();
  bool _hidden = true;

  @override
  void dispose() {
    _word.dispose();
    super.dispose();
  }

  void _submit() => Navigator.pop(context, _word.text.trim());

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      icon: const Icon(Icons.shield, color: botBlue),
      title: const Text('Safety word'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(widget.message),
            const SizedBox(height: 12),
            TextField(
              controller: _word,
              obscureText: _hidden,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _submit(),
              decoration: InputDecoration(
                labelText: 'Your safety word',
                suffixIcon: IconButton(
                  icon: Icon(_hidden ? Icons.visibility : Icons.visibility_off),
                  onPressed: () => setState(() => _hidden = !_hidden),
                ),
              ),
            ),
            const SizedBox(height: 14),
            ListenableBuilder(
              listenable: widget.voice,
              builder: (context, _) {
                final on = widget.voice.listening;
                return Listener(
                  onPointerDown: (_) => widget.voice.start(widget.locale, (text) {
                    if (!mounted) return;
                    _word.text = text;
                    _submit(); // spoken word: confirm straight away
                  }),
                  onPointerUp: (_) => widget.voice.stop(),
                  onPointerCancel: (_) => widget.voice.stop(),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    decoration: BoxDecoration(
                      color: on ? botBlue.withAlpha(60) : Colors.white10,
                      borderRadius: BorderRadius.circular(30),
                      border: Border.all(color: botBlue.withAlpha(on ? 255 : 90)),
                    ),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(on ? Icons.graphic_eq : Icons.mic, color: botBlue),
                      const SizedBox(width: 8),
                      Text(on ? 'Listening…' : 'Hold to say it'),
                    ]),
                  ),
                );
              },
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _submit, child: const Text('Confirm')),
      ],
    );
  }
}

/// Create (first time) or change the safety word. The PC stores only a hash of it.
Future<void> setSafetyWord(BuildContext context, BotConnection conn, {bool firstTime = false}) {
  return showDialog<void>(
    context: context,
    builder: (_) => _SetDialog(conn: conn, firstTime: firstTime),
  );
}

class _SetDialog extends StatefulWidget {
  const _SetDialog({required this.conn, required this.firstTime});
  final BotConnection conn;
  final bool firstTime;

  @override
  State<_SetDialog> createState() => _SetDialogState();
}

class _SetDialogState extends State<_SetDialog> {
  final _old = TextEditingController();
  final _new = TextEditingController();
  final _again = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _old.dispose();
    _new.dispose();
    _again.dispose();
    super.dispose();
  }

  void _save() {
    final w = _new.text.trim();
    if (w.replaceAll(' ', '').length < 3) {
      setState(() => _error = 'Use at least 3 letters.');
      return;
    }
    if (w.toLowerCase() != _again.text.trim().toLowerCase()) {
      setState(() => _error = "The two words don't match.");
      return;
    }
    if (!widget.conn.online) {
      setState(() => _error = 'Connect to the PC first.');
      return;
    }
    widget.conn.send({'type': 'set_keyword', 'new': w, 'old': _old.text.trim()});
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final changing = widget.conn.keywordSet;
    return AlertDialog(
      icon: const Icon(Icons.shield, color: botBlue),
      title: Text(changing ? 'Change safety word' : 'Set your safety word'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('BOT will ask for this secret word before it deletes, sends, shares, posts or pays '
                'for anything. Pick something easy to say but hard to guess, and you can say it or type it.'),
            const SizedBox(height: 8),
            if (changing)
              TextField(
                controller: _old,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'Current safety word'),
              ),
            TextField(
              controller: _new,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'New safety word'),
            ),
            TextField(
              controller: _again,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Type it again'),
              onSubmitted: (_) => _save(),
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(widget.firstTime ? 'Later' : 'Cancel'),
        ),
        FilledButton(onPressed: _save, child: const Text('Save')),
      ],
    );
  }
}
