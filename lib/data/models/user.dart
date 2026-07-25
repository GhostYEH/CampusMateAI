import 'package:equatable/equatable.dart';

/// 应用用户(学生)。
class AppUser extends Equatable {
  const AppUser({
    required this.id,
    required this.name,
    required this.nickname,
    required this.studentId,
    required this.college,
    required this.grade,
    required this.avatarSeed,
  });

  final String id;
  final String name;
  final String nickname;
  final String studentId;
  final String college; // 学院
  final String grade; // 年级,如 "2024级"
  final String avatarSeed; // 头像种子(用于生成头像)

  AppUser copyWith({
    String? id,
    String? name,
    String? nickname,
    String? studentId,
    String? college,
    String? grade,
    String? avatarSeed,
  }) {
    return AppUser(
      id: id ?? this.id,
      name: name ?? this.name,
      nickname: nickname ?? this.nickname,
      studentId: studentId ?? this.studentId,
      college: college ?? this.college,
      grade: grade ?? this.grade,
      avatarSeed: avatarSeed ?? this.avatarSeed,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'nickname': nickname,
        'studentId': studentId,
        'college': college,
        'grade': grade,
        'avatarSeed': avatarSeed,
      };

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'] as String,
        name: json['name'] as String,
        nickname: json['nickname'] as String? ?? json['name'] as String,
        studentId: json['studentId'] as String,
        college: json['college'] as String,
        grade: json['grade'] as String,
        avatarSeed: json['avatarSeed'] as String? ?? json['id'] as String,
      );

  @override
  List<Object?> get props =>
      [id, name, nickname, studentId, college, grade, avatarSeed];
}
