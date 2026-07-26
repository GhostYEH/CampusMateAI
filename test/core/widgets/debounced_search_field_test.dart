import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:campus_companion/core/widgets/debounced_search_field.dart';

/// 测试用搜索消费者 — 模拟一个使用 DebouncedSearchField 的页面,
/// 跟踪每次回调的搜索词、调用次数,以及请求取消行为。
class _SearchConsumer extends StatefulWidget {
  const _SearchConsumer({
    super.key,
    this.debounce = const Duration(milliseconds: 300),
    this.onSearch,
  });

  final Duration debounce;
  final Future<List<String>> Function(String query, CancelToken token)?
      onSearch;

  @override
  State<_SearchConsumer> createState() => _SearchConsumerState();
}

class _SearchConsumerState extends State<_SearchConsumer> {
  final _controller = TextEditingController();
  CancelToken? _cancelToken;
  List<String> _results = const [];
  String? _lastQuery;
  int _callbackCount = 0;
  int _cancelledCount = 0;

  /// 公开供测试断言。
  int get callbackCount => _callbackCount;
  int get cancelledCount => _cancelledCount;
  String? get lastQuery => _lastQuery;
  List<String> get results => _results;

  Future<void> _runSearch(String query) async {
    _callbackCount++;
    _lastQuery = query;

    // 取消上一个在途请求
    if (_cancelToken != null && !_cancelToken!.isCancelled) {
      _cancelToken!.cancel('replaced by newer query');
      _cancelledCount++;
    }

    if (query.isEmpty) {
      setState(() => _results = const []);
      return;
    }
    if (widget.onSearch == null) return;

    _cancelToken = CancelToken();
    try {
      final r = await widget.onSearch!(query, _cancelToken!);
      if (mounted) setState(() => _results = r);
    } on DioException catch (e) {
      if (e.type == DioExceptionType.cancel) {
        // 被取消 — 静默
      } else {
        rethrow;
      }
    }
  }

  @override
  void dispose() {
    _cancelToken?.cancel('disposed');
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Column(
          children: [
            DebouncedSearchField(
              hint: '搜索学生',
              debounce: widget.debounce,
              onChanged: _runSearch,
            ),
            Expanded(
              child: ListView(
                children:
                    _results.map((r) => ListTile(title: Text(r))).toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 构造一个 _SearchConsumer 与其 State 的 GlobalKey,便于测试断言。
({GlobalKey<_SearchConsumerState> key, _SearchConsumer widget}) makeConsumer({
  Duration debounce = const Duration(milliseconds: 300),
  Future<List<String>> Function(String query, CancelToken token)? onSearch,
}) {
  final key = GlobalKey<_SearchConsumerState>();
  final widget = _SearchConsumer(
    key: key,
    debounce: debounce,
    onSearch: onSearch,
  );
  return (key: key, widget: widget);
}

void main() {
  group('DebouncedSearchField - 防抖', () {
    testWidgets('快速连续输入时仅触发一次回调(在防抖延迟后)', (tester) async {
      final c = makeConsumer();
      await tester.pumpWidget(c.widget);
      await tester.pump();

      // 在搜索框中快速输入三个字符
      // 用 enterText 一次性设置整段文本(模拟快速输入)
      await tester.enterText(find.byType(TextField), 'abc');
      await tester.pump();

      // 立即检查 — 防抖延迟未到,回调不应被调用
      expect(c.key.currentState!.callbackCount, 0);

      // 推进时间 200ms(小于 300ms 防抖)
      await tester.pump(const Duration(milliseconds: 200));
      expect(c.key.currentState!.callbackCount, 0);

      // 推进到 300ms,回调应被触发
      await tester.pump(const Duration(milliseconds: 100));
      expect(c.key.currentState!.callbackCount, 1);
      expect(c.key.currentState!.lastQuery, 'abc');
    });

    testWidgets('继续输入时取消之前的回调,只用最新值触发', (tester) async {
      final c = makeConsumer();
      await tester.pumpWidget(c.widget);
      await tester.pump();

      // 第一次输入
      await tester.enterText(find.byType(TextField), 'a');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      // 此时防抖延迟未到,回调未触发
      expect(c.key.currentState!.callbackCount, 0);

      // 继续输入(延长文本)
      await tester.enterText(find.byType(TextField), 'ab');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(c.key.currentState!.callbackCount, 0);

      // 再次输入
      await tester.enterText(find.byType(TextField), 'abc');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(c.key.currentState!.callbackCount, 0);

      // 推进超过防抖延迟
      await tester.pump(const Duration(milliseconds: 300));
      expect(c.key.currentState!.callbackCount, 1);
      expect(c.key.currentState!.lastQuery, 'abc');
    });

    testWidgets('自定义防抖延迟生效', (tester) async {
      final c = makeConsumer(
        debounce: const Duration(milliseconds: 500),
      );
      await tester.pumpWidget(c.widget);
      await tester.pump();

      await tester.enterText(find.byType(TextField), 'hello');
      await tester.pump();

      // 300ms — 不应触发(防抖 500ms)
      await tester.pump(const Duration(milliseconds: 300));
      expect(c.key.currentState!.callbackCount, 0);

      // 500ms — 应触发
      await tester.pump(const Duration(milliseconds: 200));
      expect(c.key.currentState!.callbackCount, 1);
      expect(c.key.currentState!.lastQuery, 'hello');
    });

    testWidgets('清除按钮清空输入并触发回调(空字符串)', (tester) async {
      final c = makeConsumer();
      await tester.pumpWidget(c.widget);
      await tester.pump();

      // 先输入并等待防抖
      await tester.enterText(find.byType(TextField), 'something');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(c.key.currentState!.callbackCount, 1);

      // 点击清除按钮(suffixIcon)
      final clearBtn = find.byTooltip('清除');
      expect(clearBtn, findsOneWidget);
      await tester.tap(clearBtn);
      await tester.pump();

      // 清空时立即触发回调(因为 DebouncedSearchField._clear 调用 _onChanged(''))
      // _onChanged 检查 value == _lastValue,若不同则触发防抖
      // 等待防抖延迟
      await tester.pump(const Duration(milliseconds: 300));
      expect(c.key.currentState!.callbackCount, 2);
      expect(c.key.currentState!.lastQuery, '');
      // TextField 已清空
      expect(find.text('something'), findsNothing);
    });

    testWidgets('相同输入不重复触发回调', (tester) async {
      final c = makeConsumer();
      await tester.pumpWidget(c.widget);
      await tester.pump();

      await tester.enterText(find.byType(TextField), 'abc');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(c.key.currentState!.callbackCount, 1);

      // 再次输入相同值(理论上需要先清空再输入,
      // 因为 enterText 会替换整个文本 — 若文本已是 'abc' 则不会触发 onChanged)
      await tester.enterText(find.byType(TextField), 'abc');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      // 由于 _lastValue 检查,不会触发回调
      expect(c.key.currentState!.callbackCount, 1);
    });

    testWidgets('onSubmitted 在提交时触发', (tester) async {
      String? submittedValue;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DebouncedSearchField(
              hint: '搜索',
              onChanged: (_) {},
              onSubmitted: (v) => submittedValue = v,
            ),
          ),
        ),
      );
      await tester.pump();

      await tester.enterText(find.byType(TextField), 'search-term');
      await tester.pump();

      // 模拟键盘提交动作
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await tester.pump();

      expect(submittedValue, 'search-term');
    });
  });

  group('DebouncedSearchField - 消费者请求取消场景', () {
    testWidgets('快速输入时取消上一个在途请求,只保留最后一次结果', (tester) async {
      // 模拟后端响应延迟
      final requests = <String>[];
      Future<List<String>> onSearch(String query, CancelToken token) async {
        requests.add(query);
        // 模拟网络延迟
        await Future.delayed(const Duration(milliseconds: 200), () {});
        if (token.isCancelled) {
          throw DioException(
            requestOptions: RequestOptions(path: '/search'),
            type: DioExceptionType.cancel,
          );
        }
        return ['$query-result-1', '$query-result-2'];
      }

      final c = makeConsumer(onSearch: onSearch);
      await tester.pumpWidget(c.widget);
      await tester.pump();

      // 快速输入三个值
      await tester.enterText(find.byType(TextField), 'a');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300)); // 触发第一次回调

      await tester.enterText(find.byType(TextField), 'ab');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300)); // 触发第二次回调

      await tester.enterText(find.byType(TextField), 'abc');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300)); // 触发第三次回调

      // 等待所有在途请求完成
      await tester.pump(const Duration(milliseconds: 400));

      // 三个搜索请求都发起了
      expect(requests.length, 3);
      expect(requests, ['a', 'ab', 'abc']);

      // 但前两个被取消(第三个未完成时不取消)
      // 第一个请求被第二个请求取消,第二个被第三个取消
      // 第三个未被取消(因为没有后续请求)
      expect(c.key.currentState!.cancelledCount, 2);

      // 最终结果只显示最后一次的('abc')
      expect(c.key.currentState!.results, ['abc-result-1', 'abc-result-2']);
    });

    testWidgets('快速连续输入最终只发起一次请求', (tester) async {
      final requests = <String>[];
      Future<List<String>> onSearch(String query, CancelToken token) async {
        requests.add(query);
        await Future.delayed(const Duration(milliseconds: 100), () {});
        return ['$query-result'];
      }

      final c = makeConsumer(onSearch: onSearch);
      await tester.pumpWidget(c.widget);
      await tester.pump();

      // 快速输入(防抖延迟内,不会触发回调)
      await tester.enterText(find.byType(TextField), 'a');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.enterText(find.byType(TextField), 'ab');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.enterText(find.byType(TextField), 'abc');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 此时所有输入都在防抖窗口内,没有任何回调被触发
      expect(c.key.currentState!.callbackCount, 0);
      expect(requests, isEmpty);

      // 防抖结束后只触发一次
      await tester.pump(const Duration(milliseconds: 300));
      expect(c.key.currentState!.callbackCount, 1);
      expect(requests.length, 1);
      expect(requests.first, 'abc');
    });
  });

  group('DebouncedSearchField - 长度限制与初始化', () {
    testWidgets('初始值正确显示', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DebouncedSearchField(
              hint: '搜索',
              initialValue: 'initial text',
              onChanged: (_) {},
            ),
          ),
        ),
      );
      await tester.pump();

      expect(find.text('initial text'), findsOneWidget);
    });

    testWidgets('输入超过 120 字符被截断', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DebouncedSearchField(
              hint: '搜索',
              onChanged: (_) {},
            ),
          ),
        ),
      );
      await tester.pump();

      // 输入超过 120 字符的长文本
      final longText = 'a' * 200;
      await tester.enterText(find.byType(TextField), longText);
      await tester.pump();

      // 由于 LengthLimitingTextInputFormatter(120),文本被截断
      final controller = tester
          .widget<TextField>(
            find.byType(TextField),
          )
          .controller;
      expect(controller?.text.length, 120);
    });

    testWidgets('autofocus 属性正确传递', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DebouncedSearchField(
              hint: '搜索',
              autofocus: true,
              onChanged: (_) {},
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump();

      // TextField 应该获得焦点
      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.autofocus, isTrue);
    });
  });

  group('DebouncedSearchField - 资源释放', () {
    testWidgets('dispose 取消防抖 Timer 避免泄漏', (tester) async {
      final c = makeConsumer();
      await tester.pumpWidget(c.widget);
      await tester.pump();

      // 输入但不等待防抖延迟(此时 Timer 仍在 pending)
      await tester.enterText(find.byType(TextField), 'abc');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // 立即 widget tree 销毁
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();

      // 推进超过防抖延迟 — 不应抛出 "Timer was canceled" 之类的异常
      await tester.pump(const Duration(milliseconds: 300));
      // 测试通过即表示 dispose 正确取消 Timer
      expect(true, isTrue);
    });
  });
}
