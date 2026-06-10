import 'package:flutter/material.dart';

class C {
  // Brand Colors
  static const Color pinkTheme = Color(0xFFFF82A9);
  static const Color pinkLight = Color(0xFFFFB6CB);
  static const Color pinkDark  = Color(0xFFD64D7B);
  static const Color pink1     = Color(0xFFFFF0F5);
  static const Color pink2     = Color(0xFFFFE4EE);
  static const Color pink3     = Color(0xFFFFD6E4);

  // Accents
  static const Color purple    = Color(0xFFB185FF);
  static const Color purpleLight = Color(0xFFE8DDFF);
  static const Color yellow    = Color(0xFFFFD166);
  static const Color mint      = Color(0xFF88D4AB);

  // Backgrounds & Text
  static const Color bg        = Color(0xFFFAFAFC);
  static const Color surface   = Colors.white;
  static const Color textDark  = Color(0xFF2D2D2D);
  static const Color textSub   = Color(0xFF6B6B6B);

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [pinkTheme, purple],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}
