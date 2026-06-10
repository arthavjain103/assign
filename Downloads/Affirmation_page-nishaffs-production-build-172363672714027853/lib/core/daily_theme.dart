import 'package:flutter/material.dart';

class DailyPalette {
  final String name;
  final Color primary;
  final Color secondary;
  final Color background;

  const DailyPalette(this.name, this.primary, this.secondary, this.background);
}

class DailyTheme {
  static int get hash {
    final d = DateTime.now();
    return (d.day * 31 + d.month) % 7;
  }

  static const palettes = [
    DailyPalette('Rose Monday', Color(0xFFFF6B9D), Color(0xFFFF8FB1), Color(0xFFFFF0F5)),
    DailyPalette('Lavender Tuesday', Color(0xFF9B6BFF), Color(0xFFBA91FF), Color(0xFFF5F0FF)),
    DailyPalette('Mint Wednesday', Color(0xFF5BC4A0), Color(0xFF7DDCBA), Color(0xFFF0FFF8)),
    DailyPalette('Peach Thursday', Color(0xFFFF8A65), Color(0xFFFFAB91), Color(0xFFFFF5EF)),
    DailyPalette('Sky Friday', Color(0xFF42A5F5), Color(0xFF64B5F6), Color(0xFFF0F8FF)),
    DailyPalette('Gold Saturday', Color(0xFFFFB300), Color(0xFFFFD54F), Color(0xFFFFFDE7)),
    DailyPalette('Purple Sunday', Color(0xFFAB47BC), Color(0xFFCE93D8), Color(0xFFF8F0FF)),
  ];

  static DailyPalette get today => palettes[hash];
}
