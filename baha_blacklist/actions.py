# DO NOT IMPORT THIS FILE FROM OTHER FILE
import logging
import os
import sys

from .config import Config, ConfigLoader
from .main import GamerAPIExtended
from .utils import base64_decode, base64_encode, write_users

cookie_path = "decoded_cookies.txt"


def cookies_to_base64(
    input_file: str = "cookies.txt",
    output_file: str = "cookies_base64.txt",
    write: bool = False,
) -> str:
    """讀取 cookies 將內容進行 Base64 編碼後寫入或印出"""
    with open(input_file) as f:
        cookies_content = f.read()
    cookies_base64 = base64_encode(cookies_content)
    if write:
        with open(output_file, "w") as f:
            f.write(cookies_base64)
    return cookies_base64


def decode_cookies_from_base64() -> None:
    """從 GitHub 環境變數獲取 Base64 編碼的 cookie, 解碼並寫進臨時檔案"""
    cookies_base64 = os.getenv("COOKIES_BASE64")
    if not cookies_base64:
        raise ValueError("環境變數 COOKIES_BASE64 未設定或為空")

    cookies_content = base64_decode(cookies_base64)

    with open(cookie_path, "w") as f:
        f.write(cookies_content)


def simplified_logger(loglevel: int = logging.DEBUG) -> logging.Logger:
    logging.root.setLevel(loglevel)
    logging.root.handlers.clear()

    logger = logging.getLogger()
    logger.setLevel(loglevel)
    logger.handlers.clear()

    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler = logging.StreamHandler()
    handler.setLevel(loglevel)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


if __name__ == "__main__":
    decode_cookies_from_base64()
    logger = simplified_logger()

    config_loader = ConfigLoader(Config())
    config = config_loader.load_config()
    config.cookie_path = cookie_path
    config.username = os.environ["BAHA_USERNAME"]

    api = GamerAPIExtended(config)

    if not api.login_success():
        logger.error("登入失敗，請更新 Cookies")
        sys.exit(0)

    logger.info("開始匯出黑名單...")
    existing_users = api.export_users()
    logger.info(f"黑名單匯出成功, 總共匯出 {len(existing_users)} 個名單")
    write_users(config.blacklist_dest, existing_users)
    logger.info("黑名單匯出結束\n")
