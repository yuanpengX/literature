#!/usr/bin/env bash
# 下载 Android commandline-tools、安装 SDK 组件并用 Gradle 打出 release APK。
# 系统依赖（JDK 等）请先执行（一次即可）：sudo bash scripts/install-android-build-deps-root.sh
# 可用 root 或普通用户运行；root 时默认 ANDROID_HOME=/root/android-sdk。
#
# 双核 / 约 4G 内存：与 android/gradle.properties 中的堆上限、workers、Kotlin daemon 配合；
# 本脚本对 Gradle 再强制 --max-workers=1。若仍 OOM，请先加 swap 或减少同时运行的服务。
# 机器更强时可设 GRADLE_LOW_MEM=0 去掉额外 worker 限制（仍建议保留 gradle.properties 按需调大内存）。
set -euo pipefail

GRADLE_LOW_MEM="${GRADLE_LOW_MEM:-1}"

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

gradlew_args=(--no-daemon)
if [[ "$GRADLE_LOW_MEM" == "1" ]]; then
  gradlew_args+=(--max-workers=1)
fi
./gradlew "${gradlew_args[@]}" assembleRelease

# Gradle 会将 APK 同步到 android/apk/（浅路径）；否则回退默认输出目录
SHALLOW_DIR="$ANDROID_DIR/apk"
REL_DIR="$ANDROID_DIR/app/build/outputs/apk/release"
APK=""
[[ -f "$SHALLOW_DIR/app-release.apk" ]] && APK="$SHALLOW_DIR/app-release.apk"
[[ -z "$APK" && -f "$SHALLOW_DIR/app-release-unsigned.apk" ]] && APK="$SHALLOW_DIR/app-release-unsigned.apk"
[[ -z "$APK" && -f "$REL_DIR/app-release.apk" ]] && APK="$REL_DIR/app-release.apk"
[[ -z "$APK" && -f "$REL_DIR/app-release-unsigned.apk" ]] && APK="$REL_DIR/app-release-unsigned.apk"
if [[ -n "$APK" ]]; then
  echo "APK: $APK"
  ls -la "$APK"
else
  echo "未找到 release APK，请查看上方 Gradle 报错。" >&2
  exit 1
fi
