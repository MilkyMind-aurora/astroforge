# -*- coding: utf-8 -*-
"""WPD 图表数值提取核心算法（Phase 3，方案 3.3.2）。

思路参考 WebPlotDigitizer（third_party/WebPlotDigitizer，AGPL-3.0，仅参考
算法不复制代码），自研实现三步：
1. detect_plot_area：霍夫直线找最长水平/垂直线 → 绘图区边界（x 轴/y 轴）
2. extract_series：绘图区内按目标色（默认取最大饱和色簇）逐列扫描取均值 y
3. calibrate：像素坐标 → 数据坐标线性映射（需 axis_config；缺省输出 0-1
   归一化并在结果中提示需手动修正，方案允许手动配置坐标轴参数）

若纯 Python 速度瓶颈，按方案预留 Rust 重写（模式 A：.pyd/.so）。
"""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def detect_plot_area(image: np.ndarray) -> dict[str, tuple[int, int, int, int]] | None:
    """定位坐标轴。

    返回 {"area": 绘图区(扫描用), "x_px": (左,右) 数据 x 的像素边界（x 轴端点）,
    "y_px": (顶,底) 数据 y 的像素边界（y 轴端点）}；找不到轴返回 None。
    标定用轴线端点而非图像边缘——轴线通常恰好画满数据范围。
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # 黑色轴线：低阈值二值 + 形态学提长直线
    binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)[1]
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(20, image.shape[1] // 4), 1)))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(20, image.shape[0] // 4))))

    def _longest_line(mask: np.ndarray) -> tuple[int, int, int, int] | None:
        lines = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=80,
                                minLineLength=min(mask.shape) // 3, maxLineGap=4)
        if lines is None:
            return None
        best, best_len = None, 0
        for x1, y1, x2, y2 in lines.reshape(-1, 4):  # 兼容 (N,1,4)/(N,4) 两种 shape
            length = (int(x2) - int(x1)) ** 2 + (int(y2) - int(y1)) ** 2
            if length > best_len:
                best, best_len = (int(x1), int(y1), int(x2), int(y2)), length
        return best

    h_line = _longest_line(horizontal)  # x 轴
    v_line = _longest_line(vertical)    # y 轴
    if h_line is None or v_line is None:
        return None
    x_axis_y = (h_line[1] + h_line[3]) // 2
    y_axis_x = (v_line[0] + v_line[2]) // 2
    return {
        # 扫描区：y 轴右侧、x 轴上方，延伸到图像边缘
        "area": (y_axis_x + 1, 1, image.shape[1] - 1, x_axis_y - 1),
        # 标定边界：x 轴线横向端点、y 轴线纵向端点
        "x_px": (min(h_line[0], h_line[2]), max(h_line[0], h_line[2])),
        "y_px": (min(v_line[1], v_line[3]), max(v_line[1], v_line[3])),
    }


def _dominant_series_color(image: np.ndarray, area: tuple[int, int, int, int]) -> tuple[int, int, int]:
    """绘图区内最大饱和色簇的均值 BGR（自动认曲线颜色）。"""
    x0, y0, x1, y1 = area
    roi = image[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # 饱和度>60 且非纯黑白：排除轴线/文字/背景（V 上限 255 保留纯色）
    mask = cv2.inRange(hsv, (0, 60, 40), (180, 255, 255))
    pixels = roi[mask > 0]
    if len(pixels) == 0:
        raise ValueError("绘图区内未检测到彩色数据系列（可能为灰度图或无数据）")
    return tuple(int(v) for v in pixels.mean(axis=0))  # type: ignore[return-value]


def extract_series(image: np.ndarray, area: tuple[int, int, int, int],
                   color_bgr: tuple[int, int, int] | None = None,
                   color_tolerance: int = 60) -> list[tuple[int, int]]:
    """逐列扫描：目标色像素的 x 列 → 均值 y，输出像素坐标序列（按 x 升序）。"""
    x0, y0, x1, y1 = area
    roi = image[y0:y1, x0:x1]
    if color_bgr is None:
        color_bgr = _dominant_series_color(image, area)
    color = np.array(color_bgr, dtype=np.int32)
    # 色距阈值匹配（欧氏距离），比 HSV 阈值对具体曲线更稳；int32 防 255² 溢出
    distance = np.sqrt(((roi.astype(np.int32) - color.reshape(1, 1, 3)) ** 2).sum(axis=2))
    mask = distance < color_tolerance
    points: list[tuple[int, int]] = []
    for col in range(roi.shape[1]):
        rows = np.nonzero(mask[:, col])[0]
        if len(rows):
            points.append((x0 + col, y0 + int(rows.mean())))
    return points


def calibrate(points_px: list[tuple[int, int]], bounds: dict[str, tuple[int, int, int, int]],
              axis: dict[str, float] | None) -> dict[str, Any]:
    """像素坐标 → 数据坐标。

    axis = {"x_min","x_max","y_min","y_max"}：映射到轴线端点边界
    （约定 x_min 在 y 轴处、y_max 在 y 轴顶端）。缺省输出 0-1 归一化。
    """
    (px_x_min, px_x_max) = bounds["x_px"]
    (px_y_min, px_y_max) = bounds["y_px"]
    width = max(1, px_x_max - px_x_min)
    height = max(1, px_y_max - px_y_min)
    if axis and all(k in axis for k in ("x_min", "x_max", "y_min", "y_max")):
        x_min, x_max = float(axis["x_min"]), float(axis["x_max"])
        y_min, y_max = float(axis["y_min"]), float(axis["y_max"])
        note = None
    else:
        x_min, x_max, y_min, y_max = 0.0, 1.0, 0.0, 1.0
        note = "未提供坐标轴范围，输出为 0-1 归一化坐标（请手动配置 axis 修正）"
    data = []
    for cur_x, cur_y in points_px:
        data_x = x_min + (cur_x - px_x_min) / width * (x_max - x_min)
        # 图像 y 向下：像素越小数据越大
        data_y = y_min + (px_y_max - cur_y) / height * (y_max - y_min)
        data.append((round(data_x, 6), round(data_y, 6)))
    return {"points": data, "note": note}


def extract_curve(image_path: str, axis_config: dict[str, float] | None = None) -> dict[str, Any]:
    """入口：读图 → 轴检测 → 系列提取 → 标定。各步骤异常如实上抛由 CLI 归类。"""
    # cv2.imread 不支持非 ASCII 路径（Windows），用 fromfile+imdecode 兜底
    data = np.fromfile(image_path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"无法读取图片: {image_path}")
    bounds = detect_plot_area(image)
    if bounds is None:
        raise ValueError("未检测到坐标轴（无法定位绘图区）")
    points_px = extract_series(image, bounds["area"])
    if len(points_px) < 2:
        raise ValueError("数据点过少（<2），无法构成曲线")
    result = calibrate(points_px, bounds, axis_config)
    return {"points": result["points"], "note": result["note"],
            "pixel_count": len(points_px),
            "area": list(bounds["area"])}
