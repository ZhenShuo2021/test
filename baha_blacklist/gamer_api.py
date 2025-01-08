import http.cookiejar as cookiejar
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
from lxml import html

from .config import Config
from .utils import decode_response_dict, get_default_user_info, to_unicode

logger = logging.getLogger("baha_blacklist")
logger_time_fmt = "%Y-%m-%d"


@dataclass
class UserInfo:
    uid: str
    visit_count: int
    last_login: datetime

    def __str__(self) -> str:
        return f"UserInfo(uid={self.uid}, visit_count={self.visit_count}, last_login={self.last_login.strftime(logger_time_fmt)})"


class GamerLogin:
    "登入和建立 Session"

    BASE_URL = "https://www.gamer.com.tw/"
    __LOGIN_COOKIES = {"_ga": "GA1.1.135792468.2468013579"}

    def __init__(self, config: Config) -> None:
        self.logger = logger
        self.config = config
        self.session = self.new_session()
        self.csrf_token = None
        self.login_methods = [self.login_password, self.login_cookies]

    def login(self) -> bool:
        self.logger.debug("開始登入...")
        for method in self.login_methods:
            if method():
                self.logger.debug(f"{method.__name__} 登入成功")
                return True
            self.logger.debug(f"{method.__name__} 登入失敗")

        self.logger.error("所有登入方式皆失敗，程式終止")
        return False

    def login_cookies(self) -> bool:
        cookie_jar = cookiejar.MozillaCookieJar(self.config.cookie_path)
        cookie_jar.load()
        self.session.cookies.update({
            cookie.name: cookie.value for cookie in cookie_jar if cookie.value
        })
        return self.login_success()

    def login_password(self) -> bool:
        if not self.config.password:
            self.logger.debug("未提供密碼，跳過密碼登入流程")
            return False

        try:
            if alternative_captcha := self.__login_password_phase1():
                self.__login_password_phase2(alternative_captcha)
                return self.login_success()
        except Exception as e:
            self.logger.error(f"密碼登入錯誤: {e!s}")

        return False

    def login_success(self) -> bool:
        """檢查是否成功登入, 被重定向代表登入失敗, 回傳 False"""
        url = "https://home.gamer.com.tw/setting/"
        self.logger.debug("檢查登入狀態")
        response = self.session.get(url, headers=self.headers)
        login_status = response.redirect_count == 0
        self.logger.debug(f"登入狀態檢查結果: {'成功' if login_status else '失敗'}")
        return login_status

    def new_session(self, extra_headers: dict[str, str] = {}) -> requests.Session:
        self.headers = {"User-Agent": self.config.user_agent, **extra_headers}
        return requests.Session(headers=self.headers, impersonate=self.config.browser)  # type: ignore

    def __login_password_phase1(self) -> str | None:
        """登入前置步驟，回傳 None 代表失敗"""
        url = "https://user.gamer.com.tw/login.php"
        login_status = None
        response = self.session.get(url, cookies=self.__LOGIN_COOKIES)
        if response.status_code != 200:
            return login_status

        pattern = r'<input type="hidden" name="alternativeCaptcha" value="(\w+)"'
        match = re.search(pattern, response.text)
        return match.group(1) if match else login_status

    def __login_password_phase2(self, alternative_captcha: str) -> None:
        """執行登入"""
        url = "https://user.gamer.com.tw/ajax/do_login.php"
        login_data = {
            "userid": self.config.account,
            "password": self.config.password,
            "alternativeCaptcha": alternative_captcha,
        }

        response = self.session.post(url, data=login_data, cookies=self.__LOGIN_COOKIES)
        response.raise_for_status()


class GamerAPI(GamerLogin):
    """基本API類別, 用於添加用戶(添加黑名單、好友等)以及匯出用戶列表"""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self.api_url = "https://api.gamer.com.tw/user/v1/friend_add.php"

    def add_user(self, uid: str, category: str = "bad") -> str:
        """
        Args:
            uid: The user ID
            category: the operation to gamer.com API. Defaults to bad (add to black list)
        """
        self.logger.debug(f"開始處理用戶 {uid}: {category} 操作")

        if not self.csrf_token:
            self._update_csrf()
        data = {"uid": uid, "category": category}

        try:
            response = self.session.post(self.api_url, headers=self.headers, data=data)
            response.raise_for_status()
            result = str(response.json().get("data"))
            self.logger.debug(f"用戶 {uid} {category} 操作成功: {result}")
        except RequestException as e:
            result = f"狀態碼錯誤: {e}"
            self.logger.error(f"用戶 {uid} {category} 操作網路請求失敗: {result}")

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
            existing_users: 目前的既有用戶清單，清單內的用戶會被跳過避免重複發送請求
            category: 操作類型, 預設為 "bad" (加入黑名單)

        Returns:
            Dict[str, Any]: 每個用戶ID對應的操作結果
        """
        logger_mapping: dict[str, str] = {"bad": "加入黑名單"}
        results: dict[str, str] = {}
        consecutive_errors = 0
        total_users = len(uids)
        processed_count = 0

        self.logger.info(f"開始進行用戶 {logger_mapping[category]} 操作，共 {total_users} 個用戶")

        for uid in uids:
            processed_count += 1
            if uid in existing_users:
                self.logger.debug(f"用戶 {uid} 已存在清單中 ({processed_count}/{total_users})")
                results[uid] = "已存在清單中"
                continue

            if consecutive_errors >= 3:
                error_msg = "連續操作失敗三次，系統中止"
                self.logger.error(f"{error_msg} ({processed_count}/{total_users})")
                raise Exception(error_msg)

            try:
                result = self.add_user(uid, category)
                results[uid] = result
                self.logger.info(f"處理進度: {processed_count}/{total_users}")
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"用戶 {uid} 處理失敗: {e} ({processed_count}/{total_users})")

            time.sleep(random.uniform(self.config.min_sleep, self.config.max_sleep))

        self.logger.info(f"處理完成，成功處理: {processed_count}/{total_users}")
        return results

    def export_users(self, type_id: int = 5) -> list[str]:
        """
        讀取黑名單列表
        Args:
            type_id: 頁面類型id, 預設 5 是黑名單頁面
        Returns:
            list[str]: 黑名單用戶ID列表
        """
        page_mapping: dict[int, str] = {1: "好友", 2: "待確認", 3: "追蹤", 4: "追蹤者", 5: "黑名單"}
        self.logger.info(f"開始讀取用戶 {self.config.account} 的{page_mapping[type_id]}清單")
        url = f"https://home.gamer.com.tw/friendList.php?user={self.config.account}&t={type_id}"

        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            tree = html.fromstring(response.text)
            user_ids = tree.xpath("//div[@class='user_id']/@data-origin")

            if not user_ids:
                self.logger.info(f"用戶 {self.config.account} 的清單目前無資料")
                return []

            self.logger.info(f"成功讀取清單，共 {len(user_ids)} 筆資料")
            return user_ids

        except Exception as e:
            self.logger.error(f"用戶 {self.config.account} 的清單讀取失敗: {e}")
            return []

    def get_user_info(self, uid: str) -> UserInfo:
        """取得用戶資訊, 用於判斷是否刪除用戶

        Returns:
            UserInfo 物件
        """
        self.logger.debug(f"開始讀取用戶 {uid} 資訊")
        url = f"https://api.gamer.com.tw/home/v1/block_list.php?userid={uid}"
        default_visit_count, default_login_date = get_default_user_info(self.config.min_visit)

        def extract_response(data: dict[str, Any]) -> UserInfo | None:
            try:
                for block in data["data"]["blocks"]:
                    if block.get("type") == "user_info":
                        info = {item["name"]: item["value"] for item in block["data"]["items"]}
                        vc = info.get("上站次數", default_visit_count)
                        ll = info.get("上站日期", default_login_date)

                        visit_count = int(vc)
                        last_login = datetime.strptime(ll, "%Y-%m-%d")
                        return UserInfo(uid=uid, visit_count=visit_count, last_login=last_login)
                return None
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.error(f"JSON response 解碼失敗: {e}")
                return None

        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            data = decode_response_dict(response.json())

            user_info = extract_response(data)
            if user_info:
                return user_info

        except RequestException as e:
            self.logger.error(f"取得用戶 {uid} 資訊時網路請求失敗: {e}")
        except (ValueError, TypeError) as e:
            self.logger.error(f"取得用戶 {uid} 資訊時解析失敗: {e}")
        except Exception as e:
            self.logger.error(f"取得用戶 {uid} 資訊時讀取失敗: {e}")

        return UserInfo(uid=uid, visit_count=default_visit_count, last_login=default_login_date)

    def _update_csrf(self) -> None:
        self.logger.debug("開始更新 CSRF Token")
        response = self.session.get(self.BASE_URL, headers=self.headers)
        response.raise_for_status()
        self.csrf_token = self.session.cookies.get("ckBahamutCsrfToken")

        if not self.csrf_token:
            error_msg = "無法取得 CSRF Token，請更新登入資料"
            self.logger.error(error_msg)
            raise Exception(error_msg)

        self.headers["x-bahamut-csrf-token"] = self.csrf_token  # type: ignore
        self.logger.debug("CSRF Token 更新成功")


class GamerAPIExtended(GamerAPI):
    """專責處理 https://home.gamer.com.tw/friendList.php?user=用戶名稱&t=5 的 API"""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self.user_info_time = to_unicode("上站次數")
        self.user_info_login = to_unicode("上站日期")

    def remove_user(self, uid: str) -> str:
        """發送 POST 請求刪除用戶 (移除黑名單)"""
        self.logger.debug(f"開始移除用戶 {uid}")

        try:
            csrf_token = self._get_friendList_csrf()
            delete_url = f"{self.BASE_URL}ajax/friend_del.php"
            data = {
                "fid": uid,
                "token": csrf_token,
            }  # fid: see https://home.gamer.com.tw/friendList.php?user=[用戶名稱]&t=5

            response = self.session.post(delete_url, headers=self.headers, data=data)
            response.raise_for_status()
            message = response.text
            self.logger.debug(f"用戶 {uid} 移除成功")

        except RequestException as e:
            message = f"用戶移除失敗: {e}"
            self.logger.error(f"移除用戶 {uid} 時網路請求失敗: {e!s}")

        return message

    def remove_users(self, uids: list[str]) -> dict[str, Any]:
        results = {}
        total_users = len(uids)
        processed_count = 0
        consecutive_errors = 0

        self.logger.info(f"開始移除用戶，共 {total_users} 個用戶")

        for uid in uids:
            processed_count += 1
            try:
                result = self.remove_user(uid)
                results[uid] = result
                self.logger.info(f"移除進度: {processed_count}/{total_users}")
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                error_msg = f"用戶移除失敗: {e}"
                results[uid] = error_msg
                self.logger.error(f"用戶 {uid} {error_msg} ({processed_count}/{total_users})")

            time.sleep(random.uniform(self.config.min_sleep, self.config.max_sleep))

        success_count = sum(1 for r in results.values() if "失敗" not in r)
        self.logger.info(f"用戶移除完成，成功: {success_count}/{total_users}")
        return results

    def smart_remove_user(self, uid: str, min_visits: int = 50, min_days: int = 60) -> None:
        """檢查並移除不符合條件的用戶

        Args:
            uid: 用戶ID
            min_visits: 最小上站次數
            min_days: 最近登入天數最小容許值
        """
        self.logger.debug(f"開始用戶 {uid} 移除任務")

        try:
            user_info = self.get_user_info(uid)
            self.logger.debug(f"用戶資訊: {user_info}")

            last_login = (datetime.now() - user_info.last_login).days

            reasons = []
            if user_info.visit_count < min_visits:
                reasons.append(f"上站次數({user_info.visit_count})低於{min_visits}")
            if last_login > min_days:
                reasons.append(f"上站日期距離現在天數({last_login})大於{min_days}")

            if reasons:
                msg = self.remove_user(uid)
                self.logger.debug(f"用戶 {uid} 已移除: {', '.join(reasons)}, 處理結果: {msg}")
            else:
                msg = f"用戶 {uid} 已保留 (上站次數: {user_info.visit_count}, 上站日期距離現在天數: {last_login})"
                self.logger.debug(msg)

        except RequestException as e:
            self.logger.error(f"移除用戶 {uid} 時網路請求失敗: {e!s}")

    def smart_remove_users(
        self,
        uids: list[str],
        min_visits: int = 50,
        min_days: int = 60,
    ) -> None:
        total_users = len(uids)
        self.logger.info(
            f"開始移除用戶，共 {total_users} 個用戶，移除門檻為：「最小上站次數: {min_visits}, 最小天數: {min_days}」"
        )
        consecutive_errors = 0

        for index, uid in enumerate(uids, 1):
            try:
                self.smart_remove_user(uid)
                self.logger.info(f"移除進度: {index}/{total_users}")
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                error_msg = f"用戶移除失敗: {e}"
                self.logger.error(f"用戶 {uid} {error_msg} ({index}/{total_users})")

            time.sleep(random.uniform(self.config.min_sleep, self.config.max_sleep))

        self.logger.info(f"用戶移除完成，共處理 {total_users} 個用戶")

    def _get_friendList_csrf(self) -> str:
        """取得 friendList.php 專用的 CSRF Token

        see: https://home.gamer.com.tw/friendList.php?user=[你的帳號]&t=5
        """
        self.logger.debug("開始取得 friendList CSRF Token")
        csrf_token_url = urljoin(self.BASE_URL, "ajax/getCSRFToken.php")
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
            raise Exception("CSRF Token 取得失敗，請更新 cookies 文件")

        return csrf_token
