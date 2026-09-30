# 个人考试安排

> 对照日期：2026-09-30。本模块共 4 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/student/exams` | 列出考试 |
| POST | `/api/v1/student/exams` | 创建考试 |
| PATCH | `/api/v1/student/exams/{exam_id}` | 更新考试 |
| DELETE | `/api/v1/student/exams/{exam_id}` | 删除考试 |

## 接口契约

### `GET /api/v1/student/exams`

用途：列出考试。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/student_tools.py](../../backend/app/api/routes/student_tools.py)，`list_exams`。

Web 封装：`getExams`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

响应直接来自 student_exams 行；详见 [实际响应补充](response-contracts.md#exams)。PATCH 也要求 course_name 和 exam_date，不能只发送一个字段。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
[dict(row) for row in rows]
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/student/exams`

用途：创建考试。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/student_tools.py](../../backend/app/api/routes/student_tools.py)，`create_exam`。

Web 封装：`saveExam`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

响应直接来自 student_exams 行；详见 [实际响应补充](response-contracts.md#exams)。PATCH 也要求 course_name 和 exam_date，不能只发送一个字段。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[ExamIn](schemas.md#schema-examin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_name` | string | 是 | minLength=1; maxLength=200 | — |
| `exam_date` | string | 是 | minLength=1; maxLength=32 | — |
| `start_time` | string / null | 否 | string约束: maxLength=16 | — |
| `end_time` | string / null | 否 | string约束: maxLength=16 | — |
| `location` | string / null | 否 | string约束: maxLength=200 | — |
| `seat_number` | string / null | 否 | string约束: maxLength=32 | — |
| `exam_type` | string / null | 否 | string约束: maxLength=64 | — |
| `reminder_enabled` | boolean | 否 | default=true | — |
| `notes` | string / null | 否 | string约束: maxLength=2000 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "course_name": "<course_name>",
  "exam_date": "<exam_date>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
dict(row)
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `PATCH /api/v1/student/exams/{exam_id}`

用途：更新考试。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/student_tools.py](../../backend/app/api/routes/student_tools.py)，`update_exam`。

Web 封装：`saveExam`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

响应直接来自 student_exams 行；详见 [实际响应补充](response-contracts.md#exams)。PATCH 也要求 course_name 和 exam_date，不能只发送一个字段。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `exam_id` | string | 是 | — | — |

请求体：`application/json`，必填；[ExamIn](schemas.md#schema-examin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_name` | string | 是 | minLength=1; maxLength=200 | — |
| `exam_date` | string | 是 | minLength=1; maxLength=32 | — |
| `start_time` | string / null | 否 | string约束: maxLength=16 | — |
| `end_time` | string / null | 否 | string约束: maxLength=16 | — |
| `location` | string / null | 否 | string约束: maxLength=200 | — |
| `seat_number` | string / null | 否 | string约束: maxLength=32 | — |
| `exam_type` | string / null | 否 | string约束: maxLength=64 | — |
| `reminder_enabled` | boolean | 否 | default=true | — |
| `notes` | string / null | 否 | string约束: maxLength=2000 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "course_name": "<course_name>",
  "exam_date": "<exam_date>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
dict(conn.execute('SELECT * FROM student_exams WHERE id = ?', (exam_id,)).fetchone())
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | HTTPException | '考试记录不存在' |

### `DELETE /api/v1/student/exams/{exam_id}`

用途：删除考试。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/student_tools.py](../../backend/app/api/routes/student_tools.py)，`delete_exam`。

Web 封装：`deleteExam`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

响应直接来自 student_exams 行；详见 [实际响应补充](response-contracts.md#exams)。PATCH 也要求 course_name 和 exam_date，不能只发送一个字段。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `exam_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。
