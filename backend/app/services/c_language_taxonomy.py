from __future__ import annotations


C_TAXONOMY_VERSION = "c-language-v1"

# Stable, reviewable taxonomy. Names are display labels only; no student text is stored here.
C_LANGUAGE_KNOWLEDGE_COMPONENTS = [
    ("c.program.structure", "程序结构", "foundations"),
    ("c.preprocessor", "预处理与头文件", "foundations"),
    ("c.compiler.toolchain", "编译与链接流程", "foundations"),
    ("c.variables", "变量与标识符", "types"),
    ("c.constants", "常量与字面量", "types"),
    ("c.integer.types", "整数类型", "types"),
    ("c.floating.types", "浮点类型", "types"),
    ("c.char.types", "字符与字符串类型", "types"),
    ("c.type_conversion", "类型转换", "types"),
    ("c.operators.arithmetic", "算术运算符", "expressions"),
    ("c.operators.logical", "逻辑与关系运算符", "expressions"),
    ("c.operators.bitwise", "位运算符", "expressions"),
    ("c.expressions.precedence", "表达式求值与优先级", "expressions"),
    ("c.control.if", "条件分支", "control"),
    ("c.control.switch", "switch 分支", "control"),
    ("c.control.loop", "循环结构", "control"),
    ("c.control.loop_termination", "循环终止条件", "control"),
    ("c.control.nested", "嵌套控制结构", "control"),
    ("c.functions.declaration", "函数声明与定义", "functions"),
    ("c.functions.parameters", "函数参数与返回值", "functions"),
    ("c.functions.recursion", "递归函数", "functions"),
    ("c.scope.lifetime", "作用域与生命周期", "functions"),
    ("c.arrays.one_dimensional", "一维数组", "arrays"),
    ("c.array.boundaries", "数组边界", "arrays"),
    ("c.arrays.multidimensional", "多维数组", "arrays"),
    ("c.strings", "字符串处理", "arrays"),
    ("c.pointer.basics", "指针基础", "pointers"),
    ("c.pointer.indirection", "指针解引用", "pointers"),
    ("c.pointer.arithmetic", "指针运算", "pointers"),
    ("c.pointer.array_relation", "指针与数组关系", "pointers"),
    ("c.pointer.function", "函数指针", "pointers"),
    ("c.memory.dynamic_lifecycle", "动态内存生命周期", "memory"),
    ("c.memory.allocation", "内存分配与释放", "memory"),
    ("c.structs", "结构体", "composite"),
    ("c.unions_enums", "共用体与枚举", "composite"),
    ("c.file.open_close", "文件打开与关闭", "io"),
    ("c.file.read_write", "文件读写", "io"),
    ("c.file_errors", "文件错误处理", "io"),
    ("c.debugging", "调试与测试思维", "practice"),
]


def taxonomy_definitions() -> list[dict]:
    return [
        {
            "id": f"kc_{index:03d}", "code": code, "name": name, "category": category,
            "description": f"C 语言 {name} 的可评价基础概念", "domain": "c_language",
            "active": True, "parent_code": None,
            "taxonomy_version": C_TAXONOMY_VERSION, "sort_order": index,
            "prerequisite_codes": [],
        }
        for index, (code, name, category) in enumerate(C_LANGUAGE_KNOWLEDGE_COMPONENTS, start=1)
    ]


__all__ = ["C_LANGUAGE_KNOWLEDGE_COMPONENTS", "C_TAXONOMY_VERSION", "taxonomy_definitions"]
