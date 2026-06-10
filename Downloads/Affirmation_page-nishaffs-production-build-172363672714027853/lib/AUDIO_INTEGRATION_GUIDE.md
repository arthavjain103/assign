// ════════════════════════════════════════════════════════════════════
//  UPDATED SoundPlayerService - PRODUCTION VERSION
//  Replace the old version (lines 188-231 in NEW_main.dart) with this
// ════════════════════════════════════════════════════════════════════

import 'package:just_audio/just_audio.dart';

class SoundPlayerService {
  static final instance = SoundPlayerService._();
  SoundPlayerService._();

  late AudioPlayer _player;
  
  final ValueNotifier<int>      idx       = ValueNotifier(-1);
  final ValueNotifier<double>   pos       = ValueNotifier(0.0);
  final ValueNotifier<Duration> elapsed   = ValueNotifier(Duration.zero);
  final ValueNotifier<Duration> total     = ValueNotifier(Duration.zero);
  final ValueNotifier<bool>     isPlaying = ValueNotifier(false);
  final ValueNotifier<bool>     isLoading = ValueNotifier(false);

  // List of audio track paths from kHealingFrequencies
  static final _audioTracks = [
    'assets/audio/432hz_healing.mp3',
    'assets/audio/396hz_fear.mp3',
    'assets/audio/528hz_miracle.mp3',
    'assets/audio/639hz_connection.mp3',
    'assets/audio/741hz_throat.mp3',
    'assets/audio/852hz_intuition.mp3',
    'assets/audio/963hz_crown.mp3',
    'assets/audio/174hz_sleep.mp3',
  ];

  // Initialize audio player
  Future<void> initialize() async {
    _player = AudioPlayer();
    
    // Listen to player state changes
    _player.playerStateStream.listen((playerState) {
      isPlaying.value = playerState.playing;
      isLoading.value = playerState.processingState == ProcessingState.loading;
    });

    // Listen to position updates
    _player.positionStream.listen((position) {
      elapsed.value = position;
      if (total.value.inMilliseconds > 0) {
        pos.value = position.inMilliseconds / total.value.inMilliseconds;
      }
    });

    // Listen to duration
    _player.durationStream.listen((duration) {
      if (duration != null) {
        total.value = duration;
      }
    });
  }

  // Play audio track
  Future<void> play(int i) async {
    if (idx.value == i && isPlaying.value) {
      pause();
      return;
    }

    try {
      isLoading.value = true;

      if (idx.value != i) {
        elapsed.value = Duration.zero;
        pos.value = 0;
      }

      idx.value = i;

      // Load audio from assets
      await _player.setAsset(_audioTracks[i % _audioTracks.length]);
      await _player.play();
    } catch (e) {
      debugPrint('Error playing audio: $e');
      isLoading.value = false;
    }
  }

  void pause() {
    _player.pause();
  }

  void resume() {
    if (idx.value >= 0) {
      _player.play();
    }
  }

  void stop() {
    _player.stop();
    idx.value = -1;
    pos.value = 0;
    elapsed.value = Duration.zero;
    isPlaying.value = false;
  }

  void seek(double v) {
    if (idx.value < 0 || total.value.inMilliseconds == 0) return;
    final newPosition = Duration(
      milliseconds: (v * total.value.inMilliseconds).round(),
    );
    _player.seek(newPosition);
  }

  String fmt(Duration d) =>
      '${d.inHours > 0 ? "${d.inHours}:" : ""}${(d.inMinutes % 60).toString().padLeft(2, "0")}:${(d.inSeconds % 60).toString().padLeft(2, "0")}';

  Duration totalFor(int i) => kHealingFrequencies[i % kHealingFrequencies.length].duration;

  Future<void> dispose() async {
    await _player.dispose();
  }
}


// ════════════════════════════════════════════════════════════════════
//  IMPLEMENTATION IN main.dart
// ════════════════════════════════════════════════════════════════════

// In main() function, add initialization:
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // ... existing code ...
  
  // Initialize audio player
  await SoundPlayerService.instance.initialize();
  
  await AppState.instance.init();
  runApp(const NishAffsApp());
}

// In your SoundCard or SoundScapeWidget, replace timer-based logic with:

class _SoundCard extends StatelessWidget {
  final int idx;
  final String emoji, name, freq;

  const _SoundCard({required this.idx, required this.emoji, required this.name, required this.freq});

  @override
  Widget build(BuildContext context) {
    final svc = SoundPlayerService.instance;

    return GestureDetector(
      onTap: () => svc.play(idx), // Tap to play
      child: ValueListenableBuilder<int>(
        valueListenable: svc.idx,
        builder: (_, currentIdx, __) {
          final isCurrentTrack = currentIdx == idx;
          
          return ValueListenableBuilder<bool>(
            valueListenable: svc.isPlaying,
            builder: (_, isPlaying, __) {
              return ValueListenableBuilder<double>(
                valueListenable: svc.pos,
                builder: (_, progress, __) {
                  return AnimatedContainer(
                    duration: const Duration(milliseconds: 300),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(16),
                      gradient: isCurrentTrack && isPlaying
                          ? const LinearGradient(
                              colors: [C.pinkTheme, C.purple],
                            )
                          : LinearGradient(
                              colors: [C.pink1, C.pink2],
                            ),
                      boxShadow: isCurrentTrack && isPlaying
                          ? [
                              BoxShadow(
                                color: C.pinkTheme.withOpacity(0.4),
                                blurRadius: 20,
                                spreadRadius: 2,
                              )
                            ]
                          : null,
                    ),
                    child: Stack(
                      children: [
                        // Progress overlay
                        if (isCurrentTrack && isPlaying)
                          Positioned.fill(
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(16),
                              child: LinearProgressIndicator(
                                value: progress,
                                backgroundColor: Colors.transparent,
                                valueColor: AlwaysStoppedAnimation(
                                  Colors.white.withOpacity(0.2),
                                ),
                              ),
                            ),
                          ),
                        // Content
                        Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(emoji, style: const TextStyle(fontSize: 32)),
                              const SizedBox(height: 12),
                              Text(
                                name,
                                style: GoogleFonts.poppins(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                              Text(
                                freq,
                                style: GoogleFonts.poppins(
                                  fontSize: 11,
                                  color: Colors.white.withOpacity(0.7),
                                ),
                              ),
                              const Spacer(),
                              // Play/pause icon
                              Center(
                                child: Icon(
                                  isCurrentTrack && isPlaying
                                      ? Icons.pause_circle
                                      : Icons.play_circle_outline,
                                  color: Colors.white,
                                  size: 32,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ).animate().fadeIn().scale(begin: const Offset(0.95, 0.95));
                },
              );
            },
          );
        },
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════
//  AUDIO PLAYER BOTTOM SHEET / FULL SCREEN
// ════════════════════════════════════════════════════════════════════

class AudioPlayerScreen extends StatelessWidget {
  const AudioPlayerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final svc = SoundPlayerService.instance;

    return Scaffold(
      backgroundColor: C.bg,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: const BackButton(color: C.pinkDark),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const NishAffsLogo(size: 24),
            const SizedBox(width: 8),
            Text(
              L.t('sounds'),
              style: GoogleFonts.poppins(
                fontSize: 17,
                fontWeight: FontWeight.bold,
                color: C.textDark,
              ),
            ),
          ],
        ),
      ),
      body: ValueListenableBuilder<int>(
        valueListenable: svc.idx,
        builder: (_, currentIdx, __) {
          if (currentIdx < 0) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text('🎵', style: TextStyle(fontSize: 56)),
                  const SizedBox(height: 16),
                  Text(
                    'Select a healing frequency',
                    style: GoogleFonts.poppins(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: C.textDark,
                    ),
                  ),
                ],
              ),
            );
          }

          final track = kHealingFrequencies[currentIdx];

          return Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                // Album art placeholder
                Container(
                  width: 200,
                  height: 200,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [C.pinkTheme, C.purple],
                    ),
                    borderRadius: BorderRadius.circular(24),
                    boxShadow: [
                      BoxShadow(
                        color: C.pinkTheme.withOpacity(0.3),
                        blurRadius: 20,
                        spreadRadius: 5,
                      ),
                    ],
                  ),
                  child: Center(
                    child: Text(
                      '🎵',
                      style: const TextStyle(fontSize: 80),
                    ),
                  ),
                ),
                const SizedBox(height: 32),

                // Track info
                Text(
                  track.name,
                  style: GoogleFonts.poppins(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: C.textDark,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  track.frequency,
                  style: GoogleFonts.poppins(
                    fontSize: 14,
                    color: C.textSub,
                  ),
                ),
                const SizedBox(height: 24),

                // Progress bar
                ValueListenableBuilder<Duration>(
                  valueListenable: svc.elapsed,
                  builder: (_, elapsed, __) {
                    return ValueListenableBuilder<Duration>(
                      valueListenable: svc.total,
                      builder: (_, total, __) {
                        return Column(
                          children: [
                            SliderTheme(
                              data: const SliderThemeData(
                                trackHeight: 4,
                                thumbShape: RoundSliderThumbShape(
                                  enabledThumbRadius: 8,
                                ),
                              ),
                              child: Slider(
                                min: 0,
                                max: total.inMilliseconds.toDouble(),
                                value: elapsed.inMilliseconds.toDouble(),
                                onChanged: (value) {
                                  svc.seek(
                                    value / total.inMilliseconds,
                                  );
                                },
                              ),
                            ),
                            Padding(
                              padding:
                                  const EdgeInsets.symmetric(horizontal: 16),
                              child: Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    svc.fmt(elapsed),
                                    style: GoogleFonts.poppins(
                                      fontSize: 12,
                                      color: C.textSub,
                                    ),
                                  ),
                                  Text(
                                    svc.fmt(total),
                                    style: GoogleFonts.poppins(
                                      fontSize: 12,
                                      color: C.textSub,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        );
                      },
                    );
                  },
                ),
                const Spacer(),

                // Control buttons
                ValueListenableBuilder<bool>(
                  valueListenable: svc.isPlaying,
                  builder: (_, isPlaying, __) {
                    return Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        IconButton(
                          icon: const Icon(Icons.skip_previous_rounded),
                          iconSize: 32,
                          color: C.pinkDark,
                          onPressed: () {
                            if (currentIdx > 0) {
                              svc.play(currentIdx - 1);
                            }
                          },
                        ),
                        const SizedBox(width: 24),
                        GestureDetector(
                          onTap: () {
                            if (isPlaying) {
                              svc.pause();
                            } else {
                              svc.resume();
                            }
                          },
                          child: Container(
                            width: 70,
                            height: 70,
                            decoration: BoxDecoration(
                              gradient: const LinearGradient(
                                colors: [C.pinkTheme, C.purple],
                              ),
                              shape: BoxShape.circle,
                              boxShadow: [
                                BoxShadow(
                                  color: C.pinkTheme.withOpacity(0.3),
                                  blurRadius: 15,
                                  spreadRadius: 2,
                                ),
                              ],
                            ),
                            child: Center(
                              child: Icon(
                                isPlaying
                                    ? Icons.pause_rounded
                                    : Icons.play_arrow_rounded,
                                color: Colors.white,
                                size: 36,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 24),
                        IconButton(
                          icon: const Icon(Icons.skip_next_rounded),
                          iconSize: 32,
                          color: C.pinkDark,
                          onPressed: () {
                            if (currentIdx < kHealingFrequencies.length - 1) {
                              svc.play(currentIdx + 1);
                            }
                          },
                        ),
                      ],
                    );
                  },
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}


// ════════════════════════════════════════════════════════════════════
//  SETUP INSTRUCTIONS
// ════════════════════════════════════════════════════════════════════

/*
STEP 1: Add audio files to assets/audio/
  - assets/audio/432hz_healing.mp3 (45 min)
  - assets/audio/396hz_fear.mp3 (30 min)
  - assets/audio/528hz_miracle.mp3 (60 min)
  - assets/audio/639hz_connection.mp3 (75 min)
  - assets/audio/741hz_throat.mp3 (45 min)
  - assets/audio/852hz_intuition.mp3 (30 min)
  - assets/audio/963hz_crown.mp3 (60 min)
  - assets/audio/174hz_sleep.mp3 (120 min)

STEP 2: Update pubspec.yaml
  - Add: just_audio: ^0.9.39
  - Add: audio_session: ^0.1.18

STEP 3: Run flutter pub get

STEP 4: Replace OLD SoundPlayerService (lines 188-231 in NEW_main.dart) with this updated version

STEP 5: In main(), add:
  await SoundPlayerService.instance.initialize();

STEP 6: Update any UI widgets that reference SoundPlayerService to use the new stream-based API

STEP 7: Test with real audio playback
*/
