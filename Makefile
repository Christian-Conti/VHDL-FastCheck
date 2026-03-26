#!/usr/bin/env bash
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
LIBS_DIR="$PREFIX/lib/gnat"
GHDL_RELEASE_URL="https://github.com/ghdl/ghdl/releases/download/v6.0.0/ghdl-gcc-6.0.0-ubuntu24.04-x86_64.tar.gz"
TMP_DIR="/tmp/ghdl_install_$$"

append_to_rc() {
    local line="$1"
    local rc="$HOME/.bashrc"
    [[ "$SHELL" == *"zsh"* ]] && rc="$HOME/.zshrc"
    grep -qF "$line" "$rc" 2>/dev/null || printf '\n# Added by GHDL setup script\n%s\n' "$line" >> "$rc"
}

if [ -x "$PREFIX/bin/ghdl" ] && "$PREFIX/bin/ghdl" --version &>/dev/null; then
    echo "[INFO] GHDL already installed and functional. Skipping."
    exit 0
fi

mkdir -p "$TMP_DIR" "$PREFIX" "$LIBS_DIR"

echo "[INFO] Downloading GHDL..."
curl -fsSL -o "$TMP_DIR/ghdl.tar.gz" "$GHDL_RELEASE_URL" || { echo "[ERROR] Failed to download GHDL."; rm -rf "$TMP_DIR"; exit 2; }
tar -xzf "$TMP_DIR/ghdl.tar.gz" -C "$PREFIX" --strip-components=1 || { echo "[ERROR] Failed to extract GHDL."; rm -rf "$TMP_DIR"; exit 3; }

echo "[INFO] Downloading libgnat via dnf (no sudo)..."
dnf download --destdir="$TMP_DIR" libgnat 2>/dev/null || {
    echo "[INFO] libgnat not in default repos, enabling CRB..."
    dnf download --destdir="$TMP_DIR" --enablerepo=crb libgnat 2>/dev/null || {
        echo "[ERROR] Could not download libgnat. Ask your sysadmin to run: sudo dnf install libgnat"
        rm -rf "$TMP_DIR"; exit 4
    }
}

RPM_FILE=$(ls "$TMP_DIR"/libgnat*.rpm 2>/dev/null | head -1)
[ -z "$RPM_FILE" ] && { echo "[ERROR] No libgnat RPM found."; rm -rf "$TMP_DIR"; exit 5; }

echo "[INFO] Extracting $RPM_FILE..."
pushd "$TMP_DIR" > /dev/null
rpm2cpio "$RPM_FILE" | cpio -idm 2>/dev/null
popd > /dev/null
find "$TMP_DIR" -name "libgnat*.so*" -exec cp -P {} "$LIBS_DIR/" \;

export LD_LIBRARY_PATH="$LIBS_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

"$PREFIX/bin/ghdl" --version &>/dev/null || {
    echo "[ERROR] GHDL not functional. Your system glibc may also be too old."
    echo "        Run: ldd --version"
    rm -rf "$TMP_DIR"; exit 6
}
echo "[INFO] GHDL OK: $("$PREFIX/bin/ghdl" --version | head -1)"

append_to_rc "export PATH=\"$PREFIX/bin:\$PATH\""
append_to_rc "export LD_LIBRARY_PATH=\"$LIBS_DIR\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}\""

rm -rf "$TMP_DIR"
echo "[INFO] Done."
exit 0