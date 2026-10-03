# -*- coding: utf-8 -*-
"""
第六部分：AI 复盘

把统计分析结果、Top/Bottom 文章、标题特征，整理成一段结构化的提示词，
交给 AI 完成 10 项分析任务，并强制要求输出格式区分：
  【数据事实】【观察】【推测】【下一步实验】

调用 AI 的方式：
  - 若设置了环境变量 ANTHROPIC_API_KEY，则直接调用 Anthropic Messages API。
  - 否则只生成 ai_prompt.md，由用户手动粘贴到任意 AI（Claude 等）。
"""

import os
import json
import urllib.request

DEFAULT_MODEL = "claude-sonnet-5"


def build_prompt(metrics, quality, groups, title_summary, records):
    """
    构造 AI 提示词，返回字符串。

    提示词里会明确：
      - 样本量小（约几十篇），只能做「观察/假设」，不能下因果结论
      - 必须区分【数据事实】【观察】【推测】【下一步实验】
    """
    p = []
    p.append("# 你是内容数据分析师\n")
    p.append("请基于下面给出的「今日头条单篇作品数据」完成复盘。")
    p.append(f"样本量约 **{len(records)} 篇**，属于小样本，所有结论必须谨慎、留有余地，")
    p.append("严格区分【数据事实】【观察】【推测】【下一步实验】，")
    p.append("**绝不允许把相关关系说成因果关系**。\n")

    p.append("## 一、数据概况（数据事实）\n")
    p.append(f"文章数：{metrics.get('article_count')}，其中阅读量为 0 的有 {metrics.get('zero_reads_count')} 篇。\n")

    p.append("## 二、整体指标（mean / median / 分位数）\n")
    for key, label in [
        ("impressions", "展现量"), ("reads", "阅读量"), ("click_rate", "点击率"),
        ("completion_rate", "完成率"), ("interaction_rate", "互动率"),
        ("follow_rate", "涨粉率"),
    ]:
        d = metrics.get(key, {})
        p.append(f"- {label}：count={d.get('count')}, mean={_r(d.get('mean'))}, "
                 f"median={_r(d.get('median'))}, p75={_r(d.get('p75'))}, "
                 f"p90={_r(d.get('p90'))}, max={_r(d.get('max'))}")
    p.append("")

    p.append("## 三、Top / Bottom 文章组\n")
    p.append(json.dumps(_compact_groups(groups), ensure_ascii=False, indent=1))
    p.append("")

    p.append("## 四、标题特征汇总（观察变量，非因果）\n")
    p.append(json.dumps(title_summary, ensure_ascii=False, indent=1))
    p.append("")

    p.append("## 五、你要完成的任务\n")
    p.append("1. 找出高表现文章的共同特征")
    p.append("2. 找出低表现文章的共同特征")
    p.append("3. 比较高表现与低表现标题的区别")
    p.append("4. 找出值得进一步验证的假设")
    p.append("5. 找出明显表现异常的文章")
    p.append("6. 分析「高展现但低点击」的文章")
    p.append("7. 分析「低展现但高点击」的文章")
    p.append("8. 分析「高点击但低完成率」的文章")
    p.append("9. 分析「高完成率但低展现」的文章")
    p.append("10. 给出下一轮内容实验建议\n")

    p.append("## 六、输出格式要求（务必遵守）\n")
    p.append("每个结论都要标上类型，例如：")
    p.append("- 【数据事实】——只陈述数字，不加解读")
    p.append("- 【观察】——对样本的描述性发现")
    p.append("- 【推测】——带不确定性的猜想")
    p.append("- 【下一步实验】——可验证的具体做法")
    p.append("禁止使用「一定、必然、证明、导致」等因果措辞；")
    p.append("应使用「当前样本中…比例较高、值得验证、不足以证明因果关系」等谨慎表述。\n")

    return "\n".join(p)


def call_ai(prompt, model=None):
    """
    调用 Anthropic Messages API（若设置了 ANTHROPIC_API_KEY）。
    未设置则返回 None。
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    model = model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
    body = {
        "model": model,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    except Exception as e:  # noqa: BLE001
        return f"[AI 调用失败：{e}]"


def _r(x):
    """数值格式化，None 显示 '—'。"""
    if x is None:
        return "—"
    if isinstance(x, float):
        return round(x, 2)
    return x


def _compact_groups(groups):
    """把对比组精简成 AI 友好的结构（去掉冗余字段）。"""
    keep = ["title", "publish_time", "impressions", "reads", "click_rate",
            "completion_rate", "avg_read_time", "likes", "comments", "shares", "favorites"]
    out = {}
    for name, rows in groups.items():
        out[name] = [{k: r.get(k) for k in keep} for r in rows]
    return out
