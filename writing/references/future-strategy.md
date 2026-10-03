# 未来数据闭环接口与模块边界（V0.4 预留，暂不实现）

> 本文件只**预留接口与边界**，V0.4 不实现复杂功能。
> 当前没有历史文章正文数据，因此本文件里的规则**一律不作为当前写作规则**。

---

## 一、future_strategy_context 接口 schema

未来「写作 Skill」应能接收一个可选的上下文对象：

```json
{
  "validated_rules": [],
  "hypotheses": [],
  "experiments": [],
  "avoid_patterns": []
}
```

- `validated_rules`：**只有经过真实数据验证的规则**才能进入这里，会被当作写作约束。
- `hypotheses`：AI 自己**猜出来、尚未验证**的规则，只能放这里，**不能直接成为永久写作规则**。
- `experiments`：正在进行的实验（如"本批 10 篇标题统一带具体数字"）。
- `avoid_patterns`：已被数据证伪、应当避免的写法。

**当前行为**：`future_strategy_context` 为空 → 正常写作，不附加任何未经验证的约束。

---

## 二、三个模块的职责边界

| 模块 | 负责 | 不负责 |
|---|---|---|
| A. Writing Skill | 选题、标题、正文、初稿 | 判断自己的效果 |
| B. Data Collector | 采集发布后的真实数据（展现/阅读/CTR/点赞/评论/转发/收藏/涨粉/完读率/时长…） | 写作 |
| C. Review / Strategy Agent | 分析数据、发现模式、提出假设、设计实验、验证策略 | 在没有数据时把猜测写成规则 |

**Writing QA 是 A 和 C 之间的质量控制层**，闭环如下：

```
Writing Skill → Writing QA → Publish → Data Collector → Review Agent → Validated Strategy → Writing Skill
```

三条硬边界：

1. **不要让 Data Collector 负责写作。**
2. **不要让 Writing Skill 自己判断自己的效果。**
3. **不要让 Review Agent 在没有数据的情况下把猜测写成规则。**

---

## 三、未来对接方式（仅说明，不实现）

- 当 `Data Collector` + `Review Agent` 产出经过验证的结论后，把它们写入 `future_strategy_context` 的 `validated_rules` / `avoid_patterns`。
- 写作 Skill 在「选题 / 标题 / 正文」各步读取 `validated_rules` 与 `avoid_patterns`，作为约束注入。
- 未经验证的 AI 猜测只进入 `hypotheses`，仅作为参考，**不约束写作**。
