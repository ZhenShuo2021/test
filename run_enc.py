# 用於生成 Github Action 需要的 base64 編碼的 cookies
import pyperclip

from baha_blacklist.actions import cookies_to_base64

pyperclip.copy(cookies_to_base64())
print("Base64 編碼的 Cookies 已複製到剪貼簿")  # noqa: T201
