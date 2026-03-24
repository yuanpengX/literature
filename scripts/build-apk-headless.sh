#!/usr/bin/env bash
# 下载 Android commandline-tools、安装 SDK 组件并用 Gradle 打出 release APK。
# 系统依赖（JDK 等）请先执行（一次即可）：sudo bash scripts/install-android-build-deps-root.sh
# 可用 root 或普通用户运行；root 时默认 ANDROID_HOME=/root/android-sdk。
#
# 目标环境：约 4G 内存 VPS，构建 JVM 预算约 ≤2GiB（见 android/gradle.properties）+ 建议系统总 swap ≥2GiB。
# 脚本侧：--no-daemon、默认 --max-workers=1；首次部署请 sudo bash scripts/setup-swap-for-apk-build.sh（install-android-build-deps-root 也会调用）。
# 若仍 OOM：停掉 Docker 等占内存服务后再打包，或略增大 swap / 按 gradle.properties 注释微调 Metaspace。
# 机器更强时可设 GRADLE_LOW_MEM=0；swap 不足时可 SKIP_SWAP_CHECK=1 强行继续（不推荐）。
set -euo pipefail

GRADLE_LOW_MEM="${GRADLE_LOW_MEM:-1}"
MIN_SWAP_KB=$((2048 * 1024)) # 2 GiB

if [[ "${SKIP_SWAP_CHECK:-0}" != "1" ]]; then
  swap_kb="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
  if (( swap_kb < MIN_SWAP_KB )); then
    echo "当前 SwapTotal 约 $((swap_kb / 1024)) MiB，低于建议的 2 GiB，Gradle 打 APK 容易内存不足被系统杀进程。" >&2
    echo "请执行（root）：sudo bash scripts/setup-swap-for-apk-build.sh" >&2
    echo "若已手动配置足够 swap 仍误报：SKIP_SWAP_CHECK=1 bash $0" >&2
    exit 1
  fi
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

gradlew_args=(--no-daemon)
if [[ "$GRADLE_LOW_MEM" == "1" ]]; then
  gradlew_args+=(--max-workers=1)
fi
# JVM/并行策略以 android/gradle.properties 为准（约 4G 机 / 2G 构建预算 profile）
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
