import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'connection.dart';

/// Send photos / files to the PC, and share the clipboard both ways.
Future<void> showTransfer(BuildContext context, BotConnection conn) {
  return showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (_) => _TransferSheet(conn: conn),
  );
}

class _TransferSheet extends StatefulWidget {
  const _TransferSheet({required this.conn});
  final BotConnection conn;

  @override
  State<_TransferSheet> createState() => _TransferSheetState();
}

class _TransferSheetState extends State<_TransferSheet> {
  String _status = '';
  bool _ok = true;
  double? _progress;
  StreamSubscription<BotEvent>? _sub;

  BotConnection get conn => widget.conn;

  @override
  void initState() {
    super.initState();
    _sub = conn.events.listen((e) async {
      if (e.type == 'clip') {
        await Clipboard.setData(ClipboardData(text: e.message));
        _show(e.message.isEmpty ? 'The PC clipboard is empty' : 'Copied from the PC: “${_short(e.message)}”');
      } else if (e.type == 'result' && _status.startsWith('Sending clipboard')) {
        _show(e.message, ok: e.ok);
      }
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  String _short(String s) => s.length > 60 ? '${s.substring(0, 60)}…' : s;

  void _show(String text, {bool ok = true}) {
    if (!mounted) return;
    setState(() {
      _status = text;
      _ok = ok;
      _progress = null;
    });
  }

  bool _checkOnline() {
    if (conn.online) return true;
    _show('Connect to the PC first', ok: false);
    return false;
  }

  Future<void> _sendFiles() async {
    if (!_checkOnline()) return;
    final result = await FilePicker.platform.pickFiles(allowMultiple: true, withReadStream: true);
    if (result == null || result.files.isEmpty) return;
    var done = 0;
    for (final f in result.files) {
      final stream = f.readStream;
      if (stream == null) continue;
      setState(() {
        _status = 'Sending ${f.name} (${done + 1}/${result.files.length})…';
        _ok = true;
        _progress = 0;
      });
      try {
        final msg = await conn.uploadFile(f.name, f.size, stream, (p) {
          if (mounted) setState(() => _progress = p);
        });
        done++;
        _show(result.files.length > 1 ? '$msg ($done/${result.files.length})' : msg);
      } catch (e) {
        _show('Couldn\'t send ${f.name}: ${e.toString().replaceFirst('Exception: ', '')}', ok: false);
        return;
      }
    }
    HapticFeedback.mediumImpact();
  }

  Future<void> _sendClipboard() async {
    if (!_checkOnline()) return;
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    final text = data?.text ?? '';
    if (text.isEmpty) {
      _show('Your phone clipboard is empty. Copy some text first.', ok: false);
      return;
    }
    setState(() => _status = 'Sending clipboard…');
    conn.send({'type': 'clip_set', 'text': text});
  }

  void _getClipboard() {
    if (!_checkOnline()) return;
    setState(() => _status = 'Getting the PC clipboard…');
    conn.send({'type': 'clip_get'});
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Phone ⇄ PC', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: _sendFiles,
              icon: const Icon(Icons.photo_library),
              label: const Text('Send photos / files to PC'),
            ),
            const SizedBox(height: 4),
            Text('They arrive in Downloads\\BOT on the PC.',
                textAlign: TextAlign.center, style: TextStyle(color: cs.onSurfaceVariant, fontSize: 12)),
            const SizedBox(height: 14),
            Row(children: [
              Expanded(
                child: FilledButton.tonalIcon(
                  onPressed: _sendClipboard,
                  icon: const Icon(Icons.upload),
                  label: const Text('My clipboard → PC'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.tonalIcon(
                  onPressed: _getClipboard,
                  icon: const Icon(Icons.download),
                  label: const Text('PC clipboard → me'),
                ),
              ),
            ]),
            if (_status.isNotEmpty) ...[
              const SizedBox(height: 16),
              if (_progress != null) LinearProgressIndicator(value: _progress),
              const SizedBox(height: 6),
              Text(_status,
                  textAlign: TextAlign.center, style: TextStyle(color: _ok ? cs.onSurface : cs.error)),
            ],
          ],
        ),
      ),
    );
  }
}
