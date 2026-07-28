"""基准测试子包：单张 CPU 推理延迟、参数量、模型文件大小。"""

from .benchmark import run_benchmark

__all__ = ["run_benchmark"]
