import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/data/models/assignment.dart';

void main() {
  test('parses a student assignment list item from the real API', () {
    final assignment = Assignment.fromJson(const {
      'id': 'asg_1',
      'class_id': 'cls_1',
      'course_id': 'crs_1',
      'title': '实验一',
      'description': '完成实验',
      'deadline': '2026-09-15T23:59:59+08:00',
      'submission_type': 'both',
      'max_score': 50.0,
      'allow_resubmit': true,
      'created_at': '2026-07-26T13:47:59+00:00',
      'author_id': 'usr_1',
      'author_name': '李老师',
      'class_name': '计科2班',
      'course_name': '程序设计基础',
    });

    expect(assignment.id, 'asg_1');
    expect(assignment.submissionType, SubmissionType.both);
    expect(assignment.courseName, '程序设计基础');
  });
}
