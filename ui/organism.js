// organism.js - the living membrane.
// A full-screen WebGL fragment shader. It is not decoration: its mass, turbulence,
// colour and pulse are fed from the engine's real state, and it flashes on real events.
(function () {
  const cvs = document.getElementById('gl');
  const gl = cvs.getContext('webgl', { antialias: true, alpha: false })
          || cvs.getContext('experimental-webgl');

  // If WebGL is unavailable (e.g. a GPU-less headless capture), the rest of the
  // interface still works; the membrane simply stays dark.
  if (!gl) {
    window.Organism = { set() {}, flash() {}, extinct() {} };
    return;
  }

  const VERT = `attribute vec2 p; void main(){ gl_Position = vec4(p,0.,1.); }`;

  const FRAG = `
  precision highp float;
  uniform vec2  uRes;
  uniform float uTime;
  uniform float uMass;      // overall size of the organism (population)
  uniform float uActivity;  // recent birth rate -> turbulence + brightness
  uniform float uHue;       // shifts with civilization / era
  uniform float uDepth;     // 0 surface .. 1 deep inside
  uniform float uFlash;     // event pulse (decays in JS)
  uniform float uExtinct;   // reddening on extinction

  float hash(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y); }
  float vnoise(vec2 p){
    vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f);
    float a=hash(i), b=hash(i+vec2(1,0)), c=hash(i+vec2(0,1)), d=hash(i+vec2(1,1));
    return mix(mix(a,b,f.x),mix(c,d,f.x),f.y);
  }
  float fbm(vec2 p){
    float v=0., a=.5; mat2 m=mat2(1.6,1.2,-1.2,1.6);
    for(int i=0;i<6;i++){ v+=a*vnoise(p); p=m*p; a*=.5; }
    return v;
  }
  vec3 palette(float t, float h){
    // deep space -> plasma; hue rotates the whole scheme
    vec3 base = .5 + .5*cos(6.2831*(t*vec3(1.,.9,.7) + vec3(h, h+.33, h+.66)));
    return base;
  }
  void main(){
    vec2 uv = (gl_FragCoord.xy - .5*uRes)/uRes.y;
    float t = uTime*.05;
    float turb = .22 + uActivity*.5;

    // domain warp -> organic tendrils
    vec2 q = vec2(fbm(uv*2.2 + t), fbm(uv*2.2 - t + 5.2));
    vec2 r = vec2(fbm(uv*2.2 + 1.5*q + vec2(1.7,9.2) + t*1.3),
                  fbm(uv*2.2 + 1.5*q + vec2(8.3,2.8) - t));
    float f = fbm(uv*2.0 + turb*r);

    float rad = (0.52 + 0.13*uMass) * (1.0 - 0.22*uDepth);
    float body = length(uv) - rad - (f-0.5)*(0.34+turb*0.32);
    float membrane = smoothstep(0.045, 0.0, abs(body));        // glowing shell
    float inner = smoothstep(0.0, -0.9, body);                  // inner plasma
    float core = exp(-6.0*length(uv)) ;

    float glow = membrane*1.4 + inner*(0.35 + 0.5*f) + core*(0.6+uFlash*2.5);
    glow += uFlash * membrane * 3.0;

    float h = uHue + 0.08*f + uDepth*0.15;
    vec3 col = palette(0.35 + 0.5*f + uFlash*0.3, h) * glow;
    col += vec3(0.02,0.03,0.06);                                // faint nebula
    col = mix(col, vec3(1.0,0.25,0.33), uExtinct*inner);         // extinction reddening

    // vignette - keep the form centred and the edges calm
    col *= 1.0 - 0.58*dot(uv,uv);
    col = pow(col, vec3(0.9));
    gl_FragColor = vec4(col, 1.0);
  }`;

  function sh(type, src) {
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(s));
    return s;
  }
  const prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT));
  gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
  gl.linkProgram(prog); gl.useProgram(prog);

  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, 'p');
  gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

  const U = {};
  ['uRes','uTime','uMass','uActivity','uHue','uDepth','uFlash','uExtinct']
    .forEach(n => U[n] = gl.getUniformLocation(prog, n));

  const state = { mass: .2, activity: .1, hue: .58, depth: 0, flash: 0, extinct: 0,
                  tMass: .2, tActivity: .1, tHue: .58, tDepth: 0 };

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    cvs.width = innerWidth * dpr; cvs.height = innerHeight * dpr;
    gl.viewport(0, 0, cvs.width, cvs.height);
  }
  window.addEventListener('resize', resize); resize();

  let t0 = performance.now();
  function frame(now) {
    const dt = Math.min(0.05, (now - t0) / 1000); t0 = now;
    // ease toward targets so transitions feel alive
    state.mass += (state.tMass - state.mass) * 0.04;
    state.activity += (state.tActivity - state.activity) * 0.06;
    state.hue += (state.tHue - state.hue) * 0.03;
    state.depth += (state.tDepth - state.depth) * 0.07;
    state.flash *= 0.94;
    state.extinct *= 0.97;

    gl.uniform2f(U.uRes, cvs.width, cvs.height);
    gl.uniform1f(U.uTime, now / 1000);
    gl.uniform1f(U.uMass, state.mass);
    gl.uniform1f(U.uActivity, state.activity);
    gl.uniform1f(U.uHue, state.hue);
    gl.uniform1f(U.uDepth, state.depth);
    gl.uniform1f(U.uFlash, state.flash);
    gl.uniform1f(U.uExtinct, state.extinct);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  window.Organism = {
    set(o) {
      if (o.mass !== undefined) state.tMass = Math.min(1, o.mass);
      if (o.activity !== undefined) state.tActivity = Math.min(1.2, o.activity);
      if (o.hue !== undefined) state.tHue = o.hue;
      if (o.depth !== undefined) state.tDepth = o.depth;
    },
    flash(strength) { state.flash = Math.min(2, state.flash + (strength || 0.6)); },
    extinct() { state.extinct = 1; },
  };
})();
