import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class NishAffsLogo extends StatelessWidget {
  final double size;
  const NishAffsLogo({super.key, this.size = 24});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Image.asset(
          'assets/icon/logo.jpg',
          height: size * 1.5,
          errorBuilder: (context, error, stackTrace) =>
              Icon(Icons.spa, color: const Color(0xFFFF82A9), size: size),
        ),
        const SizedBox(width: 6),
        Text(
          'NishAffs',
          style: GoogleFonts.playfairDisplay(
            fontSize: size * 0.85,
            fontWeight: FontWeight.w800,
            color: const Color(0xFF2D2D2D),
          ),
        ),
      ],
    );
  }
}
