import 'dart:async';

import 'package:flutter/material.dart';

import 'connection.dart';
import 'face.dart';
import 'style.dart';

/// "Talk to BOT": a little chat. BOT answers with its own cute replies (or real AI with a free Gemini key on the PC).
class ChatPage extends StatefulWidget {
  const ChatPage({super.key, required this.conn});
  final BotConnection conn;

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<(bool, String)> _msgs = [(false, 'Hiii! 💙 Talk to me about anything. I\'m all ears 🥰')];
  StreamSubscription<BotEvent>? _sub;
  bool _waiting = false;

  @override
  void initState() {
    super.initState();
    _sub = widget.conn.events.listen((e) {
      if (e.type == 'chat_reply' && mounted) {
        setState(() {
          _waiting = false;
          _msgs.add((false, e.message));
        });
        _toBottom();
      }
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _toBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      }
    });
  }

  void _send() {
    final text = _input.text.trim();
    if (text.isEmpty) return;
    if (!widget.conn.online) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Not connected to the PC')));
      return;
    }
    widget.conn.send({'type': 'chat', 'text': text});
    setState(() {
      _msgs.add((true, text));
      _waiting = true;
    });
    _input.clear();
    _toBottom();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('💬 Talk to BOT')),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: RobotFace(mood: _waiting ? Mood.thinking : Mood.happy, size: 80, color: style.value.color),
        ),
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.all(12),
            itemCount: _msgs.length + (_waiting ? 1 : 0),
            itemBuilder: (context, i) {
              if (i == _msgs.length) {
                return const Align(alignment: Alignment.centerLeft, child: Text('  BOT is typing… 💭'));
              }
              final (mine, text) = _msgs[i];
              return Align(
                alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  margin: const EdgeInsets.symmetric(vertical: 4),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                  decoration: BoxDecoration(
                    color: mine ? cs.primaryContainer : cs.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(text),
                ),
              );
            },
          ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 4, 8, 8),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _input,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _send(),
                  decoration: const InputDecoration(hintText: 'Say something to BOT…', border: OutlineInputBorder()),
                ),
              ),
              IconButton(icon: const Icon(Icons.send), onPressed: _send),
            ]),
          ),
        ),
      ]),
    );
  }
}
