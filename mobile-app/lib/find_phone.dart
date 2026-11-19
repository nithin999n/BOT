import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'face.dart';
import 'style.dart';

bool _ringing = false;

/// "Find my phone" from the PC: play a loud tune (alarm volume, works on silent) until you tap "Found it".
Future<void> showFindPhone(BuildContext context) async {
  if (_ringing) return;
  _ringing = true;
  final player = AudioPlayer();
  Timer? buzz;
  try {
    await player.setAudioContext(AudioContext(
      android: const AudioContextAndroid(
        usageType: AndroidUsageType.alarm,
        contentType: AndroidContentType.sonification,
        audioFocus: AndroidAudioFocus.gainTransient,
        stayAwake: true,
      ),
    ));
    await player.setReleaseMode(ReleaseMode.loop);
    await player.play(AssetSource('find_phone.wav'), volume: 1.0);
  } catch (_) {
    // no sound possible: the vibration and the screen still help
  }
  buzz = Timer.periodic(const Duration(milliseconds: 700), (_) => HapticFeedback.heavyImpact());
  if (context.mounted) {
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: const Text('Here I am! 📢', textAlign: TextAlign.center),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          RobotFace(mood: Mood.excited, size: 120, color: style.value.color),
          const SizedBox(height: 8),
          const Text('BOT on your PC is looking for your phone', textAlign: TextAlign.center),
        ]),
        actions: [
          FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('Found it! 🥰')),
        ],
      ),
    );
  }
  buzz.cancel();
  await player.stop();
  await player.dispose();
  _ringing = false;
}
