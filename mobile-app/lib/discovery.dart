import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// UDP port the BOT PC agent listens on for "where are you?" broadcasts.
const discoveryPort = 8766;
const _magic = 'BOT_DISCOVER_V1';

class FoundPc {
  const FoundPc(this.name, this.host, this.port, {this.tailscale = ''});
  final String name;
  final String host;
  final int port;
  final String tailscale; // the PC's Tailscale address, if it has one (for outside use)
}

/// Broadcasts on the local Wi-Fi and collects every BOT PC that answers.
Future<List<FoundPc>> discoverPcs({
  Duration listenFor = const Duration(milliseconds: 2000),
}) async {
  final RawDatagramSocket sock;
  try {
    sock = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
  } catch (_) {
    return const [];
  }
  sock.broadcastEnabled = true;

  final found = <String, FoundPc>{};
  final sub = sock.listen((event) {
    if (event != RawSocketEvent.read) return;
    final dg = sock.receive();
    if (dg == null) return;
    try {
      final msg = jsonDecode(utf8.decode(dg.data)) as Map<String, dynamic>;
      if (msg['bot'] != 'BOT') return;
      final host = dg.address.address;
      final port = (msg['port'] as num?)?.toInt() ?? 8765;
      found['$host:$port'] = FoundPc((msg['name'] ?? host).toString(), host, port,
          tailscale: (msg['tailscale'] ?? '').toString());
    } catch (_) {
      // not a BOT reply
    }
  });

  try {
    // Global broadcast plus each local /24 subnet broadcast (some routers drop one or the other).
    final targets = <String>{'255.255.255.255'};
    try {
      final ifaces = await NetworkInterface.list(type: InternetAddressType.IPv4);
      for (final iface in ifaces) {
        for (final a in iface.addresses) {
          final p = a.address.split('.');
          if (p.length == 4 && !a.isLoopback) targets.add('${p[0]}.${p[1]}.${p[2]}.255');
        }
      }
    } catch (_) {
      // interface listing not allowed; global broadcast only
    }
    final payload = utf8.encode(_magic);
    for (var round = 0; round < 3; round++) {
      for (final t in targets) {
        try {
          sock.send(payload, InternetAddress(t), discoveryPort);
        } catch (_) {
          // unreachable subnet; ignore
        }
      }
      await Future<void>.delayed(const Duration(milliseconds: 300));
    }
    await Future<void>.delayed(listenFor);
  } finally {
    await sub.cancel();
    sock.close();
  }
  return found.values.toList()..sort((a, b) => a.name.compareTo(b.name));
}
