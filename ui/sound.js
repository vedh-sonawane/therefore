// sound.js - the engine, heard.
// Every invention has a voice derived from how it actually behaves: its sequence is
// mapped to pitch and timbre, so similar inventions sound similar. Births, discoveries,
// firsts and deaths are audible. With the screen off you can still tell what it's doing.
(function () {
  let ctx = null, master = null, drone = null, droneGain = null, on = false;

  // a warm pentatonic field so simultaneous events stay consonant
  const SCALE = [0, 3, 5, 7, 10, 12, 15, 17, 19, 22, 24];
  const BASE = 196.0; // G3

  function noteFor(seq) {
    if (!seq || !seq.length) return BASE;
    let h = 0;
    for (let i = 0; i < Math.min(seq.length, 8); i++) h += ((seq[i] % 23) + 23) * (i + 1);
    const deg = SCALE[h % SCALE.length];
    // growth pushes it up an octave or two -> big sequences ring higher
    const last = Math.abs(seq[seq.length - 1] || 1);
    const oct = Math.min(3, Math.floor(Math.log10(last + 1) / 1.2));
    return BASE * Math.pow(2, (deg + 12 * oct) / 12);
  }

  function enable() {
    if (ctx) { resume(); return true; }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return false;
    ctx = new AC();
    master = ctx.createGain(); master.gain.value = 0.9;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 5200;
    master.connect(lp); lp.connect(ctx.destination);

    // ambient drone (two detuned saws, very low) - the organism breathing
    drone = ctx.createOscillator(); const d2 = ctx.createOscillator();
    drone.type = 'sawtooth'; d2.type = 'sawtooth';
    drone.frequency.value = BASE / 2; d2.frequency.value = BASE / 2 * 1.005;
    droneGain = ctx.createGain(); droneGain.gain.value = 0.0;
    const df = ctx.createBiquadFilter(); df.type = 'lowpass'; df.frequency.value = 420;
    drone.connect(df); d2.connect(df); df.connect(droneGain); droneGain.connect(master);
    drone.start(); d2.start();
    on = true; return true;
  }
  function resume() { if (ctx && ctx.state === 'suspended') ctx.resume(); on = true; }

  function voice(freq, dur, type, gain, when) {
    if (!ctx) return;
    const t = when || ctx.currentTime;
    const o = ctx.createOscillator(); o.type = type || 'triangle'; o.frequency.value = freq;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(gain || 0.18, t + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0008, t + dur);
    o.connect(g); g.connect(master);
    o.start(t); o.stop(t + dur + 0.05);
  }

  window.Sound = {
    enabled() { return on; },
    enable,
    toggle() { if (!ctx) return enable(); on = !on; if (on) resume(); return on; },
    birth(seq, score) {
      if (!on) return;
      voice(noteFor(seq), 0.5 + Math.min(0.5, (score || 0) / 20), 'triangle', 0.10);
    },
    discovery(seq) {
      if (!on) return;
      const f = noteFor(seq);
      voice(f, 0.7, 'sine', 0.09);
      voice(f * 1.5, 0.7, 'sine', 0.05, ctx.currentTime + 0.04);
    },
    first(seq) {
      if (!on) return;
      const f = noteFor(seq); const t = ctx.currentTime;
      [1, 1.25, 1.5, 2].forEach((m, i) => voice(f * m, 1.6, 'sine', 0.11 - i * 0.015, t + i * 0.05));
    },
    dormant() {
      if (!on) return;
      voice(BASE / 2, 0.6, 'sine', 0.12);
    },
    extinction() {
      if (!on) return;
      voice(BASE / 3, 2.2, 'sawtooth', 0.2);
    },
    activity(a) {
      if (!on || !droneGain) return;
      droneGain.gain.setTargetAtTime(0.03 + Math.min(0.1, a * 0.12), ctx.currentTime, 1.5);
    },
  };
})();
