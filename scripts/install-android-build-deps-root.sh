#!/usr/bin/env bash
# 仅负责用 apt 安装「打 APK」所需的系统包，需 root 执行一次即可。
# 用法：sudo bash scripts/install-android-build-deps-root.sh
# 装完后在项目里执行：bash scripts/build-apk-headless.sh（root 或普通用户均可）
#
# 双核 / 约 4G 内存：
#   - 使用 openjdk-17-jdk-headless，减少无关图形依赖占用磁盘与 apt 体积。
#   - 若 apt 报 lock：脚本会默认等待锁释放（见 wait_dpkg_unlock）；也可设置 APT_LOCK_WAIT_MAX=3600 调整上限秒数。
#   - 若不想等待：SKIP_APT_LOCK_WAIT=1（锁仍存在时 apt 仍会失败，仅跳过轮询）。
#   - 另一终端可看进度：systemctl status unattended-upgrades 或 ps aux | grep unattended
#   - 打 APK 前建议总 swap ≥2GiB；本脚本结束时会尝试执行 scripts/setup-swap-for-apk-build.sh（也可用 SKIP_SETUP_SWAP=1 跳过）。
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "请用 root 运行：sudo bash $0" >&2
  exit 1
fi

# 等待 unattended-upgrades / 其他 apt 进程释放 dpkg 锁（避免立刻失败）
wait_dpkg_unlock() {
  [[ "${SKIP_APT_LOCK_WAIT:-0}" == "1" ]] && return 0
  local max="${APT_LOCK_WAIT_MAX:-1800}"
  local step=5
  local t=0
  # 优先用 fuser 检测锁文件（安装本脚本依赖后会装上 psmisc，下次更可靠）
  if command -v fuser >/dev/null 2>&1; then
    while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
      || fuser /var/lib/dpkg/lock >/dev/null 2>&1 \
      || fuser /var/lib/apt/lists/lock >/dev/null 2>&1; do
      if (( t == 0 )); then
        echo "dpkg/apt 正被占用（常见为 unattended-upgrades），每 ${step}s 检查一次，最多等待 ${max}s…" >&2
        echo "（另开终端可查看：systemctl status unattended-upgrades）" >&2
      elif (( t % 60 == 0 )); then
        echo "…已等待 ${t}s，锁仍被占用。占用进程：" >&2
        fuser -v /var/lib/dpkg/lock-frontend 2>/dev/null || true
        pgrep -a unattended-upgr 2>/dev/null || true
        pgrep -a 'apt-get' 2>/dev/null || true
        pgrep -a dpkg 2>/dev/null || true
      fi
      sleep "$step"
      t=$((t + step))
      if (( t > max )); then
        echo "等待 dpkg 锁超时（${max}s）。请待系统自动更新结束后再运行本脚本。" >&2
        echo "若确认无人值守更新已卡死，可在评估风险后：sudo systemctl stop unattended-upgrades，再重试。" >&2
        return 1
      fi
    done
    return 0
  fi
  # 无 fuser 时：根据常见占用进程轮询（弱于锁文件检测，首跑仍可能竞态）
  while pgrep -x unattended-upgr >/dev/null 2>&1 \
    || pgrep -x apt-get >/dev/null 2>&1 \
    || pgrep -x apt >/dev/null 2>&1 \
    || pgrep -x dpkg >/dev/null 2>&1; do
    if (( t == 0 )); then
      echo "检测到 apt/dpkg 相关进程在运行，每 ${step}s 重试，最多 ${max}s（建议安装 psmisc 以精确等待锁）…" >&2
      echo "（另开终端可查看：systemctl status unattended-upgrades）" >&2
    elif (( t % 60 == 0 )); then
      echo "…已等待 ${t}s，相关进程仍在运行：" >&2
      pgrep -a unattended-upgr 2>/dev/null || true
      pgrep -a apt 2>/dev/null || true
      pgrep -a dpkg 2>/dev/null || true
    fi
    sleep "$step"
    t=$((t + step))
    if (( t > max )); then
      echo "等待超时（${max}s）。请稍后重试。" >&2
      echo "若确认无人值守更新已卡死，可在评估风险后：sudo systemctl stop unattended-upgrades，再重试。" >&2
      return 1
    fi
  done
}

wait_dpkg_unlock

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
  psmisc openjdk-17-jdk-headless unzip wget

echo "已安装：psmisc、openjdk-17-jdk-headless、unzip、wget。"

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${SKIP_SETUP_SWAP:-0}" != "1" && -f "$THIS_DIR/setup-swap-for-apk-build.sh" ]]; then
  echo "配置打 APK 用 swap（若总 swap 已 ≥2GiB 会自动跳过）…" >&2
  bash "$THIS_DIR/setup-swap-for-apk-build.sh" || echo "swap 配置未完全成功，可稍后手动：sudo bash scripts/setup-swap-for-apk-build.sh" >&2
fi

echo "下一步：在项目根目录执行  bash scripts/build-apk-headless.sh"
