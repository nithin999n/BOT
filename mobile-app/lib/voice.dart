import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Hold-to-talk speech recognition shared by every screen of the app.
class Voice extends ChangeNotifier {
  final SpeechToText _stt = SpeechToText();
  bool ready = false;
  bool listening = false;
  String heard = '';
  double level = 0; // microphone loudness 0..1

  /// Shown to the user when something goes wrong ("Didn't catch that"...).
  void Function(String message)? onProblem;

  void Function(String text)? _onDone;
  bool _delivered = true;
  Timer? _deliverTimer;

  Future<bool> init() async {
    try {
      ready = await _stt.initialize(onStatus: _onStatus, onError: _onError);
    } catch (_) {
      ready = false;
    }
    notifyListeners();
    return ready;
  }

  /// Start listening; [onDone] gets the final text once (when the user lets go or stops talking).
  Future<void> start(String locale, void Function(String text) onDone) async {
    if (!ready) {
      onProblem?.call('Voice is not available. Type instead.');
      return;
    }
    _deliverTimer?.cancel();
    _onDone = onDone;
    _delivered = false;
    heard = '';
    level = 0;
    listening = true;
    notifyListeners();
    try {
      await _stt.listen(
        onResult: _onResult,
        localeId: locale,
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(seconds: 4),
        onSoundLevelChange: (l) {
          // Android reports roughly -2..10 dB
          level = ((l + 2) / 12).clamp(0.0, 1.0);
          notifyListeners();
        },
        listenOptions: SpeechListenOptions(
          partialResults: true,
          cancelOnError: true,
          listenMode: ListenMode.dictation,
        ),
      );
    } catch (e) {
      listening = false;
      notifyListeners();
      onProblem?.call('Could not start the mic: $e');
    }
  }

  Future<void> stop() async {
    if (!listening) return;
    listening = false;
    notifyListeners();
    await _stt.stop();
    _scheduleDeliver();
  }

  void _onStatus(String status) {
    if (status == 'done' || status == 'notListening') {
      if (listening) {
        listening = false;
        notifyListeners();
      }
      _scheduleDeliver();
    }
  }

  void _onError(SpeechRecognitionError e) {
    listening = false;
    notifyListeners();
    if (heard.trim().isNotEmpty) {
      _scheduleDeliver();
    } else if (e.errorMsg == 'error_no_match' || e.errorMsg == 'error_speech_timeout') {
      onProblem?.call("Didn't catch that. Hold and speak again.");
    } else {
      onProblem?.call('Mic error: ${e.errorMsg}');
    }
  }

  void _onResult(SpeechRecognitionResult r) {
    heard = r.recognizedWords;
    notifyListeners();
    if (r.finalResult) _deliver();
  }

  /// Wait briefly for the final transcript; deliver whatever we heard if it never comes.
  void _scheduleDeliver() {
    if (_delivered) return;
    _deliverTimer?.cancel();
    _deliverTimer = Timer(const Duration(milliseconds: 1200), _deliver);
  }

  void _deliver() {
    if (_delivered) return;
    final t = heard.trim();
    if (t.isEmpty) return;
    _delivered = true;
    _deliverTimer?.cancel();
    _onDone?.call(t);
  }

  @override
  void dispose() {
    _deliverTimer?.cancel();
    _stt.cancel();
    super.dispose();
  }
}
