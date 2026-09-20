#!/usr/bin/env python3
"""把 Typst 导出的 HTML 处理成可嵌进 Jekyll 页面的正文片段。

做三件事：
1. 取出 <body> 内容（丢掉 Typst 自己生成的 <html>/<head>）；
2. 标题层级整体上移一级 —— Typst 的 HTML 导出把 `= 章标题` 映射成 <h2>（把 <h1>
   留给文档标题），但网页版的章标题由 Jekyll 页面的 title 提供（roadmap-web 已经
   丢掉了一级标题），所以 `== 小节` 落到了 <h3>，上移一级才能恢复 <h2>/<h3> 层级；
3. 给每个标题补 `id` 与 Chirpy 风格的 `#` 锚点链接 —— 原来的 Markdown 版靠
   Kramdown 自动生成这套东西，换成 Typst 后必须自己补，否则旧的 `#锚点` 链接会失效。
   slug 规则刻意对齐 Kramdown：只保留字母/数字/连字符，空白转 `-`，其余字符丢弃。

用法： typst-html-body.py <typst 导出的 html>
输出： 处理后的正文片段（stdout）
"""

import html as htmllib
import re
import sys


def slugify(text: str) -> str:
    """对齐 Kramdown 的自动 id 规则。"""
    out = []
    for ch in text.lower():
        if ch.isalnum() or ch == "-":
            out.append(ch)
        elif ch.isspace():
            out.append("-")
    return "".join(out) or "section"


def main() -> None:
    raw = open(sys.argv[1], encoding="utf-8").read()
    m = re.search(r"<body>(.*)</body>", raw, re.S)
    body = (m.group(1) if m else raw).strip()

    seen: dict[str, int] = {}

    def fix(match: "re.Match[str]") -> str:
        level = int(match.group(1))
        inner = match.group(2)
        text = htmllib.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        sid = slugify(text)
        if sid in seen:
            seen[sid] += 1
            sid = f"{sid}-{seen[sid]}"
        else:
            seen[sid] = 0
        lvl = max(1, level - 1)
        return (
            f'<h{lvl} id="{sid}">'
            f'<span class="me-2">{inner}</span>'
            f'<a href="#{sid}" class="anchor text-muted"><i class="fas fa-hashtag"></i></a>'
            f"</h{lvl}>"
        )

    print(re.sub(r"<h([1-6])>(.*?)</h\1>", fix, body, flags=re.S))


if __name__ == "__main__":
    main()
