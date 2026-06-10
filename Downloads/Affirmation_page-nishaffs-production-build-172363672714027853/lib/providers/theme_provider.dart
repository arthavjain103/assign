import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/daily_theme.dart';

final themeProvider = Provider<DailyPalette>((ref) {
  return DailyTheme.today;
});

class MoodOverrideNotifier extends Notifier<int?> {
  @override
  int? build() => null;

  void setMood(int mood) {
    state = mood;
  }
}

final moodOverrideProvider = NotifierProvider<MoodOverrideNotifier, int?>(() {
  return MoodOverrideNotifier();
});

final currentThemeProvider = Provider<DailyPalette>((ref) {
  final mood = ref.watch(moodOverrideProvider);
  if (mood != null && mood >= 0 && mood < DailyTheme.palettes.length) {
    return DailyTheme.palettes[mood];
  }
  return ref.watch(themeProvider);
});
