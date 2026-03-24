#!/usr/bin/env bash
# 为 4G 内存等小内存机器增加专用 swap，降低 Gradle 打 APK 时 OOM 概率。
# 用法：sudo bash scripts/setup-swap-for-apk-build.sh
#
# 默认：若系统当前 SwapTotal 已 ≥ SWAP_MIN_GiB（默认 2），则不做任何事。
# 否则在 SWAP_FILE（默认 /var/swap-literature-build）创建 SWAP_FILE_SIZE（默认 2G）并 swapon，
# 并写入 /etc/fstab（幂等，不重复追加）。
#
# 环境变量（可选）：
#   SWAP_MIN_GiB=2       低于此总 swap（GiB）才尝试添加
#   SWAP_FILE_SIZE=2G    fallocate/dd 大小（仅支持整数 GiB，如 2G、3G）
#   SWAP_FILE=/var/swap-literature-build
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "请用 root 运行：sudo bash $0" >&2
  exit 1
fi

SWAP_MIN_GiB="${SWAP_MIN_GiB:-2}"
SWAP_FILE="${SWAP_FILE:-/var/swap-literature-build}"
SWAP_FILE_SIZE="${SWAP_FILE_SIZE:-2G}"

swap_total_kb() {
  awk '/^SwapTotal:/ {print $2}' /proc/meminfo
}

swapfile_is_active() {
  awk -v p="$1" '$1 == p {found=1} END { exit !found }' /proc/swaps 2>/dev/null
}

min_kb=$((SWAP_MIN_GiB * 1024 * 1024))
cur_kb="$(swap_total_kb)"
if (( cur_kb >= min_kb )); then
  echo "Swap 合计已 ≥ ${SWAP_MIN_GiB} GiB（当前约 $((cur_kb / 1024)) MiB），无需新增。"
  exit 0
fi

if [[ -f "$SWAP_FILE" ]] && swapfile_is_active "$SWAP_FILE"; then
  echo "错误：$SWAP_FILE 已在用，但 SwapTotal 仍低于 ${SWAP_MIN_GiB} GiB。" >&2
  echo "请增大交换文件，例如：" >&2
  echo "  sudo swapoff $SWAP_FILE && sudo rm -f $SWAP_FILE && sudo SWAP_FILE_SIZE=3G bash $0" >&2
  exit 1
fi

if [[ -f "$SWAP_FILE" ]] && ! swapfile_is_active "$SWAP_FILE"; then
  echo "启用已有交换文件 $SWAP_FILE …" >&2
  swapon "$SWAP_FILE" 2>/dev/null || true
  cur_kb="$(swap_total_kb)"
  if (( cur_kb >= min_kb )); then
    echo "当前 SwapTotal 约 $((cur_kb / 1024)) MiB，已达标。"
    exit 0
  fi
  echo "仅有该文件仍不足，将删除后按 ${SWAP_FILE_SIZE} 重建…" >&2
  swapoff "$SWAP_FILE" 2>/dev/null || true
  rm -f "$SWAP_FILE"
fi

need_dir="$(dirname "$SWAP_FILE")"
mkdir -p "$need_dir"
avail_kb="$(df -Pk "$need_dir" | awk 'NR==2 {print $4}')"
# 预留约 256MiB
if [[ ! "$SWAP_FILE_SIZE" =~ ^[0-9]+G$ ]]; then
  echo "SWAP_FILE_SIZE 请使用整数 GiB，例如 2G、3G（当前：$SWAP_FILE_SIZE）" >&2
  exit 1
fi
gib="${SWAP_FILE_SIZE%G}"
want_kb=$((gib * 1024 * 1024))
if (( avail_kb < want_kb + 262144 )); then
  echo "错误：$need_dir 可用空间不足（约需 ${want_kb} KiB + 余量）。" >&2
  exit 1
fi

echo "当前 SwapTotal 约 $((cur_kb / 1024)) MiB；创建 ${SWAP_FILE_SIZE} 交换文件 $SWAP_FILE …" >&2
rm -f "$SWAP_FILE"
if ! fallocate -l "$SWAP_FILE_SIZE" "$SWAP_FILE" 2>/dev/null; then
  echo "fallocate 失败，改用 dd（较慢）…" >&2
  count=$((gib * 1024))
  dd if=/dev/zero of="$SWAP_FILE" bs=1M count="$count" status=progress
fi
chmod 600 "$SWAP_FILE"
mkswap "$SWAP_FILE"
swapon "$SWAP_FILE"

fstab_line="$SWAP_FILE none swap sw 0 0"
if ! grep -qF "$SWAP_FILE" /etc/fstab 2>/dev/null; then
  echo "$fstab_line" >>/etc/fstab
  echo "已追加 fstab：$fstab_line"
else
  echo "fstab 中已存在 $SWAP_FILE 相关项，未重复写入。"
fi

cur_kb="$(swap_total_kb)"
echo "完成。当前 SwapTotal 约 $((cur_kb / 1024)) MiB。"
