"""WPD 核心算法骨架（Phase 3 实现）。

extract_curve(image_path, axis_config) -> list[(x, y)]
    输入：图表图片路径；axis_config: {"x_min","x_max","y_min","y_max","log_scale"}
    输出：像素颜色聚类 + 坐标轴标定后的数值点序列
    若纯 Python 速度瓶颈，按方案预留 Rust 重写（模式 A：.pyd/.so）
"""
from __future__ import annotations


def extract_curve(image_path: str, axis_config: dict) -> list[tuple[float, float]]:
    raise NotImplementedError("Phase 3：OpenCV 颜色聚类 + 坐标标定 + 曲线追踪")
