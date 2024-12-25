# Github Action 用，獲取 base64 編碼的 cookies
import pyperclip

from baha_blacklist.actions import cookies_to_base64

pyperclip.copy(cookies_to_base64())
print("Base64 編碼的 Cookies 已複製到剪貼簿")
