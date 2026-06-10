// ════════════════════════════════════════════════════════════════════
//  PRODUCTION VISION BOARD SERVICE
//  Real image picker with local file storage
// ════════════════════════════════════════════════════════════════════

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

// ════════════════════════════════════════════════════════════════════
//  VISION BOARD ITEM MODEL
// ════════════════════════════════════════════════════════════════════

class VisionBoardItem {
  final String id;
  final String? imagePath; // Local file path
  final String? textContent; // Optional text overlay
  final DateTime createdAt;
  final String category; // 'image', 'text', 'mixed'

  VisionBoardItem({
    required this.id,
    this.imagePath,
    this.textContent,
    required this.createdAt,
    required this.category,
  });

  // Convert to JSON for persistence
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'imagePath': imagePath,
      'textContent': textContent,
      'createdAt': createdAt.toIso8601String(),
      'category': category,
    };
  }

  // Create from JSON
  factory VisionBoardItem.fromJson(Map<String, dynamic> json) {
    return VisionBoardItem(
      id: json['id'] as String,
      imagePath: json['imagePath'] as String?,
      textContent: json['textContent'] as String?,
      createdAt: DateTime.parse(json['createdAt'] as String),
      category: json['category'] as String? ?? 'mixed',
    );
  }
}

// ════════════════════════════════════════════════════════════════════
//  VISION BOARD SERVICE
// ════════════════════════════════════════════════════════════════════

class VisionBoardService {
  static final VisionBoardService _instance = VisionBoardService._();
  factory VisionBoardService() => _instance;
  VisionBoardService._();

  final ImagePicker _imagePicker = ImagePicker();
  late Directory _visionBoardDir;

  // State management
  final ValueNotifier<List<VisionBoardItem>> visionItems =
      ValueNotifier([]);

  // ════════════════════════════════════════════════════════════════════
  //  INITIALIZATION
  // ════════════════════════════════════════════════════════════════════

  Future<void> initialize() async {
    try {
      // Get application documents directory
      final appDir = await getApplicationDocumentsDirectory();
      _visionBoardDir = Directory('${appDir.path}/vision_board');

      // Create directory if it doesn't exist
      if (!await _visionBoardDir.exists()) {
        await _visionBoardDir.create(recursive: true);
      }

      // Load existing vision items
      await _loadVisionItems();
    } catch (e) {
      debugPrint('Error initializing VisionBoardService: $e');
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  ADD ITEM FROM IMAGE PICKER
  // ════════════════════════════════════════════════════════════════════

  /// Pick image from gallery and add to vision board
  Future<void> addImageFromGallery({String? textOverlay}) async {
    try {
      final XFile? pickedFile = await _imagePicker.pickImage(
        source: ImageSource.gallery,
        imageQuality: 85, // Compress to 85% quality
      );

      if (pickedFile != null) {
        await _addImageToBoard(pickedFile, textOverlay, 'image');
      }
    } catch (e) {
      debugPrint('Error picking image: $e');
    }
  }

  /// Take photo with camera and add to vision board
  Future<void> addImageFromCamera({String? textOverlay}) async {
    try {
      final XFile? pickedFile = await _imagePicker.pickImage(
        source: ImageSource.camera,
        imageQuality: 85,
      );

      if (pickedFile != null) {
        await _addImageToBoard(pickedFile, textOverlay, 'image');
      }
    } catch (e) {
      debugPrint('Error taking photo: $e');
    }
  }

  /// Internal method to add image to vision board
  Future<void> _addImageToBoard(
    XFile imageFile,
    String? textOverlay,
    String category,
  ) async {
    try {
      // Generate unique ID
      final id = DateTime.now().millisecondsSinceEpoch.toString();

      // Copy image to app documents directory
      final localPath =
          '${_visionBoardDir.path}/$id.jpg';
      final copiedFile = await File(imageFile.path).copy(localPath);

      // Create vision board item
      final item = VisionBoardItem(
        id: id,
        imagePath: copiedFile.path,
        textContent: textOverlay,
        createdAt: DateTime.now(),
        category: category,
      );

      // Add to list
      final currentItems = visionItems.value;
      visionItems.value = [item, ...currentItems];

      // Save to persistence
      await _saveVisionItems();
    } catch (e) {
      debugPrint('Error adding image to board: $e');
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  ADD TEXT-ONLY ITEM
  // ════════════════════════════════════════════════════════════════════

  /// Add text-only vision card
  Future<void> addTextCard(String text) async {
    try {
      final id = DateTime.now().millisecondsSinceEpoch.toString();

      final item = VisionBoardItem(
        id: id,
        textContent: text,
        createdAt: DateTime.now(),
        category: 'text',
      );

      final currentItems = visionItems.value;
      visionItems.value = [item, ...currentItems];

      await _saveVisionItems();
    } catch (e) {
      debugPrint('Error adding text card: $e');
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  MANAGE ITEMS
  // ════════════════════════════════════════════════════════════════════

  /// Delete a vision board item
  Future<void> deleteItem(String id) async {
    try {
      // Find and delete the image file if it exists
      final item = visionItems.value.firstWhere(
        (item) => item.id == id,
        orElse: () => VisionBoardItem(
          id: '',
          createdAt: DateTime.now(),
          category: 'text',
        ),
      );

      if (item.imagePath != null) {
        final file = File(item.imagePath!);
        if (await file.exists()) {
          await file.delete();
        }
      }

      // Remove from list
      final updatedItems = visionItems.value
          .where((item) => item.id != id)
          .toList();
      visionItems.value = updatedItems;

      await _saveVisionItems();
    } catch (e) {
      debugPrint('Error deleting item: $e');
    }
  }

  /// Update text content of an item
  Future<void> updateItemText(String id, String newText) async {
    try {
      final items = visionItems.value;
      final index = items.indexWhere((item) => item.id == id);

      if (index >= 0) {
        final updatedItem = VisionBoardItem(
          id: items[index].id,
          imagePath: items[index].imagePath,
          textContent: newText,
          createdAt: items[index].createdAt,
          category: items[index].category,
        );

        items[index] = updatedItem;
        visionItems.value = [...items];
        await _saveVisionItems();
      }
    } catch (e) {
      debugPrint('Error updating item text: $e');
    }
  }

  /// Reorder items
  Future<void> reorderItems(int oldIndex, int newIndex) async {
    try {
      final items = visionItems.value;
      if (oldIndex < items.length && newIndex < items.length) {
        final item = items.removeAt(oldIndex);
        items.insert(newIndex, item);
        visionItems.value = [...items];
        await _saveVisionItems();
      }
    } catch (e) {
      debugPrint('Error reordering items: $e');
    }
  }

  /// Clear all items
  Future<void> clearAll() async {
    try {
      // Delete all image files
      for (final item in visionItems.value) {
        if (item.imagePath != null) {
          final file = File(item.imagePath!);
          if (await file.exists()) {
            await file.delete();
          }
        }
      }

      visionItems.value = [];
      await _saveVisionItems();
    } catch (e) {
      debugPrint('Error clearing vision board: $e');
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  PERSISTENCE
  // ════════════════════════════════════════════════════════════════════

  /// Save vision items to SharedPreferences
  Future<void> _saveVisionItems() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final itemsJson = visionItems.value
          .map((item) => jsonEncode(item.toJson()))
          .toList();
      await prefs.setStringList('vision_board_items', itemsJson);
    } catch (e) {
      debugPrint('Error saving vision items: $e');
    }
  }

  /// Load vision items from SharedPreferences
  Future<void> _loadVisionItems() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final itemsJson = prefs.getStringList('vision_board_items') ?? [];

      final items = itemsJson
          .map((json) => VisionBoardItem.fromJson(jsonDecode(json)))
          .toList();

      visionItems.value = items;
    } catch (e) {
      debugPrint('Error loading vision items: $e');
      visionItems.value = [];
    }
  }

  // ════════════════════════════════════════════════════════════════════
  //  EXPORT / BACKUP
  // ════════════════════════════════════════════════════════════════════

  /// Export vision board as JSON
  Future<String> exportAsJson() async {
    final itemsList = visionItems.value
        .map((item) => item.toJson())
        .toList();
    return jsonEncode(itemsList);
  }

  /// Get total number of items
  int get itemCount => visionItems.value.length;

  /// Get items by category
  List<VisionBoardItem> getItemsByCategory(String category) {
    return visionItems.value
        .where((item) => item.category == category)
        .toList();
  }
}

// ════════════════════════════════════════════════════════════════════
//  HELPER WIDGETS
// ════════════════════════════════════════════════════════════════════

/// Reusable Vision Board Item Display
class VisionBoardItemCard extends StatelessWidget {
  final VisionBoardItem item;
  final VoidCallback? onDelete;
  final VoidCallback? onEdit;
  final VoidCallback? onLongPress;

  const VisionBoardItemCard({
    Key? key,
    required this.item,
    this.onDelete,
    this.onEdit,
    this.onLongPress,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onLongPress: onLongPress,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Stack(
          children: [
            // Background image
            if (item.imagePath != null && item.imagePath!.isNotEmpty)
              Image.file(
                File(item.imagePath!),
                fit: BoxFit.cover,
                width: double.infinity,
                height: double.infinity,
              )
            else
              Container(
                color: Colors.grey[300],
                child: Center(
                  child: Text(
                    item.textContent ?? 'Vision',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Colors.grey,
                    ),
                  ),
                ),
              ),

            // Dark overlay
            Positioned.fill(
              child: Container(
                color: Colors.black.withOpacity(0.3),
              ),
            ),

            // Text overlay
            if (item.textContent != null)
              Positioned(
                bottom: 12,
                left: 12,
                right: 12,
                child: Text(
                  item.textContent!,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),

            // Delete button
            if (onDelete != null)
              Positioned(
                top: 8,
                right: 8,
                child: GestureDetector(
                  onTap: onDelete,
                  child: Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.8),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.close,
                      size: 16,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
