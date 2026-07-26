import 'package:equatable/equatable.dart';

/// 应用设置(可持久化)。
///
/// 正式参赛版本约束(遵循 AGENTS.md §2):
/// - 不再保留 `demoMode` 字段 — 演示模式入口已从正式产品中移除。
/// - Mock 实现仅供开发与测试使用,通过测试依赖注入控制,
///   不在普通用户设置中暴露。
class AppSettings extends Equatable {
  const AppSettings({
    this.darkMode = false,
    this.reduceMotion = false,
    this.notificationSourcesEnabled = true,
    this.reminderEnabled = true,
    this.reminderLeadMinutes = 60,
    this.cameraPermissionGranted = false,
    this.expressionRecognitionEnabled = false,
    this.counselorProactiveSuggestion = true,
    this.modelVersion = 'mock-v0.1',
    this.studyRestIntervalMinutes = 45,
    this.expressionConfidenceThreshold = 0.45,
    this.expressionStableFrames = 5,
    this.suggestionCooldownMinutes = 15,
  });

  final bool darkMode; // 深色模式
  final bool reduceMotion; // 减少动态效果
  final bool notificationSourcesEnabled; // 通知来源开关
  final bool reminderEnabled; // 提醒开关
  final int reminderLeadMinutes; // 提前提醒分钟数
  final bool cameraPermissionGranted; // 摄像头权限
  final bool expressionRecognitionEnabled; // 表情识别开关
  final bool counselorProactiveSuggestion; // AI导员主动建议
  final String modelVersion; // 模型版本(Mock 标注)
  final int studyRestIntervalMinutes; // 休息提醒间隔
  final double expressionConfidenceThreshold; // 置信度阈值
  final int expressionStableFrames; // 稳定所需帧数
  final int suggestionCooldownMinutes; // 建议冷却分钟

  AppSettings copyWith({
    bool? darkMode,
    bool? reduceMotion,
    bool? notificationSourcesEnabled,
    bool? reminderEnabled,
    int? reminderLeadMinutes,
    bool? cameraPermissionGranted,
    bool? expressionRecognitionEnabled,
    bool? counselorProactiveSuggestion,
    String? modelVersion,
    int? studyRestIntervalMinutes,
    double? expressionConfidenceThreshold,
    int? expressionStableFrames,
    int? suggestionCooldownMinutes,
  }) {
    return AppSettings(
      darkMode: darkMode ?? this.darkMode,
      reduceMotion: reduceMotion ?? this.reduceMotion,
      notificationSourcesEnabled:
          notificationSourcesEnabled ?? this.notificationSourcesEnabled,
      reminderEnabled: reminderEnabled ?? this.reminderEnabled,
      reminderLeadMinutes: reminderLeadMinutes ?? this.reminderLeadMinutes,
      cameraPermissionGranted:
          cameraPermissionGranted ?? this.cameraPermissionGranted,
      expressionRecognitionEnabled:
          expressionRecognitionEnabled ?? this.expressionRecognitionEnabled,
      counselorProactiveSuggestion:
          counselorProactiveSuggestion ?? this.counselorProactiveSuggestion,
      modelVersion: modelVersion ?? this.modelVersion,
      studyRestIntervalMinutes:
          studyRestIntervalMinutes ?? this.studyRestIntervalMinutes,
      expressionConfidenceThreshold:
          expressionConfidenceThreshold ?? this.expressionConfidenceThreshold,
      expressionStableFrames:
          expressionStableFrames ?? this.expressionStableFrames,
      suggestionCooldownMinutes:
          suggestionCooldownMinutes ?? this.suggestionCooldownMinutes,
    );
  }

  Map<String, dynamic> toJson() => {
        'darkMode': darkMode,
        'reduceMotion': reduceMotion,
        'notificationSourcesEnabled': notificationSourcesEnabled,
        'reminderEnabled': reminderEnabled,
        'reminderLeadMinutes': reminderLeadMinutes,
        'cameraPermissionGranted': cameraPermissionGranted,
        'expressionRecognitionEnabled': expressionRecognitionEnabled,
        'counselorProactiveSuggestion': counselorProactiveSuggestion,
        'modelVersion': modelVersion,
        'studyRestIntervalMinutes': studyRestIntervalMinutes,
        'expressionConfidenceThreshold': expressionConfidenceThreshold,
        'expressionStableFrames': expressionStableFrames,
        'suggestionCooldownMinutes': suggestionCooldownMinutes,
      };

  factory AppSettings.fromJson(Map<String, dynamic> json) => AppSettings(
        darkMode: json['darkMode'] as bool? ?? false,
        reduceMotion: json['reduceMotion'] as bool? ?? false,
        notificationSourcesEnabled:
            json['notificationSourcesEnabled'] as bool? ?? true,
        reminderEnabled: json['reminderEnabled'] as bool? ?? true,
        reminderLeadMinutes: json['reminderLeadMinutes'] as int? ?? 60,
        cameraPermissionGranted:
            json['cameraPermissionGranted'] as bool? ?? false,
        expressionRecognitionEnabled:
            json['expressionRecognitionEnabled'] as bool? ?? false,
        counselorProactiveSuggestion:
            json['counselorProactiveSuggestion'] as bool? ?? true,
        modelVersion: json['modelVersion'] as String? ?? 'mock-v0.1',
        studyRestIntervalMinutes:
            json['studyRestIntervalMinutes'] as int? ?? 45,
        expressionConfidenceThreshold:
            (json['expressionConfidenceThreshold'] as num?)?.toDouble() ?? 0.45,
        expressionStableFrames: json['expressionStableFrames'] as int? ?? 5,
        suggestionCooldownMinutes:
            json['suggestionCooldownMinutes'] as int? ?? 15,
      );

  @override
  List<Object?> get props => [
        darkMode,
        reduceMotion,
        notificationSourcesEnabled,
        reminderEnabled,
        reminderLeadMinutes,
        cameraPermissionGranted,
        expressionRecognitionEnabled,
        counselorProactiveSuggestion,
        modelVersion,
        studyRestIntervalMinutes,
        expressionConfidenceThreshold,
        expressionStableFrames,
        suggestionCooldownMinutes,
      ];
}
