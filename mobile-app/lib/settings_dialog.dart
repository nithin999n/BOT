import 'package:flutter/material.dart';

import 'discovery.dart';

class ConnSettings {
  const ConnSettings(this.host, this.port, this.pin, this.name, this.remoteHost);
  final String host;
  final int port;
  final String pin;
  final String name; // PC name, used to find it again if its IP changes
  final String remoteHost; // Tailscale address for outside use
}

class SettingsDialog extends StatefulWidget {
  const SettingsDialog({super.key, required this.initial});
  final ConnSettings initial;

  @override
  State<SettingsDialog> createState() => _SettingsDialogState();
}

class _SettingsDialogState extends State<SettingsDialog> {
  late final TextEditingController _host = TextEditingController(text: widget.initial.host);
  late final TextEditingController _port = TextEditingController(text: widget.initial.port.toString());
  late final TextEditingController _pin = TextEditingController(text: widget.initial.pin);
  late final TextEditingController _remote = TextEditingController(text: widget.initial.remoteHost);
  late String _name = widget.initial.name;
  String? _error;
  bool _searching = true; // a search starts as soon as the dialog opens
  List<FoundPc> _found = const [];

  @override
  void initState() {
    super.initState();
    _search();
  }

  @override
  void dispose() {
    _host.dispose();
    _port.dispose();
    _pin.dispose();
    _remote.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    if (!_searching) setState(() => _searching = true);
    final pcs = await discoverPcs();
    if (!mounted) return;
    setState(() {
      _searching = false;
      _found = pcs;
    });
    if (pcs.length == 1 && _host.text.trim().isEmpty) _pick(pcs.first);
  }

  void _pick(FoundPc pc) {
    setState(() {
      _host.text = pc.host;
      _port.text = pc.port.toString();
      if (pc.tailscale.isNotEmpty) _remote.text = pc.tailscale;
      _name = pc.name;
      _error = null;
    });
  }

  void _save() {
    var host = _host.text.trim().replaceFirst(RegExp(r'^wss?://'), '');
    var port = int.tryParse(_port.text.trim()) ?? 0;
    if (host.contains(':')) {
      final parts = host.split(':');
      host = parts.first;
      port = int.tryParse(parts.last) ?? port;
    }
    final pin = _pin.text.trim();
    final remote = _remote.text.trim();
    if ((host.isEmpty && remote.isEmpty) || port <= 0 || port > 65535 || pin.isEmpty) {
      setState(() => _error = host.isEmpty && remote.isEmpty
          ? 'Pick your PC from the list (or type its IP address).'
          : 'Please enter the PIN shown on the PC.');
      return;
    }
    // Keep the remembered PC name only if it still belongs to this address.
    final name =
        (host == widget.initial.host || _found.any((p) => p.host == host && p.name == _name)) ? _name : '';
    Navigator.pop(context, ConnSettings(host, port, pin, name, remote));
  }

  Widget _foundList(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    if (_searching) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 8),
        child: Row(children: [
          SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
          SizedBox(width: 12),
          Expanded(child: Text('Looking for your PC on Wi-Fi…')),
        ]),
      );
    }
    if (_found.isEmpty) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
              'No PC found on this Wi-Fi. Check that BOT is running on the PC, '
              'or type the address below.',
              style: TextStyle(color: cs.onSurfaceVariant)),
          TextButton.icon(onPressed: _search, icon: const Icon(Icons.refresh), label: const Text('Search again')),
        ],
      );
    }
    return Column(
      children: [
        for (final pc in _found)
          Card(
            margin: const EdgeInsets.symmetric(vertical: 4),
            color: _host.text.trim() == pc.host ? cs.primaryContainer : null,
            child: ListTile(
              leading: const Icon(Icons.computer),
              title: Text(pc.name),
              subtitle: Text('${pc.host}:${pc.port}'),
              trailing: _host.text.trim() == pc.host ? const Icon(Icons.check_circle) : null,
              onTap: () => _pick(pc),
            ),
          ),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(onPressed: _search, icon: const Icon(Icons.refresh), label: const Text('Search again')),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final label = Theme.of(context).textTheme.labelLarge;
    return AlertDialog(
      title: const Text('Connect to your PC'),
      content: SizedBox(
        width: double.maxFinite,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _foundList(context),
              const SizedBox(height: 8),
              const Text('Then enter the PIN shown on the PC (or run "python autostart.py status").'),
              TextField(
                controller: _pin,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'PIN'),
              ),
              const SizedBox(height: 18),
              Text('Use BOT outside home (Tailscale)', style: label),
              TextField(
                controller: _remote,
                keyboardType: TextInputType.url,
                decoration: const InputDecoration(
                  labelText: 'Tailscale address of the PC',
                  hintText: '100.x.y.z',
                  helperText: 'Filled in automatically once Tailscale runs on the PC',
                  helperMaxLines: 2,
                ),
              ),
              const SizedBox(height: 18),
              Text('Manual address (home Wi-Fi)', style: label),
              TextField(
                controller: _host,
                keyboardType: TextInputType.url,
                decoration: const InputDecoration(labelText: 'PC IP address', hintText: '192.168.1.10'),
              ),
              TextField(
                controller: _port,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Port'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _save, child: const Text('Connect')),
      ],
    );
  }
}
