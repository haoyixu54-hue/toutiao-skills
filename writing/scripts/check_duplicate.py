#!/usr/bin/env python3
"""
查重脚本：对生成的文章文本进行相似度检测。
使用内置 difflib 对比已知热点文章库，给出重复率估算。
如果没有安装依赖，纯本地运行也有效。
"""

import difflib
import sys
import os


def load_reference_texts(library_dir: str) -> list[dict]:
    """加载参考文章库。"""
    texts = []
    if not os.path.isdir(library_dir):
        return texts
    for fname in os.listdir(library_dir):
        if fname.endswith((".txt", ".md")):
            path = os.path.join(library_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                texts.append({"title": fname, "content": f.read()})
    return texts


def check_duplicate(text: str, reference_texts: list[dict], threshold: float = 0.6) -> dict:
    """
    将输入文本与参考文本逐一比对，返回相似度结果。
    threshold: 相似度阈值，超过此值视为"可能重复"
    """
    results = []
    for ref in reference_texts:
        sim = difflib.SequenceMatcher(None, text, ref["content"]).ratio()
        results.append({
            "title": ref["title"],
            "similarity": round(sim, 4),
            "duplicate": sim > threshold
        })
    return {
        "checked": len(results),
        "duplicates": [r for r in results if r["duplicate"]],
        "max_similarity": max((r["similarity"] for r in results), default=0),
        "safe": all(not r["duplicate"] for r in results)
    }


def main():
    if len(sys.argv) < 2:
        print("用法: python check_duplicate.py <待检测文本文件>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.isfile(file_path):
        print(f"错误: 文件不存在 - {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    library_dir = os.path.join(script_dir, "article_library")

    ref_texts = load_reference_texts(library_dir)
    result = check_duplicate(text, ref_texts)

    print(f"检测完成: 共比对 {result['checked']} 篇参考文章")
    print(f"最大相似度: {result['max_similarity']:.2%}")
    print(f"安全性: {'通过' if result['safe'] else '存在重复风险'}")

    if result["duplicates"]:
        print("\n可能重复的文章:")
        for dup in result["duplicates"]:
            print(f"  - {dup['title']} (相似度: {dup['similarity']:.2%})")


if __name__ == "__main__":
    main()
