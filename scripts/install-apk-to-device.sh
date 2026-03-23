#!/usr/bin/env bash
# 在 Linux 上：编译并直接安装到已连接的手机 / 模拟器（无需手动拷 APK）。
#
# 双核 / 约 4G：与 android/gradle.properties、scripts/build-apk-headless.sh 一致，默认
# --no-daemon --max-workers=1。更强机器可 GRADLE_LOW_MEM=0。
#
# 前置：
#   - USB 调试已开，或模拟器已启动；执行前可运行: adb devices（应列出 device）
#   - adb 在 PATH 中，或设置 ANDROID_HOME（会用 $ANDROID_HOME/platform-tools/adb）
#
# 用法：
#   ./scripts/install-apk-to-device.sh           # debug，日常调试（默认）
#   ./scripts/install-apk-to-device.sh release    # release（与 assembleRelease 一致）
#
# 无线调试（Android 11+，手机和电脑同局域网）：
#   手机「开发者选项」里用「无线调试」配对后，执行：
#     adb pair IP:配对端口
#     adb connect IP:调试端口
#   再运行本脚本即可。

set -euo pipefail

GRADLE_LOW_MEM="${GRADLE_LOW_MEM:-1}"
gradlew_args=(--no-daemon)
if [[ "$GRADLE_LOW_MEM" == "1" ]]; then
  gradlew_args+=(--max-workers=1)
fi

MODE="${1:-debug}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_DIR="$(cd "$SCRIPT_DIR/../android" && pwd)"

if command -v adb >/dev/null 2>&1; then
  ADB=(adb)
elif [[ -n "${ANDROID_HOME:-}" && -x "$ANDROID_HOME/platform-tools/adb" ]]; then
  ADB=("$ANDROID_HOME/platform-tools/adb")
else
  echo "未找到 adb。请安装 platform-tools 并加入 PATH，或设置 ANDROID_HOME。" >&2
  echo "例如：export ANDROID_HOME=\"\$HOME/android-sdk\"" >&2
  exit 1
fi

mapfile -t DEVICES < <("${ADB[@]}" devices | awk 'NR>1 && $2=="device" { print $1 }')
if [[ ${#DEVICES[@]} -eq 0 ]]; then
  echo "没有已连接的设备。请连接 USB 并允许调试，或先 adb connect。" >&2
  "${ADB[@]}" devices
  exit 1
fi

if [[ ${#DEVICES[@]} -gt 1 ]]; then
  echo "检测到多台设备：${DEVICES[*]}" >&2
  echo "将使用环境变量 ANDROID_SERIAL 指定的设备（若未设置则使用第一台）。" >&2
fi

cd "$ANDROID_DIR"
chmod +x ./gradlew

case "$MODE" in
  debug)
    ./gradlew "${gradlew_args[@]}" installDebug
    echo ""
    echo "已安装 debug 包。"
    ;;
  release)
    ./gradlew "${gradlew_args[@]}" installRelease
    echo ""
    echo "已安装 release 包。"
    ;;
  *)
    echo "用法: $0 [debug|release]" >&2
    exit 1
    ;;
esac

if [[ -z "${SKIP_LAUNCH:-}" ]]; then
  "${ADB[@]}" shell am start -n com.literatureradar.app/.MainActivity >/dev/null 2>&1 || true
  echo "已尝试拉起主界面（设置 SKIP_LAUNCH=1 可跳过）。"
fi
