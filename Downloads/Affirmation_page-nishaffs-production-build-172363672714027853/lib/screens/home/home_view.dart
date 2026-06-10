import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/constants.dart';
import '../../providers/theme_provider.dart';
import '../../widgets/nishaffs_logo.dart';

class HomeView extends ConsumerWidget {
  const HomeView({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = ref.watch(currentThemeProvider);

    return Scaffold(
      backgroundColor: theme.background,
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const NishAffsLogo(size: 28),
                    CircleAvatar(
                      backgroundColor: theme.primary.withValues(alpha: 0.2),
                      child: Text(
                        '✨',
                        style: TextStyle(color: theme.primary, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Namaste, Beautiful 🌸',
                      style: GoogleFonts.playfairDisplay(
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                        color: C.textDark,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Your daily vibe check:',
                      style: GoogleFonts.poppins(
                        fontSize: 16,
                        color: C.textSub,
                      ),
                    ),
                    const SizedBox(height: 16),
                    // Theme Selector
                    SizedBox(
                      height: 50,
                      child: ListView.builder(
                        scrollDirection: Axis.horizontal,
                        itemCount: 7,
                        itemBuilder: (context, index) {
                          return GestureDetector(
                            onTap: () {
                              ref.read(moodOverrideProvider.notifier).setMood(index);
                            },
                            child: Container(
                              margin: const EdgeInsets.only(right: 12),
                              width: 50,
                              decoration: BoxDecoration(
                                color: index == ref.watch(moodOverrideProvider) ? Colors.black26 : Colors.transparent,
                                shape: BoxShape.circle,
                                border: Border.all(color: Colors.black12),
                              ),
                              child: Center(
                                child: Text(['🌸', '💜', '🌿', '✨', '💎', '🌙', '🦋'][index], style: const TextStyle(fontSize: 24)),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 24),
                    // The Strawberry Panda Quote
                    Container(
                      padding: const EdgeInsets.all(24),
                      decoration: BoxDecoration(
                        color: theme.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(24),
                        border: Border.all(color: theme.primary.withValues(alpha: 0.3)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Strawberry Panda Says...',
                            style: GoogleFonts.poppins(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                              color: theme.primary,
                            ),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            '"I am stepping into my highest timeline. The universe is working in my favor."',
                            style: GoogleFonts.lora(
                              fontSize: 24,
                              fontStyle: FontStyle.italic,
                              color: C.textDark,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
