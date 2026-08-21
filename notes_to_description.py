"""
把 write_notes_if_needed() 生成的六段式节目笔记(.md)转成适合放进 RSS <description> 的
分段纯文本——用户反馈"没有层次"，根因是这份六段式内容一直只存在于本地 .md 文件里，
从未真正进入过 feed.xml 的 <description>（那里是手动拼的一段话）。
"""
import re
import sys
from pathlib import Path


def notes_md_to_description(md_text: str) -> str:
    """输入 write_notes_if_needed() 产出的完整 .md 文本，输出保留六段结构、
    可以直接放进 XML <description> 文本节点的纯文本（用空行分隔各段，XML 原样保留换行）。"""
    lines = md_text.splitlines()
    sections = []
    cur_title, cur_body = None, []
    for line in lines:
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            if cur_title is not None:
                sections.append((cur_title, cur_body))
            cur_title, cur_body = m.group(1).strip(), []
        elif cur_title is not None:
            cur_body.append(line)
    if cur_title is not None:
        sections.append((cur_title, cur_body))

    blocks = []
    for title, body in sections:
        text = "\n".join(body).strip()
        if not text:
            continue
        blocks.append(f"{title}：\n{text}")
    return "\n\n".join(blocks)


def main():
    md_path = Path(sys.argv[1])
    print(notes_md_to_description(md_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
