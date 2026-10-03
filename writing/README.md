# 今日头条娱乐爆文写作 Skill

一条命令安装，安装后在 Claude Code 输入 `/writing` 即可使用。

## 功能

- 热点事件自动采集 + 多方核实
- 5 种人设风格可选（毒舌犀利、温情吃瓜、侦探扒皮、阴阳怪气、理性数据派）
- 爆款标题生成（22-30 字，6 种公式）
- 正文撰写（加粗、分段、双路径结尾互动钩子）
- 百度/Bing 双引擎自动配图
- 水印智能检测 + 高斯模糊
- .docx 输出，按日期归档到桌面

## 一键安装

### Windows（PowerShell）
```powershell
irm https://raw.githubusercontent.com/haoyixu54-hue/toutiao-writing-skill/main/install.ps1 | iex
```

### macOS / Linux
```bash
curl -fsSL https://raw.githubusercontent.com/haoyixu54-hue/toutiao-writing-skill/main/install.sh | bash
```

### 手动安装
```bash
git clone https://github.com/haoyixu54-hue/toutiao-writing-skill.git ~/.claude/skills/writing/
pip install -r ~/.claude/skills/writing/requirements.txt
```

## 使用

在 Claude Code 中输入：

```
/writing 今天有什么娱乐大瓜？
```

或提供参考链接：

```
/writing https://www.toutiao.com/article/xxxxx
```

## 依赖

- Python 3.10+
- Windows 系统自带 Edge 浏览器（用于头条文章抓取）
- pip 包：`playwright`, `Pillow`, `python-docx`, `icrawler`

## 输出

文章将生成到：`桌面/今日头条/年份/月份/日期/标题.docx`
