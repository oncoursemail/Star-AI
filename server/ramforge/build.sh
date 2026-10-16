#!/bin/bash
# Build the RAMForge test binaries next to (never over) the live llama.cpp build. Run as user star on server 1.
#   SRC   live source tree to copy (default /opt/star/src/llama.cpp, b11541 f2918cabb)
#   DST   new tree (default /opt/star/src/llama.cpp-ramforge)
# The resulting binaries behave exactly like b11541 unless GGML_NUMA_BLOCK / LLAMA_RAMFORGE_PLACE /
# GGML_RF_BARRIER / GGML_RF_PROFILE are set in their environment.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=${SRC:-/opt/star/src/llama.cpp}
DST=${DST:-/opt/star/src/llama.cpp-ramforge}
if [ ! -d "$DST" ]; then
  mkdir -p "$DST"
  tar -C "$SRC" --exclude=./build --exclude=./.git -cf - . | tar -C "$DST" -xf -
  (cd "$DST" && git init -q && git -c user.name=ramforge -c user.email=ramforge@localhost add -A >/dev/null \
     && git -c user.name=ramforge -c user.email=ramforge@localhost commit -qm base)
fi
cd "$DST"
git checkout -q -- ggml src tools/server
git apply "$HERE/patches/0001-ramforge-numa-local-b11541.patch"
# Issue 118: upstream b11583 fix, a request pinned to a busy slot no longer loads its cached prompt into that slot.
git apply "$HERE/patches/0002-server-busy-pinned-slot-untouched.patch"
nice -n 19 cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_OPENMP=ON -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF
nice -n 19 cmake --build build -j "${JOBS:-8}" --target llama-server llama-bench llama-imatrix
gcc -O3 -march=native -pthread "$HERE/numa_bw.c" -o "$HERE/numa_bw"
echo "built: $DST/build/bin"
