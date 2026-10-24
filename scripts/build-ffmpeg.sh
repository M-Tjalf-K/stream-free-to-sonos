#!/bin/sh
# Run from the repository root in w64devkit 2.10.1 (Windows x64).
# Sources are fetched and SHA-256 checked by prepare-ffmpeg.py.
set -eu
export PATH_SEPARATOR=';'
export CC=gcc
export CONFIG_SHELL=sh.exe
export GREP=grep
export EGREP='grep -E'
export FGREP='grep -F'
export SED=sed
export CFLAGS='-O2 -std=gnu99'
export AR=ar RANLIB=ranlib NM=nm LD=ld STRIP=strip OBJDUMP=objdump DLLTOOL=dlltool
root=$(pwd)
mkdir -p build/ffmpeg-work build/ffmpeg-prefix
cd build/ffmpeg-work
[ -d lame-3.100 ] || tar -xf ../downloads/lame-3.100.tar.gz
[ -d ffmpeg-8.1.3 ] || tar -xf ../downloads/ffmpeg-8.1.3.tar.xz
cd lame-3.100
if [ ! -f "$root/build/ffmpeg-prefix/lib/libmp3lame.a" ]; then
./configure --build=x86_64-w64-mingw32 --host=x86_64-w64-mingw32 --prefix="$root/build/ffmpeg-prefix" \
    --disable-shared --enable-static --disable-frontend --disable-decoder \
    --disable-analyzer-hooks --disable-dependency-tracking
make -j4
make install
fi
cd ../ffmpeg-8.1.3
./configure --target-os=mingw32 --arch=x86_64 --cc=gcc --ar=ar --ranlib=ranlib \
    --disable-autodetect --disable-everything --disable-asm --disable-doc \
    --disable-debug --disable-network --disable-iconv --disable-bzlib --disable-zlib \
    --disable-lzma --disable-sdl2 --disable-ffplay --disable-ffprobe \
    --enable-small --enable-static --disable-shared --enable-ffmpeg \
    --enable-libmp3lame --enable-encoder=libmp3lame --enable-decoder=pcm_s16le \
    --enable-demuxer=pcm_s16le --enable-muxer=mp3 --enable-protocol=pipe \
    --enable-filter=aresample --enable-filter=aformat --enable-filter=anull \
    --extra-cflags="-I$root/build/ffmpeg-prefix/include" \
    --extra-ldflags="-L$root/build/ffmpeg-prefix/lib" \
    --pkg-config=false
make V=1 -j4
mkdir -p "$root/build/ffmpeg"
cp ffmpeg.exe "$root/build/ffmpeg/ffmpeg.exe"
cp "$(dirname "$(command -v gcc)")/../COPYING.MinGW-w64-runtime.txt" "$root/build/ffmpeg/MINGW-RUNTIME-LICENSE.txt"
