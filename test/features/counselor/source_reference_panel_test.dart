import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/data/models/chat.dart';
import 'package:campus_companion/features/counselor/presentation/widgets/answer_meta_badge.dart';
import 'package:campus_companion/features/counselor/presentation/widgets/source_reference_panel.dart';

void main() {
  /// 构造 [KnowledgeSource] 的辅助方法,便于以各种 flag 组合测试。
  KnowledgeSource makeSource({
    required String id,
    required String title,
    bool isOfficial = false,
    bool isExpired = false,
    bool isDemo = false,
    DateTime? updatedAt,
    DateTime? publishedAt,
    String? snippet,
  }) {
    return KnowledgeSource(
      id: id,
      title: title,
      updatedAt: updatedAt ?? DateTime(2024, 10, 15),
      publishedAt: publishedAt,
      isOfficial: isOfficial,
      isExpired: isExpired,
      isDemo: isDemo,
      snippet: snippet,
    );
  }

  /// 包裹子组件并提供 MaterialApp + Directionality,确保 InkWell / Theme 可用。
  Widget wrap(Widget child) {
    return MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: Scaffold(
        body: SingleChildScrollView(child: child),
      ),
    );
  }

  group('SourceReferencePanel', () {
    testWidgets(
      'shows "知识库来源" title when isRealBackend=true',
      (tester) async {
        final sources = [makeSource(id: 's1', title: '学生手册')];
        await tester.pumpWidget(
          wrap(
            SourceReferencePanel(sources: sources, isRealBackend: true),
          ),
        );

        expect(find.text('知识库来源'), findsOneWidget);
        expect(find.text('参考来源(模拟)'), findsNothing);
      },
    );

    testWidgets(
      'shows "参考来源(模拟)" when isRealBackend=false (mock)',
      (tester) async {
        final sources = [makeSource(id: 's1', title: '学生手册')];
        await tester.pumpWidget(
          wrap(
            SourceReferencePanel(sources: sources, isRealBackend: false),
          ),
        );

        expect(find.text('参考来源(模拟)'), findsOneWidget);
        expect(find.text('知识库来源'), findsNothing);
      },
    );

    testWidgets('shows source titles when sources provided', (tester) async {
      final sources = [
        makeSource(id: 's1', title: '学生综合测评实施细则'),
        makeSource(id: 's2', title: '奖学金评定办法'),
      ];
      await tester.pumpWidget(wrap(SourceReferencePanel(sources: sources)));

      expect(find.text('学生综合测评实施细则'), findsOneWidget);
      expect(find.text('奖学金评定办法'), findsOneWidget);
    });

    testWidgets('shows "官方" badge for official sources', (tester) async {
      final sources = [
        makeSource(id: 's1', title: '官方文件', isOfficial: true),
      ];
      await tester.pumpWidget(wrap(SourceReferencePanel(sources: sources)));

      expect(find.text('官方'), findsOneWidget);
    });

    testWidgets('shows "已过期" badge for expired sources', (tester) async {
      final sources = [
        makeSource(id: 's1', title: '过期文件', isExpired: true),
      ];
      await tester.pumpWidget(wrap(SourceReferencePanel(sources: sources)));

      expect(find.text('已过期'), findsOneWidget);
    });

    testWidgets('shows "仿真资料" badge for demo sources', (tester) async {
      final sources = [
        makeSource(id: 's1', title: '演示文件', isDemo: true),
      ];
      await tester.pumpWidget(wrap(SourceReferencePanel(sources: sources)));

      expect(find.text('仿真资料'), findsOneWidget);
    });

    testWidgets(
      'shows conflict hint banner when hasConflict=true',
      (tester) async {
        final sources = [
          makeSource(id: 's1', title: '文件A'),
          makeSource(id: 's2', title: '文件B'),
        ];
        await tester.pumpWidget(
          wrap(
            SourceReferencePanel(sources: sources, hasConflict: true),
          ),
        );

        // 标题变为 "参考来源(模拟) · 资料冲突"
        expect(
          find.text('参考来源(模拟) · 资料冲突'),
          findsOneWidget,
        );
        // 冲突提示横幅出现(无官方来源时,使用第一种文案)
        expect(
          find.textContaining('资料存在冲突,以下来源仅供对比参考'),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'shows "较新官方" badge for newest official source when conflict',
      (tester) async {
        final sources = [
          makeSource(
            id: 's_old',
            title: '旧版官方文件',
            isOfficial: true,
            publishedAt: DateTime(2023, 6, 1),
          ),
          makeSource(
            id: 's_new',
            title: '新版官方文件',
            isOfficial: true,
            publishedAt: DateTime(2024, 6, 1),
          ),
        ];
        await tester.pumpWidget(
          wrap(
            SourceReferencePanel(sources: sources, hasConflict: true),
          ),
        );

        // "较新官方" 徽章应出现(仅最新的官方来源被高亮)
        expect(find.text('较新官方'), findsOneWidget);
        // 冲突提示横幅(有官方来源时,使用第二种文案)
        expect(
          find.textContaining('已标记较新的官方资料'),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'shows "展开剩余" expand button when sources > 2',
      (tester) async {
        final sources = [
          makeSource(id: 's1', title: '文件1'),
          makeSource(id: 's2', title: '文件2'),
          makeSource(id: 's3', title: '文件3'),
          makeSource(id: 's4', title: '文件4'),
        ];
        await tester.pumpWidget(wrap(SourceReferencePanel(sources: sources)));

        // 仅展示前 2 条
        expect(find.text('文件1'), findsOneWidget);
        expect(find.text('文件2'), findsOneWidget);
        // 折叠的不显示
        expect(find.text('文件3'), findsNothing);
        expect(find.text('文件4'), findsNothing);
        // 展开按钮
        expect(find.textContaining('展开剩余'), findsOneWidget);
        expect(find.textContaining('2 条来源'), findsOneWidget);
      },
    );

    testWidgets(
      'tapping expand button reveals hidden sources',
      (tester) async {
        final sources = [
          makeSource(id: 's1', title: '文件1'),
          makeSource(id: 's2', title: '文件2'),
          makeSource(id: 's3', title: '文件3'),
        ];
        await tester.pumpWidget(wrap(SourceReferencePanel(sources: sources)));

        // 初始:文件3 不可见
        expect(find.text('文件3'), findsNothing);

        // 点击展开按钮
        await tester.tap(find.textContaining('展开剩余'));
        await tester.pump();

        // 展开:文件3 可见
        expect(find.text('文件3'), findsOneWidget);
      },
    );

    testWidgets(
      'NoSourcesHint shows hint text when sources list is empty',
      (tester) async {
        await tester.pumpWidget(wrap(const NoSourcesHint()));

        expect(
          find.textContaining('该问题暂无可靠资料'),
          findsOneWidget,
        );
        expect(
          find.textContaining('咨询辅导员或学院办公室'),
          findsOneWidget,
        );
      },
    );

    testWidgets('NoSourcesHint shows reason when provided', (tester) async {
      await tester.pumpWidget(wrap(const NoSourcesHint(reason: '知识库为空')));

      expect(
        find.textContaining('知识库为空'),
        findsOneWidget,
      );
    });
  });

  group('AnswerMetaBadge', () {
    ChatMessage makeMessage({
      AnswerMode answerMode = AnswerMode.mockDemo,
      EvidenceLevel evidenceLevel = EvidenceLevel.unknown,
      List<String> warnings = const [],
      String content = '这是一条 AI 回复。',
    }) {
      return ChatMessage(
        id: 'msg_test',
        sender: MessageSender.counselor,
        content: content,
        timestamp: DateTime(2024, 10, 15),
        answerMode: answerMode,
        evidenceLevel: evidenceLevel,
        warnings: warnings,
      );
    }

    testWidgets(
      'shows correct mode label for AnswerMode.mockDemo',
      (tester) async {
        await tester.pumpWidget(
          wrap(
            AnswerMetaBadge(
              message: makeMessage(answerMode: AnswerMode.mockDemo),
            ),
          ),
        );

        expect(find.text('Mock 演示模式'), findsOneWidget);
      },
    );

    testWidgets(
      'shows correct mode label for AnswerMode.userLlmRag',
      (tester) async {
        await tester.pumpWidget(
          wrap(
            AnswerMetaBadge(
              message: makeMessage(answerMode: AnswerMode.userLlmRag),
            ),
          ),
        );

        expect(find.text('用户知识库 · LLM RAG'), findsOneWidget);
      },
    );

    testWidgets(
      'shows correct mode label for AnswerMode.demoRetrievalSummary',
      (tester) async {
        await tester.pumpWidget(
          wrap(
            AnswerMetaBadge(
              message: makeMessage(answerMode: AnswerMode.demoRetrievalSummary),
            ),
          ),
        );

        expect(find.text('仿真知识库 · 检索摘要'), findsOneWidget);
      },
    );

    testWidgets(
      'shows correct mode label for AnswerMode.noKnowledge',
      (tester) async {
        await tester.pumpWidget(
          wrap(
            AnswerMetaBadge(
              message: makeMessage(answerMode: AnswerMode.noKnowledge),
            ),
          ),
        );

        expect(find.text('无知识库依据'), findsOneWidget);
      },
    );

    testWidgets(
      'shows evidence level label "依据较充分" for high',
      (tester) async {
        await tester.pumpWidget(
          wrap(
            AnswerMetaBadge(
              message: makeMessage(evidenceLevel: EvidenceLevel.high),
            ),
          ),
        );

        expect(find.text('依据较充分'), findsOneWidget);
      },
    );

    testWidgets(
      'shows evidence level label for medium',
      (tester) async {
        await tester.pumpWidget(
          wrap(
            AnswerMetaBadge(
              message: makeMessage(evidenceLevel: EvidenceLevel.medium),
            ),
          ),
        );

        expect(find.text('依据有限,建议核对原文'), findsOneWidget);
      },
    );

    testWidgets(
      'shows evidence level label for conflict',
      (tester) async {
        await tester.pumpWidget(
          wrap(
            AnswerMetaBadge(
              message: makeMessage(evidenceLevel: EvidenceLevel.conflict),
            ),
          ),
        );

        expect(
          find.text('资料存在冲突,需要人工确认'),
          findsOneWidget,
        );
      },
    );

    testWidgets('shows warnings when provided', (tester) async {
      await tester.pumpWidget(
        wrap(
          AnswerMetaBadge(
            message: makeMessage(
              warnings: ['该资料已过期,仅作历史参考'],
            ),
          ),
        ),
      );

      expect(find.text('该资料已过期,仅作历史参考'), findsOneWidget);
    });

    testWidgets(
      'is hidden when AnswerMode.unknown',
      (tester) async {
        await tester.pumpWidget(
          wrap(
            AnswerMetaBadge(
              message: makeMessage(answerMode: AnswerMode.unknown),
            ),
          ),
        );

        // 不应显示任何模式或证据文案
        expect(find.text('Mock 演示模式'), findsNothing);
        expect(find.text('依据较充分'), findsNothing);
        expect(find.text('无知识库依据'), findsNothing);
      },
    );

    testWidgets(
      'shows "根据回答创建待办" button when onAddToTasks provided',
      (tester) async {
        await tester.pumpWidget(
          wrap(
            AnswerMetaBadge(
              message: makeMessage(),
              onAddToTasks: () {},
            ),
          ),
        );

        expect(find.text('根据回答创建待办'), findsOneWidget);
      },
    );
  });
}
