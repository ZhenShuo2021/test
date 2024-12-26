import http.cookiejar as cookiejar
import logging
import random
import sys
import time
from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
from lxml import html

from .config import Config, ConfigLoader
from .logger import setup_logging
from .utils import get_default_user_info, load_users, to_unicode, write_users

logger = logging.getLogger("baha_blacklist")


@dataclass
class UserInfo:
    uid: str  # 用戶名稱
    visit_count: int
    last_login: datetime


class GamerAPI:
    """基本API類別, 用於添加用戶(添加黑名單、好友等)以及匯出用戶列表(黑名單列表)"""

    def __init__(self, config: Config) -> None:
        self.logger = logger
        self.config = config
        cookie_jar = cookiejar.MozillaCookieJar(config.cookie_path)
        cookie_jar.load()
        self.session = requests.Session(impersonate=config.browser)  # type: ignore
        self.session.cookies.update({
            cookie.name: cookie.value for cookie in cookie_jar if cookie.value
        })
        self.base_url = "https://home.gamer.com.tw/"
        self.api_url = "https://api.gamer.com.tw/user/v1/friend_add.php"
        self.headers = {"User-Agent": config.user_agent, "Referer": "https://www.gamer.com.tw/"}
        self.csrf_token = None

    def add_user(self, uid: str, category: str = "bad") -> str:
        """
        Args:
            uid: The user ID
            category: the operation to gamer.com API. Defaults to bad (add to black list)
        """
        if not self.csrf_token:
            self._update_csrf()
        data = {"uid": uid, "category": category}

        try:
            response = self.session.post(self.api_url, headers=self.headers, data=data)
            if response.status_code == 200:
                result = response.json()
            else:
                return f"錯誤: 請求失敗, 狀態碼: {response.status_code}"
        except Exception as e:
            result = f"用戶關係操作錯誤: {e}"

        self.logger.info(f"用戶 {uid} 新增結果: {result}")
        return result

    def add_users(
        self,
        uids: list[str],
        existing_users: list[str],
        category: str = "bad",
    ) -> dict[str, Any]:
        """
        從列表新增用戶, 跳過已經在用戶列表(黑名單)中的用戶

        Args:
            uids: 用戶ID列表
            category: 操作類型, 預設為 "bad" (加入黑名單)
            username: 使用者名稱, 用於獲取該使用者的好友(黑名單)清單

        Returns:
            Dict[str, Any]: 每個用戶ID對應的操作結果
        """
        results: dict[str, str] = {}
        consecutive_errors = 0

        for uid in uids:
            if uid in existing_users:
                self.logger.info(f"用戶 {uid} 已在列表中, 跳過")
                results[uid] = "已在列表中"
                continue

            if consecutive_errors >= 3:
                raise Exception("連續三次失敗, 程序中斷")

            result = self.add_user(uid, category)
            results[uid] = result

            if "錯誤" in result:
                consecutive_errors += 1
            else:
                consecutive_errors = 0

            time.sleep(random.uniform(self.config.min_sleep, self.config.max_sleep))
        return results

    def export_users(self, type_id: int = 5) -> list[str]:
        """
        讀取黑名單列表
        Args:
            type_id: 頁面類型id, 預設 5 是黑名單頁面
        Returns:
            list[str]: 黑名單用戶ID列表
        """
        url = f"https://home.gamer.com.tw/friendList.php?user={self.config.username}&t={type_id}"
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            tree = html.fromstring(response.text)
            user_ids = tree.xpath("//div[@class='user_id']/@data-origin")
            if not user_ids:
                self.logger.info("未找到任何黑名單ID")
                return []
            return user_ids
        except Exception as e:
            self.logger.error(f"擷取黑名單列表失敗: {e}")
            return []

    def login_success(self) -> bool:
        """檢查是否成功登入, 被 redirect 代表登入失敗, 回傳 False"""
        url = "https://home.gamer.com.tw/setting/"
        response = self.session.get(url, headers=self.headers)
        return response.redirect_count == 0

    def _update_csrf(self) -> None:
        response = self.session.get(self.base_url, headers=self.headers)
        response.raise_for_status()
        self.csrf_token = self.session.cookies.get("ckBahamutCsrfToken")
        if not self.csrf_token:
            raise Exception("找不到 ckBahamutCsrfToken, 請更新 cookies 文件")
        self.headers["x-bahamut-csrf-token"] = self.csrf_token  # type: ignore


class GamerAPIExtended(GamerAPI):
    """專責處理 https://home.gamer.com.tw/friendList.php?user=用戶名稱&t=5 的 API"""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self.user_info_time = to_unicode("上站次數")
        self.user_info_login = to_unicode("上站日期")

    def remove_user(self, uid: str) -> str:
        """發送 POST 請求刪除用戶 (移除黑名單)"""
        try:
            csrf_token = self._get_friendList_csrf()
            delete_url = f"{self.base_url}ajax/friend_del.php"
            data = {
                "fid": uid,
                "token": csrf_token,
            }  # fid: see https://home.gamer.com.tw/friendList.php?user=[用戶名稱]&t=5
            response = self.session.post(delete_url, headers=self.headers, data=data)
            response.raise_for_status()
            result = response.text
            message = f"{result}"

        except Exception as e:
            message = f"刪除好友操作錯誤: {e}"
        return message

    def batch_remove_user(self, uids: list[str]) -> dict[str, Any]:
        results = {}
        for uid in uids:
            result = self.remove_user(uid)
            results[uid] = result
            time.sleep(random.uniform(self.config.min_sleep, self.config.max_sleep))
        return results

    def auto_remove_user(self, uid: str, min_visits: int = 50, min_days: int = 60) -> None:
        """
        自動檢查並移除不符合條件的用戶
        Args:
            uid: 用戶ID
            min_visits: 最小上站次數
            min_days: 最近登入天數最小容許值
        """
        try:
            user_info = self.get_user_info(uid)
            self.logger.debug(f"擷取用戶資訊: {user_info}")

            last_login = (datetime.now() - user_info.last_login).days

            reasons = []
            if user_info.visit_count < min_visits:
                reasons.append(f"上站次數({user_info.visit_count})低於{min_visits}")
            if last_login > min_days:
                reasons.append(f"上站日期距離現在天數({last_login})大於{min_days}")

            if reasons:
                msg = self.remove_user(uid)
                self.logger.info(f"用戶移除 {uid}: {', '.join(reasons)}, 移除結果: {msg}")
            else:
                self.logger.info(
                    f"用戶保留 {uid} (上站次數: {user_info.visit_count}, 上站日期距離現在天數: {last_login})",
                )

        except Exception as e:
            self.logger.error(f"處理用戶 {uid} 時發生錯誤: {e}")

    def batch_auto_remove_user(
        self,
        uids: list[str],
        min_visits: int = 50,
        min_days: int = 60,
    ) -> None:
        for uid in uids:
            self.auto_remove_user(uid, min_visits, min_days)
            time.sleep(random.uniform(self.config.min_sleep, self.config.max_sleep))

    def get_user_info(self, uid: str) -> UserInfo:
        """取得用戶資訊, 用於自動刪除用戶

        Returns:
            UserInfo 物件
        """
        url = f"https://api.gamer.com.tw/home/v1/block_list.php?userid={uid}"

        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            visit_count, login_date = get_default_user_info(self.config.min_visit)

            for block in data.get("data", {}).get("blocks", []):
                if block.get("type") == "user_info":
                    items = block.get("data", {}).get("items", [])
                    for item in items:
                        name = item.get("name")
                        value = item.get("value")

                        if name == self.user_info_time:  # 上站次數
                            visit_count = int(value)
                        elif name == self.user_info_login:  # 上站日期（上次登入日期）
                            login_date = datetime.strptime(value, "%Y-%m-%d")

            return UserInfo(uid=uid, visit_count=visit_count, last_login=login_date)

        except RequestException as e:
            self.logger.error(f"HTTP 請求失敗: {e}")
        except (ValueError, KeyError, TypeError) as e:
            self.logger.error(f"資料處理失敗: {e}")
        except Exception as e:
            self.logger.error(f"獲取用戶資訊時發生錯誤: {e}")

        visit_count, login_date = get_default_user_info(self.config.min_visit)
        return UserInfo(uid=uid, visit_count=visit_count, last_login=login_date)

    def _get_friendList_csrf(self) -> str:
        """取得 friendList.php 專用的 CSRF Token

        see: https://home.gamer.com.tw/friendList.php?user=[你的帳號]&t=5
        """
        csrf_token_url = f"{self.base_url}ajax/getCSRFToken.php"
        headers_with_referer = {
            **self.headers,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

        csrf_response = self.session.get(csrf_token_url, headers=headers_with_referer)
        csrf_response.raise_for_status()
        csrf_token = csrf_response.text.strip()

        if not csrf_token:
            raise Exception("CSRF Token 為空, 請嘗試更新 Cookies ")

        return csrf_token


def main(args: Namespace, config_name: str = "config.json") -> int:
    if args.username == "your user name here":
        raise ValueError("帳號錯誤，請使用 -u 參數設定帳號名稱或到 config.json 修改預設值")

    loglevel = logging.INFO
    if args.verbose:
        loglevel = logging.DEBUG
    if args.quiet:
        loglevel = logging.WARNING

    setup_logging(loglevel)
    json_path = str(Path(__file__).parents[1] / config_name)
    config_loader = ConfigLoader(Config())
    config = config_loader.load_config(json_path, args)
    blacklist_src = config.blacklist_src
    blacklist_dest = config.blacklist_dest
    api = GamerAPIExtended(config)

    try:
        if not api.login_success():
            logger.error("登入失敗，請更新 Cookies")
            sys.exit(0)

        if "export" in args.mode:
            logger.info("開始匯出黑名單...")
            existing_users = api.export_users()
            logger.info(f"黑名單匯出成功, 總共匯出 {len(existing_users)} 個名單")
            write_users(blacklist_dest, existing_users)
            logger.info("黑名單匯出結束\n")
        else:
            existing_users = api.export_users()

        time.sleep(config.min_sleep)

        if "update" in args.mode:
            logger.info("開始更新黑名單...")
            uids = load_users(blacklist_src, api.session)
            if uids:
                api.add_users(uids, existing_users, category="bad")
            else:
                logger.error("黑名單來源載入失敗")
            logger.info("黑名單更新結束\n")

        if "clean" in args.mode:
            logger.info("開始清理黑名單...")
            if args.force_clean or len(existing_users) > config.friend_num:
                api.batch_auto_remove_user(
                    existing_users, min_visits=config.min_visit, min_days=config.min_day
                )
            else:
                logger.info(f"黑名單數量未超過 {config.friend_num} 人, 跳過自動清理功能")
            logger.info("黑名單清理結束\n")

        return 0
    except Exception as error:
        raise RuntimeError(f"Runtime error: {error!s}")
