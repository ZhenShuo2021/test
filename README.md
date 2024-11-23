# 巴哈姆特黑名單工具 + 黑名單合輯
管理巴哈黑名單的工具，也包括黑名單合輯清單

![demo](assets/demo.gif "demo")

## 說明
巴哈沒有提供黑名單管理、匯出、匯入的介面，所以自己寫了一個，主要提供這三個功能

1. 根據黑名單來源自動更新黑名單
2. 匯出自己的黑名單
3. 從原有的黑名單中移除特定條件的用戶

特定條件是登入次數小於一定次數或者上次登入日期過久的用戶，因為看到這些用戶的機會很小了，所以移除這些人的黑名單空出給其他人（巴哈黑名單[人數上限 1500](https://forum.gamer.com.tw/C.php?bsn=60404&snA=39366)）。

## 安裝和使用
下載腳本後使用 `pip install -r requirements.txt` 安裝，使用 [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) 選擇 netscape 格式匯出巴哈的 cookie 到同資料夾的 `cookies.txt`，使用 `python run.py` 執行。

有參數和三種模式可以選，使用範例如下，輸入帳號名稱，cookie 檔案路徑，還有只執行更新黑名單和清理黑名單列表

```sh
python run.py --username JackyChen --cookie-path /path/to/cookies.txt --mode update clean
```

如果什麼都不輸入預設三種功能都會執行，使用 `-h` 參數可以看到所有輸入選項，編輯 `constant.py` 可以修改預設值，之後使用指令就不用這麼長。

## 注意事項和使用細節
1. 等待時間久一點讓他慢慢跑沒關係，設定太快對網站來說是攻擊，帳號可能會被 ban。
2. 這個黑名單列表會自動更新，`BLACKLIST_SRC` 預設會根據我的黑名單更新，已經 ban 了很多碎念大師了，也可以用你找到的黑名單列表進行更新。
3. `USERNAME` 設定你的帳號名稱後，在更新黑名單列表時會先抓取原有的黑名單列表並且排除重複名單加速執行。
4. 出現問題先嘗試更新 cookie 檔案，不行再修改 `USER_AGENT`，不會改的話直接叫 GPT 生成一個最新最真實的

## 起因
我只想開心看動畫偏偏有人看動畫一直抱怨= =吐槽劇情跟碎碎念是兩回事欸，把他們都 ban 了之後想說可以分享這個名單，又發現巴哈沒有匯入工具所以自己寫了一個黑單工具。
