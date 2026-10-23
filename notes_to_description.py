"""
把 write_notes_if_needed() 生成的六段式节目笔记(.md)转成适合放进 RSS <description> 的
分段纯文本——用户反馈"没有层次"，根因是这份六段式内容一直只存在于本地 .md 文件里，
从未真正进入过 feed.xml 的 <description>（那里是手动拼的一段话）。
"""
import re
import sys
from pathlib import Path

COPYRIGHT_NOTICE = (
    "版权与 AI 译制说明：本节目为基于公开原始内容制作的非官方 AI 中文译制，"
    "仅供学习与交流，不代表原节目、嘉宾或相关机构立场。原始音视频、文字内容及相关权利"
    "归原权利人所有，请通过节目中标注的原始链接支持原作。中文翻译与合成语音可能存在偏差，"
    "请以原始内容为准。如权利人对本内容的使用有异议，请联系我们核实并处理。"
)


def append_copyright_notice(description: str) -> str:
    """追加一次统一版权说明；可安全重复调用。"""
    description = description.rstrip()
    if COPYRIGHT_NOTICE in description:
        return description
    return f"{description}\n\n{COPYRIGHT_NOTICE}" if description else COPYRIGHT_NOTICE


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
    return append_copyright_notice("\n\n".join(blocks))


def main():
    md_path = Path(sys.argv[1])
    print(notes_md_to_description(md_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
