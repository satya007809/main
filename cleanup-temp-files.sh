#!/usr/bin/env bash
# cleanup-temp-files.sh
# Scans and optionally removes common temporary and unwanted files.
# Usage: ./cleanup-temp-files.sh [--dry-run | --clean]

set -euo pipefail

MODE="${1:---dry-run}"
TOTAL_SIZE=0

echo "============================================"
echo "  Temp & Unwanted File Cleanup Script"
echo "  Mode: $MODE"
echo "============================================"
echo ""

# --- Helper ---
report() {
    local path="$1"
    if [ -e "$path" ]; then
        local size
        size=$(du -sh "$path" 2>/dev/null | cut -f1)
        echo "  [FOUND] $path ($size)"
    fi
}

remove_if_clean() {
    local path="$1"
    if [ -e "$path" ]; then
        local size
        size=$(du -sh "$path" 2>/dev/null | cut -f1)
        if [ "$MODE" = "--clean" ]; then
            rm -rf "$path" && echo "  [REMOVED] $path ($size)"
        else
            echo "  [WOULD REMOVE] $path ($size)"
        fi
    fi
}

# --- System Info ---
echo ">> System Overview"
echo "  OS:   $(uname -sr 2>/dev/null || echo 'unknown')"
echo "  Disk: $(df -h / 2>/dev/null | tail -1 | awk '{print $3 " used / " $2 " total (" $5 " used)"}')"
echo "  RAM:  $(free -h 2>/dev/null | awk '/Mem:/{print $3 " used / " $2 " total"}' || echo 'unknown')"
echo ""

# --- /tmp ---
echo ">> Scanning /tmp"
if [ -d /tmp ]; then
    for f in /tmp/ruby-build.*.log; do
        [ -e "$f" ] && remove_if_clean "$f"
    done
    [ -d /tmp/hsperfdata_root ] && remove_if_clean "/tmp/hsperfdata_root"
    [ -d /tmp/node-compile-cache ] && remove_if_clean "/tmp/node-compile-cache"
    for f in /tmp/*.core; do
        [ -e "$f" ] && remove_if_clean "$f"
    done
else
    echo "  /tmp not found."
fi
echo ""

# --- /var/tmp ---
echo ">> Scanning /var/tmp"
if [ -d /var/tmp ]; then
    count=$(ls -A /var/tmp 2>/dev/null | wc -l)
    if [ "$count" -gt 0 ]; then
        echo "  Found $count items in /var/tmp"
    else
        echo "  /var/tmp is clean."
    fi
else
    echo "  /var/tmp not found."
fi
echo ""

# --- Package manager caches ---
echo ">> Scanning package manager caches"
if command -v apt-get &>/dev/null; then
    cache_size=$(du -sh /var/cache/apt 2>/dev/null | cut -f1)
    echo "  apt cache: $cache_size"
    if [ "$MODE" = "--clean" ]; then
        apt-get clean 2>/dev/null && echo "  [CLEANED] apt cache" || echo "  [SKIP] apt clean requires root"
    fi
fi
if command -v pip &>/dev/null; then
    pip_cache=$(pip cache dir 2>/dev/null || echo "")
    if [ -n "$pip_cache" ] && [ -d "$pip_cache" ]; then
        cache_size=$(du -sh "$pip_cache" 2>/dev/null | cut -f1)
        echo "  pip cache: $cache_size"
        if [ "$MODE" = "--clean" ]; then
            pip cache purge 2>/dev/null && echo "  [CLEANED] pip cache" || true
        fi
    fi
fi
if command -v npm &>/dev/null; then
    npm_cache=$(npm cache ls 2>/dev/null | wc -l || echo 0)
    echo "  npm cache entries: $npm_cache"
    if [ "$MODE" = "--clean" ]; then
        npm cache clean --force 2>/dev/null && echo "  [CLEANED] npm cache" || true
    fi
fi
echo ""

# --- Log files ---
echo ">> Scanning log files"
report "/var/log"
echo ""

# --- Summary ---
echo ">> Disk after scan:"
df -h / 2>/dev/null | tail -1 | awk '{print "  " $3 " used / " $2 " total (" $5 " used)"}'
echo ""

if [ "$MODE" = "--dry-run" ]; then
    echo "This was a DRY RUN. To actually remove files, run:"
    echo "  ./cleanup-temp-files.sh --clean"
fi

echo ""
echo "Done."
