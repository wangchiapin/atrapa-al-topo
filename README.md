# 🍄 打地鼠學中文（Atrapa al Topo）

馬力歐風格的「打地鼠」中文學習遊戲，給說西班牙語的華語學習者使用。
介面是「中文在前、你選的語言（西文／英文）接在後面變小字」的雙語介面，中文會跟著繁體／簡體設定。
整體是無印風：米白底、細框線、柔和的灰綠草地，只有「目前要打的詞」用重點色標出來。
地鼠頭上的字卡是**完整的詞**（不是單字），玩家要依照句子的順序，一個詞一個詞打下去。

👉 遊戲網址（GitHub Pages）：https://wangchiapin.github.io/atrapa-al-topo/

## 怎麼玩

1. 按「開始」開始，系統會念出一句中文，地鼠上方的題目橫幅顯示這句話：字很大，每個詞上面依設定標拼音或注音（句子太長會自動縮小字級，橫幅高度固定不會跳動）。
2. 地鼠會從洞裡冒出來，頭上有字卡。依照句子的順序打出正確的詞。
3. 打完整句就放煙火，換下一句。時間 2 分鐘，看你能完成幾句。
4. 地鼠上有時會出現**沒有字卡的驚喜地鼠**（約 10%），打了不算分也不算錯。
5. 打錯順序：地鼠頭暈、字卡抖一下、發出短短的「噗」，題目列正在等的字會跳一下。連續打錯 3 次，該字會發光並放大（只放大字，不會改變橫幅高度），橫幅左上角的說明也會改成「找發光的字」。
6. 🔊 按鈕可以再聽一次整句（電腦版在題目橫幅右邊；手機直式縮小後和計時器一起放在橫幅右上角，讓句子用滿整個橫幅寬度）。
7. 時間到之後，結果畫面會列出這局完成的句子：中文、拼音／注音、西班牙文翻譯（介面選「只有中文」時不顯示翻譯），每句都能再聽一次。
8. 遊戲中可按「重新開始」，回到設定畫面換選項（中途離開不會顯示成績，也不會進排行榜）。

## 句庫等級（設定 → 句庫等級）

- 只有 **A1／A2／B1** 三個等級（預設 A1）。句子來自新句庫（各 100 句，`https://wangchiapin.github.io/corre/bank/sentences.json`，原稿與工具在 game-kit 的 `bank/`）。
  題目與干擾詞都只用該等級的句子，所以選 A1 時干擾詞只會是 A1 的詞。
- 舊的公開題庫（Firebase）不再讓玩家選；只有新句庫讀不到時才自動當備用（這時設定裡不顯示等級）。開頁時不會再讀 Firebase。
- 選擇存在 `moleSettings` 的 `level`（和 `diff` 放一起）；遊戲中不能改。排行榜目前不分等級（只分難度）。

## 計分與排行榜

- **分數 ＝ 完成句數 × 100 ＋ 準確度加分**。準確度加分 ＝ 準確度 × 50（最多 50 分，至少完成 1 句才給）。
  準確度 ＝ 打對的詞 ÷（打對的詞 ＋ 打錯的次數）；驚喜地鼠不算，時間到時沒打完的那一句不算。
- **暱稱**：第一次按「開始」會跳出視窗輸入暱稱（最多 12 字，沒填就是 `Jugador`），按視窗裡的「開始」（或 Enter）就直接開始遊戲。
  暱稱存在瀏覽器，之後可以在設定裡改。
- **排行榜**：簡單／普通／困難各一份，各顯示前 10 名，繁體與簡體不分開。設定面板和結算畫面都有「排行榜」按鈕；結算畫面會顯示這局的分數、準確度、名次。
- 同一個暱稱（不分大小寫）在同一個難度只留最高分，分數比較低的那局不會蓋掉。
- 一局沒完成任何句子（0 分）不會送出成績。

### 目前狀態：先用「這台裝置」的排行榜

排行榜的畫面和資料層都做好了，現在資料存在這台瀏覽器（localStorage），所以只有自己看得到。
Firebase 版本也已經寫好（`FirestoreBoard`），只是預設關著。接上 Firebase 的步驟：

1. 把 `index.html` 裡的 `LEADERBOARD.useFirebase` 從 `false` 改成 `true`（collection 是 `moleScores`，和「跑吧！漢字」的 `mandarinRunnerScores` 分開，放在同一個專案 corre-d16da）。
2. 到 Firebase 主控台 → Firestore → 規則，加入下面這段（保留原本其他 collection 的規則）。
3. 第一次打開排行榜時，瀏覽器主控台（Console）會有一則錯誤，附一個「建立索引」的連結，點下去建立即可（`difficulty` 升冪 ＋ `score` 降冪）。

```
match /moleScores/{id} {
  allow read: if true;
  allow create: if validScore(request.resource.data);
  allow update: if validScore(request.resource.data)
                && request.resource.data.score > resource.data.score;   // 只能往上更新
  allow delete: if false;
}
function validScore(d) {
  return d.keys().hasOnly(['name','score','sentences','accuracy','difficulty','script','updatedAt'])
      && d.name is string && d.name.size() >= 1 && d.name.size() <= 24
      && d.score is int && d.score >= 0 && d.score <= 3050
      && d.sentences is int && d.sentences >= 0 && d.sentences <= 30
      && d.accuracy is int && d.accuracy >= 0 && d.accuracy <= 100
      && d.difficulty in ['easy','normal','hard']
      && d.script in ['zh-TW','zh-CN'];
}
```

這套規則能擋掉亂填的資料和超出合理範圍的分數，但沒有登入機制，所以擋不住有心人直接在合理範圍內灌分；一般班級／朋友使用已經夠用。

資料格式（每個難度、每個暱稱一份文件，文件 ID 是 `難度__暱稱小寫`）：`name`、`score`、`sentences`、`accuracy`（0–100）、`difficulty`、`script`、`updatedAt`。

## 設定

| 項目 | 選項 |
|---|---|
| 介面語言 | 中文＋Español / 中文＋English / 只有中文（只有中文時，介面和結果畫面都不顯示西文／英文，也不顯示句子翻譯） |
| 中文字 | 繁體 / 簡體 |
| 讀音 | 拼音 / 注音 / 兩個都顯示 / 不顯示（預設拼音） |
| 語速 | 慢 0.45 / 普通 0.65 / 快 0.85（預設普通） |
| 難度 | 簡單 / 普通 / 困難（同時出現的地鼠數與停留時間不同） |

設定和暱稱會記在瀏覽器裡，下次打開還在。中文字、介面語言、讀音、語速和其他遊戲共用同一份設定（localStorage 鑰匙 `hanziGames.settings`，寫入時會合併、不會蓋掉其他遊戲的欄位，多個分頁會同步）；難度和暱稱只屬於這個遊戲。第一次打開時，會把舊的 `moleSettings` 自動搬到共用設定。

## 特色

- 手機（直式、橫式）、平板、電腦都能玩；手機的設定收在 ⚙ 彈出視窗。
- 句子來自 Firebase 句子庫（collection `mandarinRunnerSentences`），每次隨機讀 25 句，剩 5 句以下才在背景補讀，節省讀取次數。
- 連不上資料庫時，會自動使用 3 句內建句子。
- 使用瀏覽器內建語音念字（語速可選慢／普通／快 = 0.45／0.65／0.85），不管選繁體或簡體，一律念台灣讀音（zh-TW），並明確挑台灣的聲音；裝置沒有台灣聲音時才改用其他國語聲音（廣東話排除）。
- 拼音自動轉注音。

## 技術

單一檔案 `index.html`，純 HTML／CSS／JavaScript，沒有建置步驟。
Firebase Firestore（compat SDK）讀取句子。地鼠、洞、槌子都是內嵌 SVG；音效用 WebAudio 合成。

本機測試：直接用瀏覽器打開 `index.html` 即可。

## 句子資料格式

每筆文件包含：`trad[]`、`simp[]`、`pinyin[]`（每個詞一項）與 `es`（西班牙文翻譯）。
