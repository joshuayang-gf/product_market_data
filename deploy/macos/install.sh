#!/bin/bash
# 把看板安裝成 macOS 開機自動啟動的服務（LaunchDaemon），內網同事可用 http://這台的IP:8000 開啟。
# 可以重複執行：更新程式碼（git pull）之後再跑一次，就會重建環境並重新啟動服務。
#
# 用法：  deploy/macos/install.sh
#         DRY_RUN=1 deploy/macos/install.sh   只檢查環境、印出設定，不做任何變更
# 可選環境變數：PORT（預設 8000）、UPDATE_TIME（08:30）、START_MONTH（2025-01）、ADMIN_TOKEN、
#               KEEP_AWAKE（預設 1，設 0 就不改休眠設定）、HTTPS_PROXY／HTTP_PROXY／NO_PROXY（公司若需 proxy 上網）
# 安裝成功後設定會存在 data/install.env，下次重跑自動沿用；指令上有給的值優先。
set -euo pipefail

LABEL="com.goodfinance.product-market-data"
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="/Library/LaunchDaemons/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/product-market-data"
SETTINGS="$APP_DIR/data/install.env"
SETTING_KEYS="PORT UPDATE_TIME START_MONTH ADMIN_TOKEN KEEP_AWAKE HTTPS_PROXY HTTP_PROXY NO_PROXY"
DRY_RUN="${DRY_RUN:-0}"
RUN_USER="$(id -un)"

if [ -f "$SETTINGS" ]; then
  while IFS='=' read -r key value; do
    case " $SETTING_KEYS " in
      *" $key "*) [ -n "${!key:-}" ] || printf -v "$key" '%s' "$value" ;;
    esac
  done < "$SETTINGS"
fi
PORT="${PORT:-8000}"
UPDATE_TIME="${UPDATE_TIME:-08:30}"
START_MONTH="${START_MONTH:-2025-01}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"
KEEP_AWAKE="${KEEP_AWAKE:-1}"
HTTPS_PROXY="${HTTPS_PROXY:-${https_proxy:-}}"
HTTP_PROXY="${HTTP_PROXY:-${http_proxy:-}}"
NO_PROXY="${NO_PROXY:-${no_proxy:-}}"

say() { printf '\n==> %s\n' "$*"; }
die() { printf '\n[錯誤] %s\n' "$*" >&2; exit 1; }
xml() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }

[ "$(uname)" = Darwin ] || die "這支腳本只支援 macOS"
[ "$(id -u)" -ne 0 ] || die "請用一般使用者執行（不要加 sudo），需要時腳本會自己詢問密碼"
case "$APP_DIR" in
  "$HOME/Desktop"* | "$HOME/Documents"* | "$HOME/Downloads"*)
    die "程式放在 ${APP_DIR}，macOS 會擋背景服務讀取「桌面／文件／下載」。請移到家目錄（例如 ~/product_market_data）再執行。" ;;
esac

say "1/6 尋找 Python 3.10 以上"
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
  p="$(command -v "$c" 2>/dev/null || true)"
  if [ -n "$p" ] && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then PY="$p"; break; fi
done
[ -n "$PY" ] || die "找不到 Python 3.10 以上（macOS 內建的是 3.9）。請先到 https://www.python.org/downloads/macos/ 下載安裝 Python 3.12，再重新執行。"
echo "    使用 ${PY}（$("$PY" --version 2>&1)）"

say "2/6 檢查能否連到資料來源"
unreachable=0
for u in https://www.tpex.org.tw/zh-tw/ https://www.twsa.org.tw/E01/E011.html https://mopsfin.twse.com.tw/; do
  if curl -sS -o /dev/null --max-time 20 -A "Mozilla/5.0" "$u" 2>/dev/null; then echo "    OK    $u"
  else echo "    連不到 $u"; unreachable=1; fi
done
[ "$unreachable" = 0 ] || echo "    ⚠️ 有來源連不到：服務仍會安裝，但資料會下載失敗。若公司要透過 proxy 上網，請設定 HTTPS_PROXY 後重新執行。"

env_xml=""
add_env() { [ -n "${2:-}" ] && env_xml+="        <key>$1</key><string>$(printf '%s' "$2" | xml)</string>"$'\n' || true; }
add_env TZ "Asia/Taipei"
add_env UPDATE_TIME "$UPDATE_TIME"
add_env START_MONTH "$START_MONTH"
add_env ADMIN_TOKEN "$ADMIN_TOKEN"
add_env HTTPS_PROXY "$HTTPS_PROXY"
add_env HTTP_PROXY "$HTTP_PROXY"
add_env NO_PROXY "$NO_PROXY"
APP_XML="$(printf '%s' "$APP_DIR" | xml)"
LOG_XML="$(printf '%s' "$LOG_DIR" | xml)"

TMP_PLIST="$(mktemp)"
trap 'rm -f "$TMP_PLIST"' EXIT
cat > "$TMP_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>UserName</key><string>$RUN_USER</string>
    <key>WorkingDirectory</key><string>$APP_XML</string>
    <key>ProgramArguments</key>
    <array>
        <string>$APP_XML/.venv/bin/uvicorn</string>
        <string>app.main:app</string>
        <string>--host</string><string>0.0.0.0</string>
        <string>--port</string><string>$PORT</string>
        <string>--workers</string><string>1</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
$env_xml    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>30</integer>
    <key>StandardOutPath</key><string>$LOG_XML/server.log</string>
    <key>StandardErrorPath</key><string>$LOG_XML/server.log</string>
</dict>
</plist>
EOF
plutil -lint "$TMP_PLIST" >/dev/null || die "產生的服務設定檔格式錯誤"

if [ "$DRY_RUN" = 1 ]; then
  say "DRY_RUN：以下是會安裝到 $PLIST 的設定，未做任何變更"
  cat "$TMP_PLIST"
  exit 0
fi

say "3/6 停止舊的服務（第一次安裝會略過）"
echo "    接下來需要管理員權限，請輸入這台 Mac 的登入密碼"
sudo -v
sudo launchctl bootout "system/$LABEL" 2>/dev/null && { echo "    已停止"; sleep 2; } || echo "    沒有執行中的服務"
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  die "Port $PORT 已被其他程式使用，請用 PORT=8080 deploy/macos/install.sh 換一個 port"
fi

say "4/6 建立 Python 環境並安裝套件（約 1 分鐘）"
"$PY" -m venv --clear "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --disable-pip-version-check -r "$APP_DIR/requirements.txt"

say "5/6 安裝並啟動服務"
mkdir -p "$LOG_DIR"
sudo install -m 600 -o root -g wheel "$TMP_PLIST" "$PLIST"
sudo launchctl bootstrap system "$PLIST"
sudo launchctl enable "system/$LABEL"

say "6/6 防火牆與休眠設定"
FW=/usr/libexec/ApplicationFirewall/socketfilterfw
if "$FW" --getglobalstate | grep -q "enabled"; then
  real="$("$APP_DIR/.venv/bin/python" -c 'import os, sys; print(os.path.realpath(sys._base_executable))')"
  # Framework builds (python.org / Homebrew) run as Python.app, so allow both binaries.
  for b in "$real" "$(dirname "$real")/../Resources/Python.app/Contents/MacOS/Python"; do
    [ -x "$b" ] || continue
    b="$(cd "$(dirname "$b")" && pwd)/$(basename "$b")"
    sudo "$FW" --add "$b" >/dev/null && sudo "$FW" --unblockapp "$b" >/dev/null
    echo "    防火牆已允許連入：$b"
  done
else
  echo "    防火牆未開啟，略過"
fi
if [ "$KEEP_AWAKE" = 1 ]; then
  sudo pmset -c sleep 0 || echo "    ⚠️ 無法關閉睡眠，請到「系統設定 → 能源」手動設定"
  # 停電復電後自動開機；筆電不支援此選項，忽略錯誤
  sudo pmset -a autorestart 1 2>/dev/null || true
  echo "    已設定：接電源時不睡眠、停電後自動開機（桌上型 Mac）"
fi

say "等待服務啟動"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/api/health" 2>/dev/null; then ok=1; break; fi
  sleep 1
done
[ "$ok" = 1 ] || die "服務沒有起來，請看 log：tail -50 \"$LOG_DIR/server.log\""

mkdir -p "$APP_DIR/data"
( umask 077
  for key in $SETTING_KEYS; do
    if [ -n "${!key}" ]; then printf '%s=%s\n' "$key" "${!key}"; fi
  done > "$SETTINGS" )

iface="$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')"
ip="$(ipconfig getifaddr "${iface:-en0}" 2>/dev/null || true)"
cat <<EOF

✅ 安裝完成
    這台電腦：  http://localhost:$PORT
    內網同事：  http://${ip:-這台的IP}:$PORT
               http://$(scutil --get LocalHostName).local:${PORT}（公司網路支援時可用，IP 變動也不受影響）
    Log：      $LOG_DIR/server.log
    第一次啟動會在背景下載歷史資料，大約 1 分鐘後畫面就會有資料。
    更新程式：  cd "$APP_DIR" && git pull && deploy/macos/install.sh（會沿用這次的 port 等設定）
    移除服務：  deploy/macos/uninstall.sh
EOF
