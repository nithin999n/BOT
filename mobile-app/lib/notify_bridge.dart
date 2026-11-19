import 'dart:async';

import 'package:notification_listener_service/notification_event.dart';
import 'package:notification_listener_service/notification_listener_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'connection.dart';

/// Phone calls and chat messages -> the desktop BOT holds up a sign on the PC ("📞 Mom is calling!").
/// Off until you switch it on (BOT's world -> Settings) and allow "Notification access".
class NotifyBridge {
  NotifyBridge(this.conn) {
    instance = this;
  }
  static NotifyBridge? instance;
  final BotConnection conn;
  StreamSubscription<ServiceNotificationEvent>? _sub;
  final Map<String, DateTime> _seen = {};
  bool enabled = false;

  static const _apps = {
    'com.whatsapp': 'WhatsApp',
    'com.whatsapp.w4b': 'WhatsApp',
    'org.telegram.messenger': 'Telegram',
    'com.instagram.android': 'Instagram',
    'com.facebook.orca': 'Messenger',
    'com.snapchat.android': 'Snapchat',
    'com.google.android.apps.messaging': 'Messages',
    'com.samsung.android.messaging': 'Messages',
    'com.android.mms': 'Messages',
    'com.discord': 'Discord',
    'org.thoughtcrime.securesms': 'Signal',
  };
  static const _callApps = [
    'com.google.android.dialer',
    'com.android.dialer',
    'com.samsung.android.incallui',
    'com.android.incallui',
    'com.android.server.telecom',
    'com.oneplus.dialer',
    'com.coloros.incallui',
    'com.android.phone',
  ];

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    enabled = p.getBool('notify_pc') ?? false;
    if (enabled) await start();
  }

  Future<bool> setEnabled(bool on) async {
    final p = await SharedPreferences.getInstance();
    if (on) {
      var ok = await NotificationListenerService.isPermissionGranted();
      if (!ok) ok = await NotificationListenerService.requestPermission();
      if (!ok) return false;
      await start();
    } else {
      await _sub?.cancel();
      _sub = null;
    }
    enabled = on;
    await p.setBool('notify_pc', on);
    return true;
  }

  Future<void> start() async {
    if (_sub != null) return;
    try {
      if (!await NotificationListenerService.isPermissionGranted()) return;
      _sub = NotificationListenerService.notificationsStream.listen(_onEvent, onError: (_) {});
    } catch (_) {
      // not available on this phone
    }
  }

  void _onEvent(ServiceNotificationEvent e) {
    if (e.hasRemoved || !conn.online) return;
    final pkg = e.packageName;
    final title = e.title.trim();
    final text = e.content.trim();
    if (title.isEmpty) return;
    final lower = '$title $text'.toLowerCase();
    final isCall = _callApps.contains(pkg) ||
        (_apps.containsKey(pkg) && (lower.contains('incoming') && lower.contains('call')));
    if (!isCall && !_apps.containsKey(pkg)) return;
    if (isCall && !(lower.contains('incoming') || lower.contains('calling') || lower.contains('ringing') ||
        _callApps.contains(pkg))) {
      return;
    }
    if (isCall && (lower.contains('missed') || lower.contains('ongoing') || lower.contains('on hold'))) return;
    final key = '$pkg|$title|${isCall ? '' : text}';
    final now = DateTime.now();
    final last = _seen[key];
    if (last != null && now.difference(last) < Duration(seconds: isCall ? 30 : 8)) return;
    _seen[key] = now;
    _seen.removeWhere((_, t) => now.difference(t) > const Duration(minutes: 5));
    conn.send({
      'type': 'phone_notification',
      'kind': isCall ? 'call' : 'msg',
      'app': _apps[pkg] ?? 'Phone',
      'title': isCall ? title : '${_apps[pkg]} · $title',
      'text': isCall ? '' : text,
    });
  }

  void dispose() {
    _sub?.cancel();
  }
}
