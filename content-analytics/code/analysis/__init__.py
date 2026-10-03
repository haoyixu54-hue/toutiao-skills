# -*- coding: utf-8 -*-
"""
分析模块（V0.3：AI 内容数据复盘）

子模块：
  data_quality   第一部分：数据清洗 / 数据质检
  metrics        第二部分：建立基础指标（mean/median/分位数 + 互动率/涨粉率）
  tiering        第三部分：文章表现分层（分位数分层 + 综合表现）
  compare        第四部分：生成对比数据（Top/Bottom 10%）
  title_features 第五部分：标题分析（特征提取，仅观察变量）
  ai_review      第六部分：AI 复盘（构造提示词 + 可选调用 AI）
  report         第七部分：生成复盘报告（Markdown）
  utils          共享工具（百分位数 / 读取数据等）

未来扩展（V1.0）：
  将新增 article_content（文章正文）字段，
  届时在 title_features 之外增加正文分析，实现「标题+正文+图片+数据表现」的多维复盘。
"""
