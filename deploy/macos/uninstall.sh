#!/bin/bash
# 停止並移除 install.sh 安裝的服務。資料（data/）與程式碼都會保留。
set -euo pipefail

LABEL="com.goodfinance.product-market-data"
PLIST="/Library/LaunchDaemons/$LABEL.plist"
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

sudo launchctl bootout "system/$LABEL" 2>/dev/null && echo "已停止服務" || echo "服務本來就沒有在執行"
sudo rm -f "$PLIST"
echo "已移除開機自動啟動設定。資料仍保留在 $APP_DIR/data（分戶帳歷史只存在這裡，刪除前請先備份）。"
echo "防火牆與休眠設定沒有還原，如需調整請到「系統設定」修改。"
