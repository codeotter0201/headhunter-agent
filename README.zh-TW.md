# headhunter-agent

[English](README.md) | **繁體中文**

**給 Claude Code 與其他 AI agent 使用的 AI 獵頭。** 可以用在自己的求職，也能同時替很多位候選人操作。建立候選人資料庫、讀取職缺網站、評估每個職缺與每位候選人的適合度、產出中英雙版客製履歷，並追蹤每一次投遞的進度與回饋。

> **狀態：** 開發中。開發藍圖與各功能規格都在 [roadmap epic](https://github.com/codeotter0201/headhunter-agent/issues/3) 追蹤。

## 為什麼需要它

求職過程累積的資料多到很難記清楚：舊履歷、筆記、工作紀錄、證照與 repo，看過的每個職缺、每次投遞的結果，以及下次要修正什麼。`headhunter-agent` 就是你的個人獵頭：你就是它的候選人，它會記住這一切，而且每一條事實都保留出處。獵頭和職涯顧問也能用同一套流程，同時替**很多位候選人**操作。

## 功能

- **候選人資料庫**：關於候選人的任何資料都能交給它：筆記、工作紀錄、照片、舊履歷、GitHub repo。它會檢查每份資料缺了哪些細節、哪些描述太模糊、和既有資料有沒有矛盾，提出追問，並用共用的中英標籤分類每一條事實。每一條事實都保留出處，沒有你確認不會自行補上內容。支援新增、查看、更新、封存，可依技能、產業、職級、工作年資、證據強度或狀態查詢候選人和事實。
- **讀取職缺網站**：貼上 104、CakeResume、Yourator、企業官網或 LinkedIn 的職缺列表網址，先讀標題粗篩，再逐一讀取完整職缺內容並存成快照：必備條件、加分條件、工作內容、薪資與地點，條件會用和候選人事實相同的標籤分類。Yourator 和企業官網直接讀取，並遵守各網站的 robots.txt。104 和 CakeResume 會擋自動化請求，所以改由 skill 引導你：把搜尋結果捲到所有職缺都載入、複製整頁貼上，職缺頁則從你的瀏覽器讀取或用你複製的文字。LinkedIn 只讀你已登入瀏覽器中開啟的頁面或你貼上的文字。
- **適合度與成功率評估**：可針對一位候選人，或從整個資料庫找出適合的人。產出適合度分數、推薦原因、缺口與風險，以及高／中／低的成功率等級與理由。
- **客製履歷**：每個職缺產出中文與英文兩版，Markdown 與 PDF 格式，只使用有出處的事實。
- **投遞進度追蹤**：每組「候選人 × 職缺」依階段推進（發現 → 已評估 → 準備中 → 已投遞 → 面試 → Offer → 結案），附下一步與期限。
- **回饋與修正**：記錄來自 HR、面試官、候選人與獵頭的回饋、原因分類與具體修正方向。重複出現的問題會更新候選人的求職策略，同一家公司的回饋會累積成公司情報，實際結果用來校準評分。

## 安裝

```
/plugin marketplace add codeotter0201/headhunter-agent
/plugin install headhunter@headhunter-agent
```

安裝後在 Claude Code 輸入 `/headhunter`。

skill 的輔助腳本需要 Python 3.9 以上，不需安裝其他套件。匯入 GitHub repo 或個人頁面時會用到 [GitHub CLI](https://cli.github.com)（`gh`）。

其他支援 Agent Skills 格式的 AI agent 也能使用：把 `skills/headhunter/` 複製到該 agent 的 skills 資料夾即可。

## 資料只存在本機

候選人資料永遠不會進入這個 repo，只存在你電腦上的 `~/headhunter-data/`（或 `HEADHUNTER_DATA_DIR` 指定的資料夾），也不會上傳到任何第三方服務。

## 參與開發

開發以 issue 與 PR 進行，人類與 AI agent 依同一套規則協作。請先閱讀 [CONTRIBUTING.md](CONTRIBUTING.md)（英文）；AI agent 先讀 [AGENTS.md](AGENTS.md)。

---

關鍵字：獵頭、猎头、人力仲介、求職、找工作、履歷、客製履歷、職缺評估、職缺媒合、投遞追蹤、面試回饋、人力銀行、104、CakeResume、Claude Code skill

## 授權

[MIT](LICENSE)
