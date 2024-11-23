import os
import argparse

import requests

from .constant import BLACKLIST_DEST, BLACKLIST_SRC, COOKIE_PATH, USERNAME


def load_users(source: str) -> list[str]:
    if source.startswith(("http://", "https://")):
        response = requests.get(source)
        response.raise_for_status()
        return [line.rstrip("\n") for line in response.text.splitlines()]
    else:
        if os.path.isfile(source):
            with open(source, encoding="utf-8") as f:
                return [line.rstrip("\n") for line in f]
        else:
            return None


def write_users(file_path: str, content: list | None = None) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content))
        f.write("\n")


def to_unicode(string: str) -> str:
    return string.encode(encoding="UTF-8").decode()


class CustomHelpFormatter(argparse.RawTextHelpFormatter):
    def __init__(self, prog) -> None:
        super().__init__(prog, max_help_position=36)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="巴哈黑名單工具",
        formatter_class=CustomHelpFormatter,
    )
    parser.add_argument("--username", type=str, default=USERNAME, help="帳號名稱")
    parser.add_argument("--cookie-path", type=str, default=COOKIE_PATH, help="cookie檔案路徑")
    parser.add_argument("--source-path", type=str, default=BLACKLIST_SRC, help="黑名單來源檔案路徑")
    parser.add_argument(
        "--output-path",
        type=str,
        default=BLACKLIST_DEST,
        help="匯出黑名單的檔案路徑",
    )
    parser.add_argument(
        "--mode",
        choices=["update", "export", "clean"],
        nargs="+",
        required=False,
        default=["update", "export", "clean"],
        help="選擇執行模式，可以同時選擇多個模式, 預設全選\n'update' 更新黑名單\n'export' 匯出黑名單\n'clean' 清除黑名單",
    )

    return parser.parse_args()
