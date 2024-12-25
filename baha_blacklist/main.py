import sys
import time
import random
import http.cookiejar as cookiejar
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from .constant import (
    FRIEND_NUM,
    MAX_SLEEP,
    MIN_DAY,
    MIN_SLEEP,
    MIN_VISIT,
    USER_AGENT,
)
from .utils import get_default_user_info, load_users, parse_arguments, to_unicode, write_users


@dataclass
class UserInfo:
    visit_count: int
    last_login: datetime


class GamerAPI:
    """基本API類別, 用於添加用戶(添加黑名單、好友等)以及匯出用戶列表(黑名單列表)"""

    def __init__(self, username: str, cookie_path: str) -> None:
        """
        Args:
            username (str): 使用者的帳號名稱
            cookie_path (str): cookie 檔案路徑
        """
        self.username = username
        self.cookie_jar = cookiejar.MozillaCookieJar(cookie_path)
        self.cookie_jar.load()
        self.session = requests.Session()
        self.session.cookies.update({
            cookie.name: cookie.value for cookie in self.cookie_jar if cookie.value
        })
        self.base_url = "https://home.gamer.com.tw/"
        self.api_url = "https://api.gamer.com.tw/user/v1/friend_add.php"
        self.headers = {"User-Agent": USER_AGENT, "Referer": "https://www.gamer.com.tw/"}
        self.csrf_token = None

    def add_user(self, uid: str, category="bad") -> str | None:
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
                return f"請求失敗, 狀態碼: {response.status_code}"
        except Exception as e:
            result = f"用戶關係操作錯誤: {e}"

        print(f"用戶 {uid} 新增結果: {result}")
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
        results = {}
        consecutive_errors = 0

        for uid in uids:
            if uid in existing_users:
                print(f"用戶 {uid} 已在列表中, 跳過")
                results[uid] = "已在列表中"
                continue

            if consecutive_errors >= 3:
                raise Exception("連續三次失敗, 程序中斷")

            result = self.add_user(uid, category)
            results[uid] = result

            if isinstance(result, str):
                consecutive_errors += 1
            else:
                consecutive_errors = 0

            time.sleep(random.uniform(MIN_SLEEP, MAX_SLEEP))
        return results

    def export_users(self, username: str, type_id=5) -> list[str]:
        """
        讀取黑名單列表
        Args:
            username: 你的帳號名稱
            type_id: 頁面類型id, 預設 5 是黑名單頁面
        Returns:
            blacklisted_uids: 黑名單用戶ID列表
        """
        url = f"https://home.gamer.com.tw/friendList.php?user={username}&t={type_id}"
        try:
            response = self.session.get(url, headers=self.headers)
            if response.status_code != 200:
                print(f"無法獲取頁面, 狀態碼: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            user_ids = [div.get("data-origin") for div in soup.find_all("div", class_="user_id")]

            if not user_ids:
                print("未找到任何黑名單ID")
                return []

            return user_ids
        except Exception as e:
            print(f"擷取黑名單列表失敗: {e}")
            return []

    def check_login(self) -> bool:
        """檢查是否成功登入, 被 redirect 代表登入失敗, 回傳 False"""
        url = "https://home.gamer.com.tw/setting/"
        response = self.session.get(url, headers=self.headers)
        return not response.history or not (300 <= response.history[0].status_code < 400)

    def _update_csrf(self) -> None:
        response = self.session.get(self.base_url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"連接失敗, 狀態碼: {response.status_code}")
        self.csrf_token = self.session.cookies.get("ckBahamutCsrfToken")
        if not self.csrf_token:
            raise Exception("找不到 ckBahamutCsrfToken, 請更新 cookies 文件")
        self.headers["x-bahamut-csrf-token"] = self.csrf_token


class GamerAPIExtended(GamerAPI):
    """專責處理 https://home.gamer.com.tw/friendList.php?user=用戶名稱&t=5 的 API"""

    def __init__(self, username, cookie_path: str) -> None:
        super().__init__(username, cookie_path)
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

            if response.status_code == 200:
                result = response.text
                message = f"{result}"
            else:
                message = f"刪除請求失敗, 狀態碼: {response.status_code}"
        except Exception as e:
            message = f"刪除好友操作錯誤: {e}"

        return message

    def batch_remove_user(self, uids: list[str]) -> dict[str, Any]:
        results = {}
        for uid in uids:
            result = self.remove_user(uid)
            results[uid] = result
            time.sleep(random.uniform(MIN_SLEEP, MAX_SLEEP))
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
            user_info = self._get_user_info(uid)
            if user_info is None:
                print(f"無法獲取用戶 {uid} 的資訊")
                return

            last_login = (datetime.now() - user_info.last_login).days

            reason = []
            if user_info.visit_count < min_visits:
                reason.append(f"上站次數({user_info.visit_count})低於{min_visits}")
            if last_login > min_days:
                reason.append(f"上站日期距離現在天數({last_login})大於{min_days}")

            if reason:
                msg = self.remove_user(uid)
                print(f"用戶移除 {uid}: {', '.join(reason)}, 移除結果: {msg}")
            else:
                print(
                    f"用戶保留 {uid} (上站次數: {user_info.visit_count}, 上站日期距離現在天數: {last_login})",
                )

        except Exception as e:
            print(f"處理用戶 {uid} 時發生錯誤: {e}")

    def batch_auto_remove_user(
        self,
        uids: list[str],
        min_visits: int = 50,
        min_days: int = 60,
    ) -> None:
        for uid in uids:
            self.auto_remove_user(uid, min_visits, min_days)
            time.sleep(random.uniform(MIN_SLEEP, MAX_SLEEP))

    def _get_user_info(self, uid: str) -> UserInfo | None:
        """
        取得用戶資訊, 用於自動刪除用戶
        Returns: UserInfo 對象或 None
        """
        url = f"https://home.gamer.com.tw/homeindex.php?owner={uid}"
        try:
            response = self.session.get(url, headers=self.headers, allow_redirects=True)
            if response.status_code != 200:
                print(f"取得用戶頁面失敗, 狀態碼: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            info_list = soup.select_one(".BH-rbox.BH-list1 ul")
            if info_list:  # 舊版面
                visit_count, login_date = self._get_user_info_old(uid, info_list)
            else:  # 新版面
                visit_count, login_date = self._get_user_info_api(uid)
                if not visit_count or not login_date:
                    visit_count, login_date = get_default_user_info()

            return UserInfo(visit_count=visit_count, last_login=login_date)

        except Exception as e:
            print(f"獲取用戶資訊時發生錯誤: {e}")
            return None

    def _get_user_info_old(self, userid: str, info_list) -> tuple[int, datetime]:
        # 舊版頁面, 範例 https://home.gamer.com.tw/homeindex.php?owner=win920424
        visit_count, login_date = get_default_user_info()
        for li in info_list.find_all("li"):
            text = li.text.strip()
            if "上站次數" in text:
                visit_count = int(text.split("：")[1])
            if "上站日期" in text:
                login_date = datetime.strptime(text.split("：")[1], "%Y-%m-%d")

        return visit_count, login_date

    def _get_user_info_api(
        self,
        userid: str,
    ) -> tuple[int, datetime] | tuple[None, None]:
        # 新版頁面, 範例 https://home.gamer.com.tw/profile/index.php?&owner=alele1680
        url = f"https://api.gamer.com.tw/home/v1/block_list.php?userid={userid}"
        login_date, visit_count = datetime.now(), MIN_VISIT + 1  # 預設不刪除

        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()

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

            return visit_count, login_date

        except requests.RequestException as e:
            print(f"HTTP 請求失敗: {e}")
        except Exception as e:
            print(f"資料處理失敗: {e}")

        return None, None

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

        if csrf_response.status_code != 200:
            raise Exception(f"獲取 CSRF Token 失敗, 狀態碼: {csrf_response.status_code}")

        csrf_token = csrf_response.text.strip()

        if not csrf_token:
            raise Exception("CSRF Token 為空, 請嘗試更新 Cookies ")

        return csrf_token


def main(args) -> None:
    if args.username == "your user name here":
        raise ValueError("帳號錯誤，請使用 --username 設定帳號名稱或到 constant.py 修改預設值")

    cookie_path = args.cookie_path
    source_path = args.source_path
    output_path = args.output_path
    username = args.username
    api = GamerAPIExtended(username, cookie_path)

    if not api.check_login():
        print("登入失敗，請更新 Cookies")
        sys.exit(0)

    if "export" in args.mode:
        print("開始匯出黑名單...")
        existing_users = api.export_users(username)
        print(f"黑名單匯出成功, 總共匯出 {len(existing_users)} 個名單")
        write_users(output_path, existing_users)
        print("黑名單匯出結束\n")
    else:
        existing_users = api.export_users(username)

    time.sleep(MIN_SLEEP)

    if "update" in args.mode:
        print("開始更新黑名單...")
        uids = load_users(source_path)
        if uids:
            api.add_users(uids, existing_users, category="bad")
        else:
            print("黑名單來源載入失敗")
        print("黑名單更新結束\n")

    if "clean" in args.mode:
        print("開始清理黑名單...")
        if args.force_clean or len(existing_users) > FRIEND_NUM:
            api.batch_auto_remove_user(existing_users, min_visits=MIN_VISIT, min_days=MIN_DAY)
        else:
            print(f"你的黑名單數量未超過 {FRIEND_NUM} 人, 跳過自動清理功能")
        print("黑名單清理結束\n")


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
