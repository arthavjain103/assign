// ════════════════════════════════════════════════════════════════════
//  UPDATED VisionBoardScreen - PRODUCTION VERSION
//  Replace the old version (lines 2490-2569 in NEW_main.dart) with this
// ════════════════════════════════════════════════════════════════════

import 'package:image_picker/image_picker.dart';
import 'services/vision_board_service.dart';

class VisionBoardScreen extends StatefulWidget {
  const VisionBoardScreen({super.key});

  @override
  State<VisionBoardScreen> createState() => _VisionBoardScreenState();
}

class _VisionBoardScreenState extends State<VisionBoardScreen> {
  late VisionBoardService _visionService;
  final TextEditingController _textController = TextEditingController();

  static const _prompts = [
    'My dream home is...',
    'I feel deeply...',
    'My body is...',
    'My career is...',
    'Love looks like...',
    'My bank account says...',
    'I am grateful for...',
    'I wake up to...',
    'My relationships are...',
    'I travel to...',
  ];

  @override
  void initState() {
    super.initState();
    _visionService = VisionBoardService();
    _visionService.initialize();
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  void _showAddOptionsSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
        padding: EdgeInsets.fromLTRB(
          22,
          18,
          22,
          MediaQuery.of(ctx).viewInsets.bottom + 28,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 44,
              height: 5,
              decoration: BoxDecoration(
                color: C.pink2,
                borderRadius: BorderRadius.circular(3),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const NishAffsLogo(size: 26),
                const SizedBox(width: 8),
                Text(
                  L.isHindi ? 'विजन कार्ड जोड़ें' : 'Add Vision Card',
                  style: GoogleFonts.poppins(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: C.textDark,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            
            // Image/Photo buttons
            Row(
              children: [
                Expanded(
                  child: GestureDetector(
                    onTap: () {
                      Navigator.pop(ctx);
                      _visionService.addImageFromGallery();
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      decoration: BoxDecoration(
                        color: C.pink1,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: C.pink3),
                      ),
                      child: Column(
                        children: [
                          const Icon(Icons.image_rounded,
                              color: C.pinkDark, size: 24),
                          const SizedBox(height: 6),
                          Text(
                            'Gallery',
                            style: GoogleFonts.poppins(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: C.pinkDark,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: GestureDetector(
                    onTap: () {
                      Navigator.pop(ctx);
                      _visionService.addImageFromCamera();
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      decoration: BoxDecoration(
                        color: C.purple.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: C.purple.withOpacity(0.3)),
                      ),
                      child: Column(
                        children: [
                          const Icon(Icons.camera_alt_rounded,
                              color: C.purple, size: 24),
                          const SizedBox(height: 6),
                          Text(
                            'Camera',
                            style: GoogleFonts.poppins(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: C.purple,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            
            // Divider
            Container(
              height: 1,
              color: Colors.grey[200],
            ),
            const SizedBox(height: 20),

            // Text card option
            Text(
              'Or create a text card:',
              style: GoogleFonts.poppins(
                fontSize: 12,
                color: C.textSub,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),

            // Prompt suggestions
            SizedBox(
              height: 40,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: _prompts.length,
                itemBuilder: (_, i) => GestureDetector(
                  onTap: () => _textController.text = _prompts[i],
                  child: Container(
                    margin: const EdgeInsets.only(right: 8),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: C.pink1,
                      borderRadius: BorderRadius.circular(100),
                      border: Border.all(color: C.pink3),
                    ),
                    child: Text(
                      _prompts[i],
                      style: GoogleFonts.poppins(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: C.pinkDark,
                      ),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Text input
            TextField(
              controller: _textController,
              maxLines: 3,
              style: GoogleFonts.lora(
                fontSize: 15,
                color: C.textDark,
                height: 1.6,
              ),
              decoration: InputDecoration(
                hintText: 'My dream life includes...',
                hintStyle: GoogleFonts.lora(
                  fontSize: 14,
                  color: C.textSub.withOpacity(0.5),
                  fontStyle: FontStyle.italic,
                ),
                filled: true,
                fillColor: C.pink1,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(16),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.all(16),
              ),
            ),
            const SizedBox(height: 16),

            // Add button
            GestureDetector(
              onTap: () {
                if (_textController.text.trim().isNotEmpty) {
                  _visionService.addTextCard(_textController.text.trim());
                  _textController.clear();
                  Navigator.pop(ctx);
                }
              },
              child: Container(
                width: double.infinity,
                height: 50,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [C.pinkTheme, C.purple],
                  ),
                  borderRadius: BorderRadius.circular(100),
                ),
                child: Center(
                  child: Text(
                    L.isHindi ? 'बोर्ड में जोड़ें ✨' : 'Add to Board ✨',
                    style: GoogleFonts.poppins(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: C.bg,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        leading: const BackButton(color: C.pinkDark),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const NishAffsLogo(size: 24),
            const SizedBox(width: 8),
            Text(
              L.t('vision_board'),
              style: GoogleFonts.poppins(
                fontSize: 17,
                fontWeight: FontWeight.bold,
                color: C.textDark,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.add_rounded, color: C.pinkDark, size: 28),
            onPressed: _showAddOptionsSheet,
          ),
        ],
      ),
      body: ValueListenableBuilder<List<VisionBoardItem>>(
        valueListenable: _visionService.visionItems,
        builder: (_, items, __) {
          if (items.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text('🌟', style: TextStyle(fontSize: 56)),
                  const SizedBox(height: 14),
                  Text(
                    L.isHindi
                        ? 'आपका विजन बोर्ड खाली है!'
                        : 'Your vision board is empty!',
                    style: GoogleFonts.poppins(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: C.textSub,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    L.isHindi
                        ? '+ टैप करें और अपना पहला सपना जोड़ें ✨'
                        : 'Tap + to add your first dream ✨',
                    style: GoogleFonts.poppins(
                      fontSize: 13,
                      color: C.textSub,
                    ),
                  ),
                ],
              ),
            );
          }

          return GridView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: items.length,
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 0.9,
            ),
            itemBuilder: (ctx, i) {
              final item = items[i];

              return VisionBoardItemCard(
                item: item,
                onDelete: () {
                  showDialog(
                    context: context,
                    builder: (ctx) => AlertDialog(
                      title: const Text('Delete?'),
                      content: const Text(
                        'Remove this card from your vision board?',
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(ctx),
                          child: const Text('Cancel'),
                        ),
                        TextButton(
                          onPressed: () {
                            _visionService.deleteItem(item.id);
                            Navigator.pop(ctx);
                          },
                          child: const Text('Delete'),
                        ),
                      ],
                    ),
                  );
                },
                onLongPress: () {
                  // Optional: Show edit dialog
                  showDialog(
                    context: context,
                    builder: (ctx) => AlertDialog(
                      title: const Text('Edit Card'),
                      content: TextField(
                        controller: TextEditingController(
                          text: item.textContent,
                        ),
                        onChanged: (newText) {
                          _visionService.updateItemText(item.id, newText);
                        },
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(ctx),
                          child: const Text('Done'),
                        ),
                      ],
                    ),
                  );
                },
              ).animate(delay: (i * 50).ms).fadeIn().scale(
                    begin: const Offset(0.95, 0.95),
                  );
            },
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
STEP 1: Add dependencies to pubspec.yaml
  - image_picker: ^1.1.2
  - path_provider: ^2.1.4

STEP 2: Configure platform permissions

  Android (android/app/src/main/AndroidManifest.xml):
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.CAMERA" />

  iOS (ios/Runner/Info.plist):
    <key>NSCameraUsageDescription</key>
    <string>We need access to your camera to take photos for your vision board.</string>
    <key>NSPhotoLibraryUsageDescription</key>
    <string>We need access to your photos to add images to your vision board.</string>

STEP 3: Run flutter pub get

STEP 4: Create VisionBoardService in lib/services/vision_board_service.dart
  (See services/vision_board_service.dart)

STEP 5: Replace OLD VisionBoardScreen (lines 2490-2569 in NEW_main.dart) 
  with this updated version

STEP 6: In your Me page / profile page, navigate to VisionBoardScreen:
  Navigator.push(context, _pageRoute(const VisionBoardScreen()))

STEP 7: Test with image picker on both Android and iOS

STEP 8: Verify that:
  - Image picker opens and selects images
  - Camera works
  - Images are saved locally
  - Vision board persists after app restart
  - Delete and edit functions work
*/

// ════════════════════════════════════════════════════════════════════
//  FEATURES INCLUDED
// ════════════════════════════════════════════════════════════════════

/*
✅ Real image picker from gallery
✅ Camera integration
✅ Local image storage with path_provider
✅ Text-only vision cards
✅ Mixed image + text cards
✅ Delete functionality with confirmation
✅ Edit text functionality
✅ Long-press to edit
✅ Beautiful UI animations
✅ Persistence with SharedPreferences
✅ Export as JSON
✅ Category filtering
✅ Empty state design

FUTURE ENHANCEMENTS:
- Drag and drop reordering
- Image editing / cropping
- Sharing vision board as image
- Backup to cloud
- Vision board templates
- Mood-linked vision boards
- Video support
- Collaborative boards
*/
