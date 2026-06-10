// ════════════════════════════════════════════════════════════════════
//  PRODUCTION AUDIO PLAYER SERVICE
//  Using just_audio package with real playback
// ════════════════════════════════════════════════════════════════════

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:audio_session/audio_session.dart';
import 'data/affirmations_data.dart';

class AudioPlayerService {
  static final AudioPlayerService _instance = AudioPlayerService._();
  factory AudioPlayerService() => _instance;
  AudioPlayerService._();

  late AudioPlayer _player;
  StreamSubscription? _positionSubscription;
  StreamSubscription? _playerStateSubscription;

  // ════════════════════════════════════════════════════════════════════
  //  STATE NOTIFIERS
  // ════════════════════════════════════════════════════════════════════
  final ValueNotifier<int> currentTrackIndex = ValueNotifier(-1);
  final ValueNotifier<Duration> currentPosition = ValueNotifier(Duration.zero);
  final ValueNotifier<Duration> totalDuration = ValueNotifier(Duration.zero);
  final ValueNotifier<bool> isPlaying = ValueNotifier(false);
  final ValueNotifier<bool> isLoading = ValueNotifier(false);
  final ValueNotifier<double> playbackSpeed = ValueNotifier(1.0);
  final ValueNotifier<PlayerState?> playerState = ValueNotifier(null);

  // ════════════════════════════════════════════════════════════════════
  //  INITIALIZATION
  // ════════════════════════════════════════════════════════════════════
  Future<void> initialize() async {
    _player = AudioPlayer();

    // Configure audio session for background playback
    final session = await AudioSession.instance;
    await session.configure(const AudioSessionConfiguration.music());

    // Listen to player state changes
    _playerStateSubscription = _player.playerStateStream.listen((state) {
      playerState.value = state;
      isLoading.value = state.processingState == ProcessingState.loading;
      isPlaying.value = state.playing;
    });

    // Listen to position updates
    _positionSubscription = _player.positionStream.listen((position) {
      currentPosition.value = position;
    });
  }

  // ════════════════════════════════════════════════════════════════════
  //  PLAYBACK CONTROLS
  // ════════════════════════════════════════════════════════════════════

  /// Play a specific track by index
  Future<void> playTrack(int index) async {
    if (index < 0 || index >= kHealingFrequencies.length) return;

    try {
      final track = kHealingFrequencies[index];
      currentTrackIndex.value = index;
      isLoading.value = true;

      // Set audio source from assets
      await _player.setAsset(track.path);

      // Get duration from the loaded audio
      if (_player.duration != null) {
        totalDuration.value = _player.duration!;
      }

      // Start playback
      await _player.play();
    } catch (e) {
      debugPrint('Error playing track: $e');
      isLoading.value = false;
    }
  }

  /// Pause current playback
  Future<void> pause() async {
    try {
      await _player.pause();
    } catch (e) {
      debugPrint('Error pausing: $e');
    }
  }

  /// Resume playback
  Future<void> resume() async {
    try {
      await _player.play();
    } catch (e) {
      debugPrint('Error resuming: $e');
    }
  }

  /// Stop playback and reset
  Future<void> stop() async {
    try {
      await _player.stop();
      currentTrackIndex.value = -1;
      currentPosition.value = Duration.zero;
      totalDuration.value = Duration.zero;
    } catch (e) {
      debugPrint('Error stopping: $e');
    }
  }

  /// Seek to a specific position
  Future<void> seek(Duration position) async {
    try {
      await _player.seek(position);
    } catch (e) {
      debugPrint('Error seeking: $e');
    }
  }

  /// Seek by percentage (0.0 - 1.0)
  Future<void> seekPercent(double percent) async {
    if (totalDuration.value.inMilliseconds == 0) return;
    final position = Duration(
      milliseconds: (totalDuration.value.inMilliseconds * percent).toInt(),
    );
    await seek(position);
  }

  /// Set playback speed
  Future<void> setPlaybackSpeed(double speed) async {
    try {
      playbackSpeed.value = speed;
      await _player.setSpeed(speed);
    } catch (e) {
      debugPrint('Error setting speed: $e');
    }
  }

  /// Skip to next track
  Future<void> skipNext() async {
    final nextIndex = currentTrackIndex.value + 1;
    if (nextIndex < kHealingFrequencies.length) {
      await playTrack(nextIndex);
    }
  }

  /// Skip to previous track
  Future<void> skipPrevious() async {
    final prevIndex = currentTrackIndex.value - 1;
    if (prevIndex >= 0) {
      await playTrack(prevIndex);
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  HELPER METHODS
  // ════════════════════════════════════════════════════════════════════

  /// Format duration for display (HH:MM:SS)
  String formatDuration(Duration duration) {
    final hours = duration.inHours;
    final minutes = duration.inMinutes % 60;
    final seconds = duration.inSeconds % 60;

    if (hours > 0) {
      return '$hours:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    }
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }

  /// Get current track info
  AudioTrack? get currentTrack {
    if (currentTrackIndex.value >= 0 &&
        currentTrackIndex.value < kHealingFrequencies.length) {
      return kHealingFrequencies[currentTrackIndex.value];
    }
    return null;
  }

  /// Get progress percentage (0.0 - 1.0)
  double get progressPercent {
    if (totalDuration.value.inMilliseconds == 0) return 0.0;
    return currentPosition.value.inMilliseconds /
        totalDuration.value.inMilliseconds;
  }

  // ════════════════════════════════════════════════════════════════════
  //  CLEANUP
  // ════════════════════════════════════════════════════════════════════

  Future<void> dispose() async {
    await _positionSubscription?.cancel();
    await _playerStateSubscription?.cancel();
    await _player.dispose();
  }
}

// ════════════════════════════════════════════════════════════════════
//  USAGE EXAMPLE IN UI
// ════════════════════════════════════════════════════════════════════

/*
class AudioPlayerUI extends StatefulWidget {
  const AudioPlayerUI({super.key});

  @override
  State<AudioPlayerUI> createState() => _AudioPlayerUIState();
}

class _AudioPlayerUIState extends State<AudioPlayerUI> {
  late AudioPlayerService _audioService;

  @override
  void initState() {
    super.initState();
    _audioService = AudioPlayerService();
    _audioService.initialize();
  }

  @override
  void dispose() {
    _audioService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<int>(
      valueListenable: _audioService.currentTrackIndex,
      builder: (_, trackIndex, __) {
        return ValueListenableBuilder<bool>(
          valueListenable: _audioService.isPlaying,
          builder: (_, isPlaying, __) {
            return ValueListenableBuilder<Duration>(
              valueListenable: _audioService.currentPosition,
              builder: (_, position, __) {
                return ValueListenableBuilder<Duration>(
                  valueListenable: _audioService.totalDuration,
                  builder: (_, duration, __) {
                    return Column(
                      children: [
                        // Track display
                        if (trackIndex >= 0 && trackIndex < kHealingFrequencies.length)
                          Text(
                            kHealingFrequencies[trackIndex].name,
                            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                          ),
                        const SizedBox(height: 16),
                        
                        // Progress bar
                        SliderTheme(
                          data: SliderThemeData(
                            trackHeight: 4,
                            thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 8),
                          ),
                          child: Slider(
                            min: 0,
                            max: duration.inMilliseconds.toDouble(),
                            value: position.inMilliseconds.toDouble(),
                            onChanged: (value) {
                              _audioService.seek(Duration(milliseconds: value.toInt()));
                            },
                          ),
                        ),
                        
                        // Time display
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(_audioService.formatDuration(position)),
                              Text(_audioService.formatDuration(duration)),
                            ],
                          ),
                        ),
                        const SizedBox(height: 24),
                        
                        // Controls
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            IconButton(
                              icon: const Icon(Icons.skip_previous),
                              onPressed: () => _audioService.skipPrevious(),
                            ),
                            IconButton(
                              icon: Icon(isPlaying ? Icons.pause : Icons.play_arrow),
                              iconSize: 48,
                              onPressed: () {
                                if (isPlaying) {
                                  _audioService.pause();
                                } else {
                                  _audioService.resume();
                                }
                              },
                            ),
                            IconButton(
                              icon: const Icon(Icons.skip_next),
                              onPressed: () => _audioService.skipNext(),
                            ),
                          ],
                        ),
                      ],
                    );
                  },
                );
              },
            );
          },
        );
      },
    );
  }
}
*/
