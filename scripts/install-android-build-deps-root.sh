#!/usr/bin/env bash
# 仅负责用 apt 安装「打 APK」所需的系统包，需 root 执行一次即可。
# 用法：sudo bash scripts/install-android-build-deps-root.sh
# 装完后请用普通用户在项目里执行：bash scripts/build-apk-headless.sh
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "请用 root 运行：sudo bash $0" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends openjdk-17-jdk unzip wget

echo "已安装：openjdk-17-jdk、unzip、wget。"
echo "下一步（勿用 root）：在项目根目录执行  bash scripts/build-apk-headless.sh"
