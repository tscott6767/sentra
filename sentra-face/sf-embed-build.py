#!/usr/bin/env python3
# sf-embed-build.py — Sentra Face v1.3.0-embedded build (Sept 6, 2026)
# WHY: phone Firefox loads direct PNG URLs fine but BLOCKS the in-page
# cross-origin http <img> subresource (alt text showed instead). Fix: embed
# all four rig frames as base64 data: URLs — zero network fetches, immune to
# subresource blocking; bonus: no ~6.9MB re-fetch per page load on any device.
# Pipeline: probe caps (PIL/ffmpeg/numpy/pure-python) -> downscale 1152x1728
# -> 576x864 -> verify -> write small PNGs (served for eyeball check) ->
# transform source v1.2.3 into the embedded artifact -> serve-verify everything.

import base64, os, shutil, struct, subprocess, sys, time, zlib, urllib.request

SRC_DIR   = "/projects/sandbox/out/sentra-rig"
SMALL_DIR = "/projects/sandbox/out/sentra-rig-small"
SOURCE    = "/projects/sentra-face/sentra-face.user.js"
ARTIFACT  = "/projects/sandbox/out/sentra-face-embedded.user.js"
FRAMES    = ["idle", "talk", "blink", "talk_blink"]
FACTOR    = 2
OW, OH    = 1152, 1648          # original
NW, NH    = OW // FACTOR, OH // FACTOR  # 576 x 864
BASE      = "http://127.0.0.1:8090"

# ---------- capability probe ----------
def probe():
    caps = {"pil": False, "ffmpeg": None, "numpy": False}
    try:
        import PIL.Image  # noqa
        caps["pil"] = True
    except ImportError:
        pass
    try:
        import numpy  # noqa
        caps["numpy"] = True
    except ImportError:
        pass
    for tool in ("ffmpeg",):
        caps[tool] = shutil.which(tool)
    return caps

# ---------- pure-stdlib PNG codec (fallback + verifier) ----------
def png_decode(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos, w, h, depth, ctype, idat = 8, 0, 0, 0, 0, b""
    while pos < len(data):
        ln, = struct.unpack(">I", data[pos:pos+4])
        typ = data[pos+4:pos+8]
        chunk = data[pos+8:pos+8+ln]
        if typ == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", chunk[:10])
        elif typ == b"IDAT":
            idat += chunk
        pos += 12 + ln
    assert depth == 8 and ctype == 6, "expected 8-bit RGBA (depth=%d ctype=%d)" % (depth, ctype)
    raw = zlib.decompress(idat)
    bpp, stride = 4, w * 4
    out = bytearray(w * h * 4)

    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        return a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)

    p = 0
    for y in range(h):
        f = raw[p]; p += 1
        for x in range(stride):
            a = out[y*stride + x - bpp] if x >= bpp else 0
            b = out[(y-1)*stride + x] if y > 0 else 0
            c = out[(y-1)*stride + x - bpp] if (y > 0 and x >= bpp) else 0
            v = raw[p]; p += 1
            if f == 0:   r = v
            elif f == 1: r = (v + a) & 0xFF
            elif f == 2: r = (v + b) & 0xFF
            elif f == 3: r = (v + (a + b) // 2) & 0xFF
            elif f == 4: r = (v + paeth(a, b, c)) & 0xFF
            else: raise ValueError("bad filter %d" % f)
            out[y*stride + x] = r
    return bytes(out), w, h

def png_encode(px, w, h):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)  # filter None
        raw += px[y*stride:(y+1)*stride]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))

def downscale_premult(px, w, h, f):
    # premultiplied box average: avoids dark halos on transparent edges
    nw, nh = w // f, h // f
    out = bytearray(nw * nh * 4)
    n = f * f
    for oy in range(nh):
        for ox in range(nw):
            rs = gs = bs = asum = 0
            for dy in range(f):
                row = ((oy*f + dy) * w + ox * f) * 4
                for dx in range(f):
                    i = row + dx * 4
                    a = px[i+3]
                    rs += px[i] * a; gs += px[i+1] * a; bs += px[i+2] * a; asum += a
            j = (oy * nw + ox) * 4
            if asum == 0:
                out[j:j+4] = b"\x00\x00\x00\x00"
            else:
                out[j]   = min(255, int(rs / asum + 0.5))
                out[j+1] = min(255, int(gs / asum + 0.5))
                out[j+2] = min(255, int(bs / asum + 0.5))
            out[j+3] = int(asum / n + 0.5)
    return bytes(out), nw, nh

# ---------- downscale dispatch ----------
def downscale(name, caps, timings):
    src = os.path.join(SRC_DIR, name + ".png")
    dst = os.path.join(SMALL_DIR, name + ".png")
    t0 = time.time()
    if caps["pil"]:
        from PIL import Image
        im = Image.open(src).convert("RGBA")
        assert im.size == (OW, OH), "unexpected size %s" % (im.size,)
        small = im.resize((NW, NH), Image.BOX)
        small.save(dst, optimize=True)
        method = "PIL"
    elif caps["ffmpeg"]:
        r = subprocess.run(
            [caps["ffmpeg"], "-y", "-loglevel", "error", "-i", src,
             "-vf", "scale=%d:%d:flags=area" % (NW, NH), "-pix_fmt", "rgba", dst],
            capture_output=True, timeout=120)
        assert r.returncode == 0, "ffmpeg failed: %s" % r.stderr.decode()[:300]
        method = "ffmpeg"
    else:
        data = open(src, "rb").read()
        px, w, h = png_decode(data)
        assert (w, h) == (OW, OH)
        spx, sw, sh = downscale_premult(px, w, h, FACTOR)
        open(dst, "wb").write(png_encode(spx, sw, sh))
        method = "pure-python"
    timings.append((name, method, time.time() - t0))
    return dst

# ---------- main ----------
def main():
    caps = probe()
    print("caps: PIL=%s ffmpeg=%s numpy=%s" % (caps["pil"], bool(caps["ffmpeg"]), caps["numpy"]))
    os.makedirs(SMALL_DIR, exist_ok=True)

    timings, results = [], {}
    for name in FRAMES:
        dst = downscale(name, caps, timings)
        data = open(dst, "rb").read()
        px, w, h = png_decode(data)  # verify our own output decodes (all paths)
        assert (w, h) == (NW, NH), "bad output size %s" % (w, h)
        results[name] = data
    for name, method, dt in timings:
        print("DOWNSCALE %-11s via %-11s %5.1fs  -> %10d bytes (%.0f%% of original)"
              % (name, method, dt, len(results[name]), 100.0 * len(results[name]) / os.path.getsize(os.path.join(SRC_DIR, name + ".png"))))
    total = sum(len(v) for v in results.values())
    print("small total: %d bytes (%.2f MB); base64 will be ~%.2f MB" % (total, total/1e6, total*4/3/1e6))

    # ---------- transform source into embedded artifact ----------
    src = open(SOURCE, encoding="utf-8").read()
    img_block = '''  var ASSET_BASE = "http://192.168.178.57:8090/sandbox/out/sentra-rig";
  var IMG = {
    idle:       ASSET_BASE + "/idle.png",
    talk:       ASSET_BASE + "/talk.png",
    blink:      ASSET_BASE + "/blink.png",
    talk_blink: ASSET_BASE + "/talk_blink.png",
  };'''
    assert img_block in src, "IMG block not found in source — source changed?"
    b64 = {k: base64.b64encode(results[k]).decode("ascii") for k in FRAMES}
    new_block = ("  // v1.3: frames EMBEDDED as data: URLs (phone browsers block cross-origin\n"
                 "  // http <img> subresources; embedded frames need zero network fetches).\n"
                 "  var IMG = {\n"
                 + "".join('    %s:%s"data:image/png;base64,%s",\n' % (k, " " * max(1, 12 - len(k)), b64[k]) for k in FRAMES)
                 + "  };")
    out = src.replace(img_block, new_block)
    out = out.replace("// @version      1.2.3", "// @version      1.3.0")
    out = out.replace("/* Sentra Face v1.2.3 \u2014 spec:", "/* Sentra Face v1.3.0-embedded \u2014 spec:")
    note_anchor = " *       src on the face (seen on phone when the browser blocked the fetch)."
    assert note_anchor in out, "v1.2.3 note anchor missing"
    out = out.replace(note_anchor, note_anchor + "\n"
        " * v1.3.0-embedded: all four frames downscaled 2x (1152x1648 -> 576x824,\n"
        " *       premultiplied box average) and embedded as base64 data: URLs \u2014\n"
        " *       built by /projects/sandbox/sf-embed-build.py from this source.\n"
        " *       No network fetches: immune to phone subresource blocking; no\n"
        " *       per-page-load re-download on any device.")
    out = out.replace('console.info("[Sentra Face] v1.2.3 active', 'console.info("[Sentra Face] v1.3.0-embedded active')
    open(ARTIFACT, "wb").write(out.encode("utf-8"))
    artifact_bytes = os.path.getsize(ARTIFACT)
    print("artifact written: %s (%d bytes; %d chars, diff = UTF-8 multibyte)" % (ARTIFACT, artifact_bytes, len(out)))

    # ---------- serve-verify ----------
    print("\n--- HTTP SERVE CHECK ---")
    fails = 0
    checks = [("/sandbox/out/sentra-face-embedded.user.js", artifact_bytes)] + \
             [("/sandbox/out/sentra-rig-small/%s.png" % k, len(results[k])) for k in FRAMES]
    for path, want in checks:
        try:
            r = urllib.request.urlopen(BASE + path, timeout=10)
            b = r.read()
            ok = r.status == 200 and len(b) == want
            print("%s %s -> %d, %d bytes (want %d)" % ("OK  " if ok else "FAIL", path, r.status, len(b), want))
            fails += 0 if ok else 1
        except Exception as e:
            print("FAIL %s -> %s" % (path, e)); fails += 1
    print("\nRESULT: " + ("BUILD VERIFIED" if fails == 0 else "%d FAILURE(S)" % fails))
    sys.exit(1 if fails else 0)

main()
