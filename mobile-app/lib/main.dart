import 'package:flutter/material.dart';

import 'home_page.dart';
import 'style.dart';

void main() => runApp(const BotApp());

class BotApp extends StatelessWidget {
  const BotApp({super.key});

  @override
  Widget build(BuildContext context) {
    // The whole app follows BOT's colour (⋮ menu -> Name & colour).
    return ValueListenableBuilder<BotStyle>(
      valueListenable: style,
      builder: (context, s, _) {
        final scheme = ColorScheme.fromSeed(seedColor: s.color, brightness: Brightness.dark);
        return MaterialApp(
          title: s.name,
          debugShowCheckedModeBanner: false,
          themeMode: ThemeMode.dark,
          darkTheme: ThemeData(
            useMaterial3: true,
            colorScheme: scheme,
            scaffoldBackgroundColor: const Color(0xFF070C1C),
            appBarTheme: const AppBarTheme(backgroundColor: Color(0xFF070C1C), centerTitle: false),
          ),
          theme: ThemeData(useMaterial3: true, colorScheme: scheme),
          home: const HomePage(),
        );
      },
    );
  }
}
