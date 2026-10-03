# -*- coding: utf-8 -*-
"""
第五部分：标题分析

目前只有标题，先做标题层面的特征提取（第一版）。
所有特征都只是「观察变量」，只能用于发现相关现象，
绝不能直接推出「某个特征导致流量高」的因果结论。

提取的特征：
  - title_len        标题长度（字符数）
  - has_number       是否包含数字
  - number_count     数字片段数量
  - has_question     是否包含问号（？/ ?）
  - has_exclamation  是否包含感叹号（！/ !）
  - has_person       是否包含人物姓名
  - person_count     出现的人物数量
  - multi_person     是否出现多个人物
  - has_why          「为什么」
  - has_caifaxian    「才发现」
  - has_meirenzhidao 「没人知道」
  - has_quanwang     「全网」
  - has_zhenxiang    「真相」
  - has_que          「却」
  - has_dan          「但」
  - has_fanwen       反问（问号 + 反问语气词，启发式）
  - has_conflict     冲突/反转结构（转折词，启发式）
  - has_num_info     时间/年龄/数量信息（数字 + 单位，启发式）
"""

import re

# 人物姓名库（娱乐类内容常用；可在此扩充。仅作观察变量，人名识别是启发式的）
KNOWN_NAMES = [
    "鹿晗", "关晓彤", "谢娜", "王菲", "谢霆锋", "张柏芝", "韩红", "贾玲", "杨紫", "陈露",
    "黄一鸣", "迪丽热巴", "杜海涛", "张雨绮", "白鹿", "于正", "严浩翔", "杨超越", "李晨",
    "陈妍希", "陈晓", "韩栋", "王力宏", "王鹤棣", "田震", "那英", "何猷君", "肖旭", "释永信",
    "杨颖", "董明珠", "汪涵", "窦骁", "何超莲", "刘宇婕", "宁泽涛", "沙溢", "王健林", "王思聪",
    "张艺谋", "郑伊健", "陈浩南", "王晶", "周也", "董洁", "杨幂", "赵丽颖", "庾澄庆", "伊能静",
    "沈月", "景甜", "白冰", "黄圣依", "杨子", "王菲", "鹿晗", "关晓彤", "特朗普", "汪小菲",
    "大S", "小S", "何炅", "黄磊", "林志玲", "刘德华", "周杰伦", "邓超", "孙俪", "杨幂",
]

# 反问语气词
FANWEN_WORDS = ["谁", "什么", "怎么", "为何", "难道", "到底", "凭什么", "还能", "如何",
                "为什么", "是不是", "吗", "哪", "何"]

# 冲突/反转结构词
CONFLICT_WORDS = ["却", "但", "然而", "没想到", "原来", "才发现", "反而", "竟然", "居然",
                  "偏偏", "反转", "翻车", "打脸", "真相", "背后", "没人知道", "含金量",
                  "差距", "双标", "致命", "炸裂", "破防"]

# 时间/年龄/数量单位
NUM_INFO_UNITS = ["岁", "年", "天", "月", "日", "亿", "万", "次", "个", "条", "分", "秒",
                  "元", "张", "笔", "部", "场", "杯", "美金", "套", "级", "倍", "斤", "小时"]


def extract_title_features(title):
    """提取单条标题的特征，返回 dict。"""
    f = {}
    t = title or ""
    f["title_len"] = len(t)
    f["has_number"] = bool(re.search(r"\d", t))
    f["number_count"] = len(re.findall(r"\d+(?:\.\d+)?", t))
    f["has_question"] = bool(re.search(r"[？?]", t))
    f["has_exclamation"] = bool(re.search(r"[！!]", t))

    # 人物：命中姓名库
    persons = [name for name in KNOWN_NAMES if name in t]
    f["has_person"] = bool(persons)
    f["person_count"] = len(persons)
    f["multi_person"] = len(persons) >= 2

    # 关键词
    f["has_why"] = "为什么" in t
    f["has_caifaxian"] = "才发现" in t
    f["has_meirenzhidao"] = "没人知道" in t
    f["has_quanwang"] = "全网" in t
    f["has_zhenxiang"] = "真相" in t
    f["has_que"] = "却" in t
    f["has_dan"] = "但" in t

    # 反问（启发式）：有问号 且 含反问语气词
    f["has_fanwen"] = f["has_question"] and any(w in t for w in FANWEN_WORDS)

    # 冲突结构（启发式）：含转折/反转词
    f["has_conflict"] = any(w in t for w in CONFLICT_WORDS)

    # 时间/年龄/数量信息（启发式）：数字 + 单位
    f["has_num_info"] = bool(re.search(r"\d+\s*(?:%s)" % "|".join(NUM_INFO_UNITS), t))

    return f


def extract_all(records):
    """给每篇记录追加标题特征字段，返回 (记录副本, 特征清单)。"""
    recs = [dict(r) for r in records]
    feat_keys = None
    for r in recs:
        f = extract_title_features(r.get("title"))
        if feat_keys is None:
            feat_keys = list(f.keys())
        r.update({f"title_{k}": v for k, v in f.items()})
    return recs, feat_keys


def summarize(records):
    """
    汇总标题特征：每个特征的出现次数 / 占比（按「全样本」和「按阅读分层」两个视角）。
    返回 dict 供报告和 AI 使用。
    """
    all_recs = records
    n = len(all_recs)

    # 阅读量中位数，用于「高阅读 / 低阅读」粗分（观察用，非因果）
    reads_sorted = sorted([r.get("reads") or 0 for r in all_recs])
    if reads_sorted:
        med = reads_sorted[len(reads_sorted) // 2]
    else:
        med = 0
    high_reads = [r for r in all_recs if (r.get("reads") or 0) > med]
    low_reads = [r for r in all_recs if (r.get("reads") or 0) <= med]

    feat_keys = None
    tmp = {}
    for r in all_recs:
        f = extract_title_features(r.get("title"))
        if feat_keys is None:
            feat_keys = list(f.keys())
        tmp[id(r)] = f

    summary = {"n": n, "read_median": med,
               "high_reads_n": len(high_reads), "low_reads_n": len(low_reads)}

    # 布尔特征按 True 计数；数值特征（title_len/number_count/person_count）给均值
    bool_keys = {k for k in feat_keys
                 if isinstance(tmp[id(all_recs[0])][k], bool)} if all_recs else set()

    for k in feat_keys:
        if k in bool_keys:
            hi_cnt = sum(1 for r in high_reads if tmp[id(r)][k])
            lo_cnt = sum(1 for r in low_reads if tmp[id(r)][k])
            all_cnt = hi_cnt + lo_cnt
            summary[k] = {
                "all": all_cnt, "all_pct": round(all_cnt / n * 100, 1) if n else 0,
                "high": hi_cnt, "low": lo_cnt,
                "high_pct": round(hi_cnt / len(high_reads) * 100, 1) if high_reads else 0,
                "low_pct": round(lo_cnt / len(low_reads) * 100, 1) if low_reads else 0,
            }
        else:
            # 数值特征：给出全样本均值
            vals = [tmp[id(r)][k] for r in all_recs if tmp[id(r)][k] is not None]
            summary[k] = {"mean": round(sum(vals) / len(vals), 2) if vals else None}

    return summary


def render_summary(summary):
    """把标题特征汇总渲染成 Markdown 表格（布尔特征）。"""
    L = []
    L.append("| 特征 | 全样本出现 | 全样本占比 | 高阅读出现 | 高阅读占比 | 低阅读占比 |")
    L.append("|---|---|---|---|---|---|")
    for k, v in summary.items():
        if k in ("n", "read_median", "high_reads_n", "low_reads_n"):
            continue
        if "all_pct" not in v:
            # 数值特征
            if "mean" in v:
                L.append(f"| {k}（数值均值） | — | — | — | — | — | 均值 {v['mean']} |")
            continue
        L.append(
            f"| {k} | {v['all']} | {v['all_pct']}% | {v['high']} | {v['high_pct']}% | {v['low_pct']}% |"
        )
    return "\n".join(L)
