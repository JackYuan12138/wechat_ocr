"""命令行入口：便于 AI 或其他脚本通过 subprocess 调用。

用法::

    python -m wechat_ocr <图片路径> [更多图片路径...]

输出：JSON 对象，键为输入路径，值为识别结果（含 text 与逐行坐标、置信度）。
"""
import sys
import json

from .engine import WeChatOcr


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("用法: python -m wechat_ocr <图片路径> [更多图片路径...]", file=sys.stderr)
        return 2

    with WeChatOcr() as client:
        output = {}
        for path in argv:
            output[path] = client.recognize(path).to_dict()

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
