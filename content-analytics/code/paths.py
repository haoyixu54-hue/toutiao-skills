# -*- coding: utf-8 -*-
"""
================================================================================
统一数据目录（Single Source of Truth）
================================================================================

Content Analytics 的「采集输出」与「分析输入」共用同一个目录，
彻底消除「output/ -> 手动复制 -> 数据目录/」这种中间搬运。

可移植设计：
  - 优先读取环境变量 TOUTIAO_DATA_DIR
  - 未设置时，默认用本文件同级的 data/ 目录（换机器克隆后无需改代码即可用）

  DATA_DIR      统一数据目录（采集输出 = 分析输入）
  ANALYSIS_DIR  分析中间结果子目录（metrics.json / tiering.json / advanced.json ...）
================================================================================
"""
import os

# 环境变量优先；本机要继续用旧数据目录，可设：TOUTIAO_DATA_DIR=E:/toutiao_data
DATA_DIR = os.environ.get("TOUTIAO_DATA_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data"
)

# 分析中间结果子目录
ANALYSIS_DIR = os.path.join(DATA_DIR, "analysis")

# 采集结果文件名（三个扩展名由 data_storage.save_all 统一生成）
BATCH_BASENAME = "batch_result"
