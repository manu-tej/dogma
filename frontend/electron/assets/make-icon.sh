#!/usr/bin/env bash
#
# Generate frontend/electron/assets/icon.icns (and icon.png) from the two SVG
# masters in the same directory.
#
# Uses only tools that ship with macOS:
#   qlmanage  - renders SVG through WebKit (ImageMagick cannot: its SVG delegate
#               is rsvg-convert, which is not installed, so it silently falls
#               back to the MSVG renderer and drops every stroked path)
#   sips      - downsamples
#   iconutil  - packs the .iconset into a .icns
#
# qlmanage needs a logged-in window server session. Do not run this in CI; run
# it locally and commit the resulting icon.icns.

set -euo pipefail

ASSETS="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

render() { # <svg> <out.png>
  # qlmanage renders through WebKit, which on a malformed document happily
  # produces a picture of an XML error page instead of failing. That render is a
  # valid 1024x1024 PNG, so the existence check below cannot tell it apart from
  # a real icon — an unbalanced comment once shipped a pink error card as the
  # app icon. Validate the SVG first, and sanity-check the pixels after.
  xmllint --noout "$1" || { echo "not well-formed XML: $1" >&2; exit 1; }

  cp "$1" "$WORK/in.svg"
  qlmanage -t -s 1024 -o "$WORK" "$WORK/in.svg" >/dev/null 2>&1 || true
  [ -f "$WORK/in.svg.png" ] || { echo "qlmanage produced no render for $1" >&2; exit 1; }
  mv "$WORK/in.svg.png" "$2"

  # A WebKit error page is white with black text; every real master is a
  # saturated tile. Sampling one pixel well inside the tile separates them.
  local rgb
  rgb=$(
    sips -g pixelWidth "$2" >/dev/null 2>&1 &&
      python3 -c "
import struct, sys, zlib
# Read the single pixel at (512, 512) without any third-party imaging library.
path = sys.argv[1]
data = open(path, 'rb').read()
pos, width, height, idat = 8, 0, 0, b''
while pos < len(data):
    ln = struct.unpack('>I', data[pos:pos+4])[0]
    typ = data[pos+4:pos+8]
    body = data[pos+8:pos+8+ln]
    if typ == b'IHDR':
        width, height, depth, color = struct.unpack('>IIBB', body[:10])
        if depth != 8 or color not in (2, 6):
            print('unsupported'); sys.exit(0)
        channels = 3 if color == 2 else 4
    elif typ == b'IDAT':
        idat += body
    elif typ == b'IEND':
        break
    pos += 12 + ln
raw = zlib.decompress(idat)
stride = width * channels
y = min(512, height - 1)
prev = bytearray(stride)
for row in range(y + 1):
    off = row * (stride + 1)
    filt = raw[off]
    line = bytearray(raw[off+1:off+1+stride])
    for i in range(stride):
        a = line[i - channels] if i >= channels else 0
        b = prev[i]
        c = prev[i - channels] if i >= channels else 0
        if filt == 1: line[i] = (line[i] + a) & 255
        elif filt == 2: line[i] = (line[i] + b) & 255
        elif filt == 3: line[i] = (line[i] + (a + b) // 2) & 255
        elif filt == 4:
            p = a + b - c
            pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
            pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            line[i] = (line[i] + pr) & 255
    prev = line
x = min(512, width - 1) * channels
print(f'{prev[x]},{prev[x+1]},{prev[x+2]}')
" "$2"
  )
  case "$rgb" in
    unsupported) echo "  (skipped pixel check: unexpected PNG format)" >&2 ;;
    255,255,255) echo "render for $1 is a blank/error page, not an icon" >&2; exit 1 ;;
    *) echo "  centre pixel of $(basename "$2"): rgb($rgb)" >&2 ;;
  esac
}

render "$ASSETS/icon.svg"       "$WORK/master.png"        # inset, 128px and up
render "$ASSETS/icon-small.svg" "$WORK/master-small.png"  # near-full-bleed, 16/32

ICONSET="$WORK/dogma.iconset"
mkdir -p "$ICONSET"

# 16 and 32 come off the small master; anything 128 and up off the inset master.
sips -z 16   16   "$WORK/master-small.png" --out "$ICONSET/icon_16x16.png"      >/dev/null
sips -z 32   32   "$WORK/master-small.png" --out "$ICONSET/icon_16x16@2x.png"   >/dev/null
sips -z 32   32   "$WORK/master-small.png" --out "$ICONSET/icon_32x32.png"      >/dev/null
sips -z 64   64   "$WORK/master-small.png" --out "$ICONSET/icon_32x32@2x.png"   >/dev/null
sips -z 128  128  "$WORK/master.png"       --out "$ICONSET/icon_128x128.png"    >/dev/null
sips -z 256  256  "$WORK/master.png"       --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z 256  256  "$WORK/master.png"       --out "$ICONSET/icon_256x256.png"    >/dev/null
sips -z 512  512  "$WORK/master.png"       --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z 512  512  "$WORK/master.png"       --out "$ICONSET/icon_512x512.png"    >/dev/null
cp "$WORK/master.png" "$ICONSET/icon_512x512@2x.png"

iconutil -c icns "$ICONSET" -o "$ASSETS/icon.icns"
cp "$WORK/master.png" "$ASSETS/icon.png"

echo "wrote $ASSETS/icon.icns and $ASSETS/icon.png"
file "$ASSETS/icon.icns"
