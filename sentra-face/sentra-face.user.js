// ==UserScript==
// @name         Sentra Face
// @namespace    sentra
// @version      1.2.3
// @description  Talking-face avatar for Open WebUI — 4-state PNGTuber rig, amplitude lip-sync on backend TTS audio
// @author       Sentra (Tony's household AI)
// @match        *://192.168.178.231/*
// @grant        none
// @run-at       document-idle
// @noframes
// ==/UserScript==

/* Sentra Face v1.2.3 — spec: /projects/sentra-face/SPEC.md (locked 2026-09-06)
 * v1.1: envelope follower (fast attack / release) + hysteresis + min-open
 *       dwell — fixes v1.0's disjointed/laggy mouth (raw RMS vs hard threshold
 *       caused rapid flapping at the boundary and missed opens between syllables).
 * v1.1.1: retuned for livelier motion — RELEASE 0.30 (closes between words,
 *       not just sentences), MIN_OPEN_MS 80, close threshold 0.055. Fixes
 *       "slow, not frequent enough" (v1.1 over-damped).
 * v1.1.2: state() now reports attack/release/minOpenMs so tuning changes are
 *       visible; env clamped to 0 on idle decay (no 1e-159 underflow displays).
 * v1.2.0: AUTO threshold — open threshold tracks the speech's own recent peak
 *       (~30%, floor-guarded) instead of fixed 0.10. Fixes "pauses too long"
 *       (much of the TTS sits below fixed 0.10 -> long closed stretches).
 *       setThreshold() = manual override; setAuto(true) returns to auto.
 * v1.2.1: ratio retune — OPEN_RATIO 0.30->0.45, CLOSE_RATIO 0.55->0.70.
 *       v1.2's band (close bar at 16.5% of peak) only shut near silence —
 *       mouth held open through quiet words ("stays open too long too often").
 *       New band: open ~45% of peak, close ~31% -> closes on inter-word dips.
 *       Live knobs: setOpenRatio() / setCloseRatio().
 * v1.2.2: Tony-verified values baked — OPEN_RATIO 0.40, CLOSE_RATIO 0.80
 *       ("these work well"); desktop avatar DOUBLED 24vh -> 48vh per request;
 *       new setSize(vh) live knob (localStorage-persisted, desktop only —
 *       mobile keeps its 18vh media-query rule).
 * v1.2.3: applyFrame now requires naturalWidth>0 — a FAILED image load can
 *       still report complete=true (spec quirk), which put a broken alt-text
 *       src on the face (seen on phone when the browser blocked the fetch).
 * Rig: idle / talk / blink / talk_blink (1152x1728 RGBA, Grok-generated)
 * Assets: served by projects file server (LXC 111 :8090) — <img> display is
 *         CORS-free; only backend-TTS <audio> drives the face (Web Speech
 *         browser mode has no <audio> and won't animate it — by design).
 * Live tuning (browser console): window.SENTRA_FACE.setThreshold(x),
 *         window.SENTRA_FACE.debug(true), window.SENTRA_FACE.state()
 */

(function () {
  "use strict";

  // ---------------- CONFIG ----------------
  var ASSET_BASE = "http://192.168.178.57:8090/sandbox/out/sentra-rig";
  var IMG = {
    idle:       ASSET_BASE + "/idle.png",
    talk:       ASSET_BASE + "/talk.png",
    blink:      ASSET_BASE + "/blink.png",
    talk_blink: ASSET_BASE + "/talk_blink.png",
  };
  // --- mouth-open threshold: AUTO-calibrating (v1.2, Tony-verified v1.2.2) ---
  // Much of the TTS speech sits BELOW any fixed threshold -> mouth stayed
  // closed through quiet stretches ("pauses too long"). The threshold now
  // tracks the speech's own recent peak: opens at ~40% of it, closes at ~32%.
  var AUTO_THRESHOLD = true;  // false = manual fixed threshold (MANUAL_OPEN)
  var OPEN_RATIO   = 0.40;    // open at 40% of recent speech peak (Tony-verified)
  var CLOSE_RATIO  = 0.80;    // close at 80% of the open threshold (Tony-verified)
  var THRESH_FLOOR = 0.02;    // never open below this (silence guard)
  var PEAK_DECAY   = 0.995;   // per-tick peak decay (half-life ~2.3s @ 60Hz)
  var MANUAL_OPEN  = 0.10;    // used only when AUTO_THRESHOLD = false
  var ATTACK = 0.60;  // fast attack: mouth snaps open on speech onset
  var RELEASE = 0.30; // quick release: envelope falls ~60-100ms after a dip so
                      // the mouth closes between words and reopens — word-rate
                      // motion (v1.1's 0.10 over-smoothed into sluggish)
  var MIN_OPEN_MS = 80;  // bridges only the fastest dips (prevents 60Hz flapping)
  var SAMPLE_MS       = 16;  // amplitude sampling interval (~60/s, snappy attack)
  var BLINK_MIN_MS    = 3000;
  var BLINK_MAX_MS    = 6000;
  var BLINK_HOLD_MS   = 140; // how long a blink frame shows
  var SCAN_MS         = 2000; // watchdog: re-scan audios + re-check overlay

  // ---------------- STATE ----------------
  var overlay = null, faceImg = null, styleEl = null, hud = null;
  var preloaded = {};
  var currentKey = null;
  var talking = false, blinking = false;
  var env = 0;          // smoothed amplitude envelope (attack/release follower)
  var talkingSince = 0; // timestamp of current mouth-open period
  var peakEnv = 0;      // recent speech peak (auto-threshold reference)
  var sharedCtx = null;
  var attached = new WeakSet();
  var analysers = []; // {el, an, buf}
  var lastRms = 0;

  // ---------------- STYLES ----------------
  function ensureStyles() {
    if (document.getElementById("sf-style")) return;
    styleEl = document.createElement("style");
    styleEl.id = "sf-style";
    styleEl.textContent = [
      "#sentra-face{position:fixed;top:50%;right:16px;transform:translateY(-50%);" +
        "z-index:99999;pointer-events:none;user-select:none;}",
      "#sentra-face img{display:block;height:48vh;width:auto;" +
        "filter:drop-shadow(0 4px 14px rgba(0,0,0,.45));" +
        "animation:sf-bob 3.4s ease-in-out infinite;}",
      "@keyframes sf-bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}",
      "@media (max-width:768px){",
      " #sentra-face{top:auto;right:12px;bottom:96px;transform:none;" +
        "pointer-events:auto;touch-action:none;cursor:grab;}",
      " #sentra-face img{height:18vh;border-radius:14px;}",
      "}",
      "#sentra-face.sf-dragging{cursor:grabbing;}",
      "#sf-hud{position:fixed;left:8px;top:8px;z-index:100000;font:11px/1.5 monospace;" +
        "background:rgba(0,0,0,.75);color:#7f7;padding:4px 8px;border-radius:6px;" +
        "pointer-events:none;display:none;white-space:pre;}",
    ].join("\n");
    (document.head || document.documentElement).appendChild(styleEl);
    if (!document.getElementById("sf-hud")) {
      hud = document.createElement("div");
      hud.id = "sf-hud";
      document.body.appendChild(hud);
    } else {
      hud = document.getElementById("sf-hud");
    }
  }

  // ---------------- FRAMES ----------------
  function preload() {
    Object.keys(IMG).forEach(function (k) {
      var im = new Image();
      im.onload = function () { if (currentKey === null) applyFrame(true); };
      im.src = IMG[k];
      preloaded[k] = im;
    });
  }

  function frameKey() {
    if (talking) return blinking ? "talk_blink" : "talk";
    return blinking ? "blink" : "idle";
  }

  function applyFrame(force) {
    var k = frameKey();
    if (k === currentKey && !force) return;
    var im = preloaded[k];
    if (!im || !im.complete || im.naturalWidth === 0) return; // wait until frame actually loaded (guards failed fetches)
    faceImg.src = im.src;
    currentKey = k;
  }

  // ---------------- AUDIO ----------------
  function ensureCtx() {
    if (!sharedCtx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      sharedCtx = new AC();
    }
    if (sharedCtx.state === "suspended") sharedCtx.resume();
    return sharedCtx;
  }

  function attachAudio(el) {
    if (!el || attached.has(el)) return;
    attached.add(el);
    try {
      var ctx = ensureCtx();
      var src = ctx.createMediaElementSource(el);
      var an = ctx.createAnalyser();
      an.fftSize = 1024; // ~21ms window @48kHz; time-domain data ignores smoothing
      src.connect(an);
      an.connect(ctx.destination); // MUST route through, else audio goes silent
      analysers.push({ el: el, an: an, buf: new Uint8Array(an.fftSize) });
      console.info("[Sentra Face] attached to <audio>", el.currentSrc || el.src || "(no src yet)");
    } catch (e) {
      console.warn("[Sentra Face] audio attach failed:", e);
      attached.delete(el);
      return;
    }
    el.addEventListener("play", function () {
      ensureCtx(); // resume near a user gesture
    });
  }

  function scanAudios() {
    var list = document.querySelectorAll("audio");
    for (var i = 0; i < list.length; i++) attachAudio(list[i]);
  }

  function observeAudios() {
    var mo = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var m = muts[i];
        for (var j = 0; j < m.addedNodes.length; j++) {
          var n = m.addedNodes[j];
          if (n.nodeType !== 1) continue;
          if (n.tagName === "AUDIO") attachAudio(n);
          else if (n.querySelectorAll) {
            var auds = n.querySelectorAll("audio");
            for (var k = 0; k < auds.length; k++) attachAudio(auds[k]);
          }
        }
      }
    });
    mo.observe(document.documentElement, { childList: true, subtree: true });
  }

  function curOpenThr() {
    return AUTO_THRESHOLD ? Math.max(THRESH_FLOOR, peakEnv * OPEN_RATIO) : MANUAL_OPEN;
  }

  function sampleLoop() {
    var entry = null;
    for (var i = 0; i < analysers.length; i++) {
      var a = analysers[i];
      if (a.el.readyState >= 2 && !a.el.paused && !a.el.ended) entry = a; // last playing wins
    }
    var now = Date.now();
    if (!entry) {
      lastRms = 0;
      env = env * 0.85; // nothing playing: envelope decays, mouth closes softly
      if (env < 1e-9) env = 0; // clamp float underflow (avoids 1e-159-style values)
      peakEnv = 0; // no audio: reset the auto-threshold reference
      if (env < THRESH_FLOOR) talking = false;
    } else {
      var d = entry.buf;
      entry.an.getByteTimeDomainData(d);
      var sum = 0;
      for (var j = 0; j < d.length; j++) {
        var v = (d[j] - 128) / 128;
        sum += v * v;
      }
      lastRms = Math.sqrt(sum / d.length);
      // Envelope follower: fast attack on rising volume, slow release on falling.
      var k = lastRms > env ? ATTACK : RELEASE;
      env = k * lastRms + (1 - k) * env;
      // Track the speech's own recent peak (slow decay between words).
      if (env > peakEnv) peakEnv = env;
      else peakEnv *= PEAK_DECAY;
      // Dynamic thresholds: auto (ratio of the speech peak) or manual (fixed).
      var openThr = curOpenThr();
      var closeThr = openThr * CLOSE_RATIO;
      if (!talking && env > openThr) {
        talking = true;
        talkingSince = now;
      } else if (talking && env < closeThr && now - talkingSince > MIN_OPEN_MS) {
        talking = false;
      }
    }
    applyFrame(false);
    updateHud();
  }

  // ---------------- BLINK ----------------
  function scheduleBlink() {
    var wait = BLINK_MIN_MS + Math.random() * (BLINK_MAX_MS - BLINK_MIN_MS);
    setTimeout(function () {
      blinking = true;
      applyFrame(false);
      setTimeout(function () {
        blinking = false;
        applyFrame(false);
        scheduleBlink();
      }, BLINK_HOLD_MS);
    }, wait);
  }

  // ---------------- OVERLAY + DRAG ----------------
  function clampPos(x, y, w, h) {
    var vw = window.innerWidth, vh = window.innerHeight;
    return {
      x: Math.min(Math.max(0, x), Math.max(0, vw - w)),
      y: Math.min(Math.max(0, y), Math.max(0, vh - h)),
    };
  }

  function restorePos() {
    // mobile only: restore last dragged position
    try {
      if (!window.matchMedia("(max-width: 768px)").matches) return;
      var p = JSON.parse(localStorage.getItem("sf-pos") || "null");
      if (!p) return;
      var r = overlay.getBoundingClientRect();
      var c = clampPos(p.x, p.y, r.width, r.height);
      overlay.style.left = c.x + "px";
      overlay.style.top = c.y + "px";
      overlay.style.right = "auto";
      overlay.style.bottom = "auto";
      overlay.style.transform = "none";
    } catch (e) { /* ignore */ }
  }

  function makeDraggable(node) {
    var dragging = false, sx = 0, sy = 0, ox = 0, oy = 0;
    node.addEventListener("pointerdown", function (e) {
      dragging = true;
      node.setPointerCapture(e.pointerId);
      node.classList.add("sf-dragging");
      var r = node.getBoundingClientRect();
      sx = e.clientX; sy = e.clientY; ox = r.left; oy = r.top;
      e.preventDefault();
    });
    node.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      var r = node.getBoundingClientRect();
      var c = clampPos(ox + e.clientX - sx, oy + e.clientY - sy, r.width, r.height);
      node.style.left = c.x + "px";
      node.style.top = c.y + "px";
      node.style.right = "auto";
      node.style.bottom = "auto";
      node.style.transform = "none";
      try { localStorage.setItem("sf-pos", JSON.stringify({ x: c.x, y: c.y })); } catch (err) {}
    });
    ["pointerup", "pointercancel"].forEach(function (ev) {
      node.addEventListener(ev, function () {
        dragging = false;
        node.classList.remove("sf-dragging");
      });
    });
  }

  function buildOverlay() {
    var existing = document.getElementById("sentra-face");
    if (existing) { overlay = existing; return; }
    overlay = document.createElement("div");
    overlay.id = "sentra-face";
    faceImg = document.createElement("img");
    faceImg.alt = "Sentra";
    overlay.appendChild(faceImg);
    document.body.appendChild(overlay);
    makeDraggable(overlay);
    restorePos();
    try { // restore saved desktop size (mobile keeps its 18vh media-query rule)
      if (!window.matchMedia("(max-width: 768px)").matches) {
        var sz = parseFloat(localStorage.getItem("sf-size"));
        if (sz > 0) faceImg.style.height = sz + "vh";
      }
    } catch (e) { /* ignore */ }
    preload();
    applyFrame(true);
  }

  // ---------------- DEBUG HUD + TUNING API ----------------
  function updateHud() {
    if (!hud || hud.style.display === "none") return;
    hud.textContent =
      "rms=" + lastRms.toFixed(3) + "  env=" + env.toFixed(3) + "  peak=" + peakEnv.toFixed(3) + "\n" +
      (AUTO_THRESHOLD ? "[auto] " : "[man] ") +
      "open@" + curOpenThr().toFixed(3) + "  close@" + (curOpenThr() * CLOSE_RATIO).toFixed(3) + "\n" +
      (talking ? "TALK" : "idle") + (blinking ? "+blink" : "") +
      "  frame=" + (currentKey || "-");
    hud.style.background = talking ? "rgba(0,96,0,.85)" : "rgba(0,0,0,.75)";
  }

  window.SENTRA_FACE = {
    // setThreshold = MANUAL override (disables auto; close tracks at 55%).
    // setAuto(true) returns to the auto-calibrating default.
    setThreshold: function (v) { AUTO_THRESHOLD = false; MANUAL_OPEN = v; return v; },
    getThreshold: function () { return curOpenThr(); },
    setAuto: function (on) { AUTO_THRESHOLD = !!on; return AUTO_THRESHOLD; },
    setOpenRatio: function (v) { OPEN_RATIO = v; return v; },   // 0.40 default
    setCloseRatio: function (v) { CLOSE_RATIO = v; return v; }, // 0.80 default
    setSize: function (vh) { // desktop avatar height in vh units (48 default)
      faceImg.style.height = vh + "vh";
      try { localStorage.setItem("sf-size", String(vh)); } catch (err) {}
      return vh;
    },
    setAttack: function (v) { ATTACK = v; return ATTACK; },
    setRelease: function (v) { RELEASE = v; return RELEASE; },
    debug: function (on) {
      ensureStyles();
      hud.style.display = on ? "block" : "none";
      updateHud();
      return !!on;
    },
    state: function () {
      return {
        rms: lastRms, env: env, peak: peakEnv, auto: AUTO_THRESHOLD,
        openThreshold: curOpenThr(), closeThreshold: curOpenThr() * CLOSE_RATIO,
        openRatio: OPEN_RATIO, closeRatio: CLOSE_RATIO,
        attack: ATTACK, release: RELEASE, minOpenMs: MIN_OPEN_MS,
        talking: talking, blinking: blinking, frame: currentKey,
      };
    },
  };

  // ---------------- WATCHDOG (survives Svelte re-renders) ----------------
  setInterval(function () {
    if (!document.body) return;
    if (!document.getElementById("sf-style")) ensureStyles();
    if (!document.getElementById("sentra-face")) buildOverlay();
    scanAudios();
  }, SCAN_MS);

  // ---------------- INIT ----------------
  function init() {
    ensureStyles();
    buildOverlay();
    scanAudios();
    observeAudios();
    setInterval(sampleLoop, SAMPLE_MS);
    scheduleBlink();
    console.info("[Sentra Face] v1.2.3 active — verified thresholds (open 40%/close 32% of peak), desktop 48vh; tune via window.SENTRA_FACE");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
