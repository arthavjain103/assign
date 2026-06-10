import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../screens/home/home_view.dart';
import '../screens/home/main_scaffold.dart';
import '../screens/community/community_view.dart';
import '../screens/diary/diary_screen.dart';
import '../screens/profile/profile_view.dart';

final routerProvider = Provider<GoRouter>((ref) {

  return GoRouter(
    initialLocation: '/',
    routes: [
      ShellRoute(
        builder: (context, state, child) => MainScaffold(child: child),
        routes: [
          GoRoute(
            path: '/',
            builder: (context, state) => const HomeView(),
          ),
          GoRoute(
            path: '/community',
            builder: (context, state) => const CommunityView(),
          ),
          GoRoute(
            path: '/diary',
            builder: (context, state) => const DiaryScreen(),
          ),
          GoRoute(
            path: '/profile',
            builder: (context, state) => const ProfileView(),
          ),
        ],
      ),
    ],
  );
});
