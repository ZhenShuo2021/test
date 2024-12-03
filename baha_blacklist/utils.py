import os
import argparse
from datetime import datetime
from typing import Literal

import requests

from .constant import BLACKLIST_DEST, BLACKLIST_SRC, COOKIE_PATH, MIN_VISIT, USERNAME


def load_users(source: str) -> list[str]:
    """從黑名單列表中讀取用戶，來源可以是網路或者文件檔案"""
    if source.startswith(("http://", "https://")):
        response = requests.get(source)
        response.raise_for_status()
        return [line.rstrip("\n") for line in response.text.splitlines()]
    else:
        if os.path.isfile(source):
            with open(source, encoding="utf-8") as f:
                return [line.rstrip("\n") for line in f]
        else:
            return []


def write_users(file_path: str, content: list[str]) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content))
        f.write("\n")


def to_unicode(string: str) -> str:
    return string.encode(encoding="UTF-8").decode()


def get_default_user_info() -> tuple[Literal[51], datetime]:
    """獲取user_info失敗時的預設數值, 預設數值被設定為不會修改好友名單"""
    login_date, visit_count = datetime.now(), MIN_VISIT + 1
    return visit_count, login_date


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
    parser.add_argument(
        "--force-clean",
        action="store_true",
        help="強制清理黑名單列表，預設黑名單數量超過 1000 人才會自動清理",
    )

    return parser.parse_args()
