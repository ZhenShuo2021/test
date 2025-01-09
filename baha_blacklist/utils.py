import argparse
import base64
import json
import os
from datetime import datetime
from typing import Any

from curl_cffi.requests import Session


def load_users(source: str, session: Session) -> list[str]:
    """從黑名單列表中讀取用戶，來源可以是網路或者文件檔案"""
    if source.startswith(("http://", "https://")):
        response = session.get(source)
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


def get_default_user_info(min_visit: int) -> tuple[int, datetime]:
    """獲取user_info失敗時的預設數值, 預設數值被設定為不會修改好友名單"""
    login_date, visit_count = datetime.now(), min_visit + 1
    return visit_count, login_date


def encode_base64(data: str) -> str:
    """編碼成base64格式"""
    return base64.b64encode(data.encode("utf-8")).decode("utf-8")


def decode_base64(encoded_data: str) -> str:
    """解碼回字串"""
    return base64.b64decode(encoded_data.encode("utf-8")).decode("utf-8")


def decode_response_dict(response: dict[str, Any]) -> dict[str, Any]:
    """懶惰的解碼方式，只適用於簡單 unicode"""
    return json.loads(json.dumps(response, ensure_ascii=False))


def count_success(results: dict[Any, Any], keywords: list[str] = ["失敗"]) -> int:
    return sum(1 for r in results.values() if not any(keyword in r for keyword in keywords))


class CustomHelpFormatter(argparse.RawTextHelpFormatter):
    def __init__(self, prog: Any) -> None:
        super().__init__(prog, max_help_position=36)

    def _format_action_invocation(self, action: argparse.Action) -> str:
        if not action.option_strings:
            (metavar,) = self._metavar_formatter(action, action.dest)(1)
            return metavar
        else:
            parts: list[str] = []
            if action.nargs == 0:
                parts.extend(action.option_strings)

            else:
                default = action.dest.upper()
                args_string = self._format_args(action, default)
                for option_string in action.option_strings:
                    # parts.append('%s %s' % (option_string, args_string))
                    parts.append(f"{option_string}")
                parts[-1] += f" {args_string}"
            return ", ".join(parts)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="巴哈黑名單工具",
        formatter_class=CustomHelpFormatter,
    )
    parser.add_argument("-a", "--account", dest="account", type=str, help="帳戶名稱")
    parser.add_argument("-p", "--password", dest="password", type=str, help="帳戶密碼")
    parser.add_argument("-c", "--cookie-path", dest="cookie_path", type=str, help="cookie檔案路徑")
    parser.add_argument(
        "--cookies-first",
        action="store_true",
        dest="cookies_first",
        help="先使用cookies登入，失敗才改用密碼登入",
    )
    parser.add_argument(
        "-s",
        "--source-path",
        dest="blacklist_src",
        type=str,
        help="黑名單來源檔案路徑",
    )
    parser.add_argument(
        "-o",
        "--output-path",
        dest="blacklist_dest",
        type=str,
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
        dest="force_clean",
        help="強制清理黑名單列表，預設黑名單數量超過 1000 人才會自動清理",
    )

    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument("-q", "--quiet", action="store_true", help="安靜模式")
    log_group.add_argument("-v", "--verbose", action="store_true", help="偵錯模式")

    return parser.parse_args()
