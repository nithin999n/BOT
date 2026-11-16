import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'face.dart';

/// Your BOT's name and colour (the PC bubble cursor matches it).
class BotStyle {
  const BotStyle(this.name, this.color);
  final String name;
  final Color color;
}

const botColors = <String, Color>{
  'Blue': Color(0xFF4FC3FF),
  'Pink': Color(0xFFFF7EB6),
  'Purple': Color(0xFFB388FF),
  'Mint': Color(0xFF5EE6C1),
  'Orange': Color(0xFFFFA74F),
  'Yellow': Color(0xFFFFD54F),
};

final style = ValueNotifier<BotStyle>(const BotStyle('BOT', botBlue));

String colorHex(Color c) =>
    '#${(c.toARGB32() & 0xFFFFFF).toRadixString(16).padLeft(6, '0').toUpperCase()}';

Future<void> loadStyle() async {
  final p = await SharedPreferences.getInstance();
  final name = p.getString('botName') ?? 'BOT';
  final color = p.getInt('botColor');
  style.value = BotStyle(name, color == null ? botBlue : Color(color));
}

Future<void> saveStyle(BotStyle s) async {
  style.value = s;
  final p = await SharedPreferences.getInstance();
  await p.setString('botName', s.name);
  await p.setInt('botColor', s.color.toARGB32());
}

/// Name + colour picker. Returns the new style, or null if cancelled.
Future<BotStyle?> showPersonalize(BuildContext context) {
  return showDialog<BotStyle>(context: context, builder: (_) => const _PersonalizeDialog());
}

class _PersonalizeDialog extends StatefulWidget {
  const _PersonalizeDialog();

  @override
  State<_PersonalizeDialog> createState() => _PersonalizeDialogState();
}

class _PersonalizeDialogState extends State<_PersonalizeDialog> {
  late final TextEditingController _name = TextEditingController(text: style.value.name);
  late Color _color = style.value.color;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Personalize your BOT'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            RobotFace(mood: Mood.happy, size: 130, color: _color),
            TextField(
              controller: _name,
              maxLength: 20,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Name', hintText: 'BOT'),
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              alignment: WrapAlignment.center,
              children: [
                for (final e in botColors.entries)
                  GestureDetector(
                    onTap: () => setState(() => _color = e.value),
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      AnimatedContainer(
                        duration: const Duration(milliseconds: 150),
                        width: 38,
                        height: 38,
                        decoration: BoxDecoration(
                          color: e.value,
                          shape: BoxShape.circle,
                          border: Border.all(
                              color: _color.toARGB32() == e.value.toARGB32() ? Colors.white : Colors.transparent,
                              width: 3),
                          boxShadow: [BoxShadow(color: e.value.withAlpha(120), blurRadius: 10)],
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(e.key, style: const TextStyle(fontSize: 11)),
                    ]),
                  ),
              ],
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          onPressed: () {
            final name = _name.text.trim().isEmpty ? 'BOT' : _name.text.trim();
            Navigator.pop(context, BotStyle(name, _color));
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}
