# 巴哈姆特黑名單工具 + 黑名單合輯

管理巴哈黑名單的工具，也包括黑名單合輯清單

## 起因

我只想開心看動畫偏偏有人一直抱怨= =吐槽劇情跟碎碎念是兩回事欸，把他們都 ban 了之後想說可以分享這個名單，又發現巴哈沒有匯入工具所以自己寫了一個黑單工具。

https://github.com/user-attachments/assets/1d1640de-eb2d-41ad-b788-e529fc00bbfb

## 說明

巴哈沒有提供黑名單管理、匯出、匯入的介面，所以自己寫了一個，提供以下三個功能

1. 根據黑名單來源自動更新黑名單
2. 匯出自己的黑名單
3. 從原有的黑名單中移除特定條件的用戶

特定條件是登入次數小於一定次數或者上次登入日期過久的用戶，因為看到這些用戶的機會很小了，所以移除這些人的黑名單空出給其他人（巴哈黑名單[人數上限 1500](https://forum.gamer.com.tw/C.php?bsn=60404&snA=39366)）。

## 安裝和使用

下載腳本後

1. 使用 `pip install -r requirements.txt` 安裝
2. 在 `config.json` 修改帳號密碼
3. 使用 `python run.py` 執行，使用範例如下

```sh
python run.py -a <帳號> -p <密碼>
```

如果什麼都不輸入預設的三種功能都會執行，使用 `-h` 參數可以看到所有輸入選項。

## 注意事項

- 登入相關
  1. 預設使用帳號密碼登入，此方式每次使用都會新增一筆[登入紀錄](https://home.gamer.com.tw/setting/login_log.php)，使用 Cookies 則沒有此問題。然而因為 Cookies 有期限，隔一陣子再使用可能就會失效，兩種方法都不完美。
  2. Cookies 登入方式是使用 [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) 匯出 netscape 格式的 cookie 並且儲存到同資料夾的 `cookies.txt`。根據 [aniGamerPlus](https://github.com/miyouzi/aniGamerPlus) 的建議可以使用無痕瀏覽器登入巴哈以取得程式碼專用的 cookies。
  1. 有問題可以先嘗試更新 cookie 檔案以及修改 `user_agent`，可以到 https://www.whatsmyua.info/ 取得後在 `config.json` 修改，或者修改模擬的瀏覽器，兩者相同是最好的，[支援的瀏覽器清單](https://curl-cffi.readthedocs.io/en/latest/impersonate.html)。

- 其他
  1. 等待時間久一點讓他慢慢跑沒關係，設定太快對網站來說是攻擊，帳號可能會被 ban。
  2. 這個黑名單列表會自動更新，`blacklist_src` 預設根據我的黑名單更新，已經 ban 了很多碎念大師了，也可以用你找到的黑名單列表進行更新。

# Disclaimer

This tool is provided "as is," and the creator makes no guarantees regarding the functionality or reliability of the tool. By using this tool, you acknowledge and accept that the use of automated systems may lead to account bans or other negative consequences, and the creator is not responsible for any resulting issues. The tool is intended solely for personal use and must not be used for any illegal activities, commercial purposes, or any action that violates terms of service of any platform. Unauthorized or harmful use of this tool may result in legal action. The creator disclaims any responsibility for damages caused by improper or unintended usage.

# Acknowledgment

The password login functionality is derived from the project "BahaMaster" by davidleitw, available at https://github.com/davidleitw/BahaMaster.
