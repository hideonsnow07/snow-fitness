# SNOW 健身

訓練紀錄、飲食熱量、冰箱食譜的合併版。用 `build/build.py` 組裝，不要手改 `dist/index.html`。

## 組裝

```bash
ln -sfn ../src build/src
python3 build/build.py
mkdir -p dist
cp build/dist/index.html dist/index.html
```

來源頁在 `src/`（`gym.html`、`diet.html`、`fridge.html`），外殼在 `build/shell.html`。

## 資料

日常餐點與訓練寫在合併版資料庫，不要寫回三個來源頁。不要刪合併版紀錄。

目前線上使用中的雲端紀錄仍在 claude.ai 的「SNOW 健身」。靜態網頁在沒有 Claude 資料庫時，各模組會退回瀏覽器 localStorage；跨裝置同步與「問 Claude 估熱量」不會自動跟著走。
