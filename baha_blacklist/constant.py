# =====基本設定===== #
# 注意: Windows 平台設定路徑要加上r，例如 r".\cookies.txt" 代表同層的 cookies.txt 檔案
# 你的帳號名稱
USERNAME = "your user name here"
# 你的cookies檔案位置，預設在同一資料夾下的 cookies.txt
COOKIE_PATH = "./cookies.txt"
# 從你的帳號中匯出的黑單列表
BLACKLIST_DEST = "./黑單匯出結果.txt"
# 黑單來源
BLACKLIST_SRC = "https://raw.githubusercontent.com/ZhenShuo2021/baha-blacklist/refs/heads/main/%E9%BB%91%E5%96%AE%E5%8C%AF%E5%87%BA%E7%B5%90%E6%9E%9C.txt"
# 最小等待時間
MIN_SLEEP = 1
# 最大等待時間
MAX_SLEEP = 3.5

# =====清除黑名單模式的參數===== #
# 登入次數低於這個數值的帳號會被移除
MIN_VISIT = 10
# 上次登入日期高於這個數值的帳號會被移除
MIN_DAY = 360
# 黑名單數量高於這個數值才會清理黑名單列表
FRIEND_NUM = 1000
# 使用者代理，連接失敗時可以嘗試修改
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
