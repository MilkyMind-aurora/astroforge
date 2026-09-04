# -*- coding: utf-8 -*-
"""WPD 图表提数精度验证：程序化生成已知曲线 → 提取 → 断言还原误差（Phase 3）。"""
from pathlib import Path

import chart_extractor
import cv2
import numpy as np

REPO_TESTS = Path(__file__).resolve().parent


def make_line_chart(path: Path) -> None:
    """生成已知映射的折线图：x 轴线像素[50,550]→数据[0,10]，y 轴线像素[350,50]→数据[0,5]。

    曲线数据空间为 y = 0.5x，终点 (10,5) 落在 y 轴顶端延长处（像素 (550,50)）。
    """
    img = np.full((400, 600, 3), 255, np.uint8)
    cv2.line(img, (50, 350), (550, 350), (0, 0, 0), 2)   # x 轴
    cv2.line(img, (50, 50), (50, 350), (0, 0, 0), 2)     # y 轴
    for px in range(50, 551):                            # 红色曲线（BGR=0,0,255）
        py = int(350 - 300 * (px - 50) / 500)
        cv2.circle(img, (px, py), 1, (0, 0, 255), -1)
    cv2.imwrite(str(path), img)


def test_extract_known_linear_curve(tmp_path: Path):
    chart = tmp_path / "line.png"
    make_line_chart(chart)
    result = chart_extractor.extract_curve(
        str(chart), {"x_min": 0, "x_max": 10, "y_min": 0, "y_max": 5})
    points = result["points"]
    assert result["note"] is None
    assert len(points) >= 300  # 500 像素列大部分有数据
    first_x, first_y = points[0]
    last_x, last_y = points[-1]
    assert abs(first_x) < 0.2 and abs(first_y) < 0.2      # 起点 ≈ (0, 0)
    assert abs(last_x - 10) < 0.2 and abs(last_y - 5) < 0.2  # 终点 ≈ (10, 5)
    # 线性 y=0.5x：中间点抽样验证
    for data_x, data_y in points[::50]:
        assert abs(data_y - 0.5 * data_x) < 0.15, f"偏离 y=0.5x: ({data_x},{data_y})"


def test_missing_axis_note(tmp_path: Path):
    chart = tmp_path / "line.png"
    make_line_chart(chart)
    result = chart_extractor.extract_curve(str(chart))
    assert result["note"] and "归一化" in result["note"]
    # 归一化：首尾覆盖 0..1 区间
    xs = [p[0] for p in result["points"]]
    assert min(xs) < 0.05 and max(xs) > 0.95


def test_no_axis_image_rejected(tmp_path: Path):
    blank = tmp_path / "blank.png"
    cv2.imwrite(str(blank), np.full((200, 200, 3), 255, np.uint8))
    try:
        chart_extractor.extract_curve(str(blank))
        raise AssertionError("空白图应报未检测到坐标轴")
    except ValueError as exc:
        assert "坐标轴" in str(exc)


def test_nonexistent_image(tmp_path: Path):
    try:
        chart_extractor.extract_curve(str(tmp_path / "nope.png"))
        raise AssertionError("应抛 FileNotFoundError")
    except FileNotFoundError:
        pass
