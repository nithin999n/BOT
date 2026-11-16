import 'package:flutter/material.dart';

import 'face.dart';
import 'home_page.dart';

void main() => runApp(const BotApp());

class BotApp extends StatelessWidget {
  const BotApp({super.key});

  @override
  Widget build(BuildContext context) {
    final scheme = ColorScheme.fromSeed(seedColor: botBlue, brightness: Brightness.dark);
    return MaterialApp(
      title: 'BOT',
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
  }
}
