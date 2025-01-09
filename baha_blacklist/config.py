import json
import logging
import os
from argparse import Namespace
from dataclasses import asdict, dataclass
from typing import Any

from curl_cffi.requests.impersonate import BrowserTypeLiteral

logger = logging.getLogger()


@dataclass
class Config:
    account: str = "your account here"
    password: str = ""
    cookie_path: str = "./cookies.txt"
    cookies_first: bool = False
    blacklist_dest: str = "./blacklist.txt"
    blacklist_src: str = (
        "https://github.com/ZhenShuo2021/baha-blacklist/raw/refs/heads/main/blacklist.txt"
    )
    min_sleep: int | float = 1.0
    max_sleep: int | float = 10.0
    min_visit: int = 5
    min_day: int = 1
    friend_num: int = 100
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    browser: BrowserTypeLiteral = "chrome131"

    def validate(self) -> None:
        # 別忘了修改 actions.py
        if self.account == "your account here":
            raise ValueError(
                "未設定使用者帳號，請使用 -u 參數設定帳號名稱或到 config.json 修改預設值"
            )
        if self.min_sleep > self.max_sleep:
            raise ValueError("min_sleep 必須大於 max_sleep.")


class ConfigLoader:
    def __init__(self, defaults: Config):
        self.defaults = defaults

    def load_config(
        self,
        json_path: str | None = None,
        args: dict[str, Any] | Namespace = {},
        env_mapping: dict[str, str] | None = None,
    ) -> Config:
        logger.info("開始載入設定")
        env_mapping = env_mapping or {}
        json_config = ("json_config", self.load_from_json(json_path))
        env_config = ("env_config", self.load_from_env(env_mapping))
        cli_config = ("cli_config", self.load_from_cli(args))
        final_config = self.merge_configs(json_config, env_config, cli_config)
        final_config.validate()
        logger.info("設定已成功載入並驗證")
        return final_config

    def load_from_json(self, file_path: str | None) -> dict[str, Any]:
        if file_path and os.path.exists(file_path):
            logger.debug(f"開始從 JSON 文件載入設定：{file_path}")
            with open(file_path) as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError as e:
                    logger.error(f"{file_path} 中的 JSON 格式無效：{e}")
                    raise ValueError(f"{file_path} 中的 JSON 格式無效：{e}")
        logger.warning("未提供 JSON 設定檔或檔案不存在")
        return {}

    def load_from_cli(self, args: dict[str, Any] | Namespace) -> dict[str, Any]:
        logger.debug("開始從 CLI 參數載入設定")
        if isinstance(args, Namespace):
            args = vars(args)
        return args

    def load_from_env(self, env_mapping: dict[str, str]) -> dict[str, Any]:
        """只讀取特定的環境變數，支援變數名稱映射

        Args:
            env_mapping (dict[str, str]): 將字典 value 取出作為 key 在環境變數中尋找值，如果非 None 則把字典的 key
            作為回傳字典的 key 新增

        Returns:
            dict[str, Any]: 將被載入到 Config 中的設定值
        """
        logger.debug("開始從環境變數載入設定")
        return {
            key: os.getenv(env_var)
            for key, env_var in env_mapping.items()
            if os.getenv(env_var) is not None
        }

    def merge_configs(self, *config_pairs: tuple[str, dict[str, Any]]) -> Config:
        logger.debug("開始合併設定")
        valid_keys = asdict(self.defaults)
        for source_name, config in config_pairs:
            for key, value in config.items():
                # 不在合法的 key 中
                if key not in valid_keys:
                    logger.debug(f"跳過由 {source_name} 不支援的設定類型: {key}")
                    continue

                # 在合法的 key 中
                if value is None:
                    continue
                elif isinstance(value, type(valid_keys[key])):
                    valid_keys[key] = value
                else:
                    err_msg = f"key '{key}' 型別錯誤： Expected {type(valid_keys[key])}, got {type(value)}"
                    logger.error(err_msg)
                    raise TypeError(err_msg)
        logger.debug("設定已成功合併")
        return Config(**valid_keys)
