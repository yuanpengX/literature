#!/usr/bin/env bash
# 下载 Android commandline-tools、安装 SDK 组件并用 Gradle 打出 release APK。
# 无需 root；请先执行（一次即可）：sudo bash scripts/install-android-build-deps-root.sh
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "请勿用 root 运行本脚本；请用普通用户执行，避免 Gradle/SDK 文件属主混乱。" >&2
  echo "若尚未安装 JDK/unzip/wget，请先：sudo bash scripts/install-android-build-deps-root.sh" >&2
  exit 1
fi

if ! command -v java >/dev/null 2>&1; then
  echo "未找到 java。请先执行：sudo bash scripts/install-android-build-deps-root.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ANDROID_DIR="$ROOT_DIR/android"

export ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
mkdir -p "$ANDROID_HOME/cmdline-tools"

# Google 官方 commandline-tools（若下载慢，可在有代理的机器下载后放到 /tmp）
CMDLINE_ZIP="${CMDLINE_ZIP:-commandlinetools-linux-11076708_latest.zip}"
CMDLINE_URL="https://dl.google.com/android/repository/${CMDLINE_ZIP}"
if [[ ! -f "/tmp/${CMDLINE_ZIP}" ]]; then
  wget -nv -O "/tmp/${CMDLINE_ZIP}" "$CMDLINE_URL"
fi
rm -rf /tmp/cmdline-tools-extract
unzip -q -o "/tmp/${CMDLINE_ZIP}" -d /tmp/cmdline-tools-extract
rm -rf "$ANDROID_HOME/cmdline-tools/latest"
mkdir -p "$ANDROID_HOME/cmdline-tools/latest"
mv /tmp/cmdline-tools-extract/cmdline-tools/* "$ANDROID_HOME/cmdline-tools/latest/"

SDKMGR="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"

# sdkmanager 接受完许可后会关 stdin，yes 向已关闭的管道写会收到 SIGPIPE(141)；
# 在 pipefail 下整条管道的退出码会变成 141，需视为成功。
yes | "$SDKMGR" --sdk_root="$ANDROID_HOME" --licenses >/dev/null || {
  _lic=$?
  [[ $_lic -eq 141 ]] || exit "$_lic"
}
"$SDKMGR" --sdk_root="$ANDROID_HOME" \
  "platform-tools" "platforms;android-35" "build-tools;35.0.0"

echo "sdk.dir=$ANDROID_HOME" >"$ANDROID_DIR/local.properties"

cd "$ANDROID_DIR"
chmod +x ./gradlew
./gradlew --no-daemon assembleRelease

REL_DIR="$ANDROID_DIR/app/build/outputs/apk/release"
APK=""
[[ -f "$REL_DIR/app-release.apk" ]] && APK="$REL_DIR/app-release.apk"
[[ -z "$APK" && -f "$REL_DIR/app-release-unsigned.apk" ]] && APK="$REL_DIR/app-release-unsigned.apk"
if [[ -n "$APK" ]]; then
  echo "APK: $APK"
  ls -la "$APK"
else
  echo "未找到 release APK，请查看上方 Gradle 报错。" >&2
  exit 1
fi
