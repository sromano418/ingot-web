// Campo de partículas de la portada, inspirado en antigravity.google.
// Conversión a JavaScript normal de crm-commodities/src/components/CampoParticulas.tsx:
// mismos shaders y misma lógica; solo cambian los colores (paleta InGot) y que la página
// siempre es oscura. Todo el cálculo corre en la tarjeta gráfica (WebGL).
(function () {
  const canvas = document.getElementById('campo')
  if (!canvas) return

  // Ruido simplex 3D en GLSL (versión estándar de dominio público de Ashima Arts / Stefan Gustavson)
  const NOISE = `
vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1.0/6.0,1.0/3.0); const vec4 D=vec4(0.0,0.5,1.0,2.0);
  vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.0-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));
  float n_=0.142857142857; vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.0*floor(p*ns.z*ns.z); vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.0*x_);
  vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.0-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.0+1.0; vec4 s1=floor(b1)*2.0+1.0; vec4 sh=-step(h,vec4(0.0));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x; p1*=norm.y; p2*=norm.z; p3*=norm.w;
  vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0); m=m*m;
  return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}`

  const VERT = `
precision highp float;
attribute vec2 aPos;          // posición base en px
uniform vec2 uRes;            // tamaño del lienzo en px
uniform float uTime, uU, uR, uW1, uW2, uTam, uDpr, uDark;
uniform vec2 uRing;           // centro del anillo en px
uniform vec3 uC1, uC2, uC3;
varying float vAng, vAlpha, vRatio;
varying vec3 vColor;
${NOISE}
void main(){
  float t = uTime * 0.5;
  vec2 s = aPos / uU;                                   // coordenadas de escena para el ruido
  // Deriva lenta: ruido de escala media y fina
  vec2 disp = vec2(snoise(vec3(s*0.8+vec2(88.4,32.4), t*0.7)), snoise(vec3(s*0.8+vec2(50.9,12.9), t*0.7))) * 0.13 * uU;
  disp += vec2(snoise(vec3(s*4.0+vec2(18.4,72.9), t)), snoise(vec3(s*4.0+vec2(50.9,120.9), t))) * 0.02 * uU;

  float d  = distance(aPos, uRing);
  float d1 = distance(aPos + snoise(vec3(s*0.04, t*0.5)) * 0.025 * uU, uRing);
  // Banda ancha + banda fina en el borde + interior + manchas de fondo
  float b  = clamp(smoothstep(uR - uW1*2.0, uR, d) - smoothstep(uR, uR + uW1, d1), 0.0, 1.0);
  float b2 = clamp(smoothstep(uR - uW2*2.0, uR, d) - smoothstep(uR, uR + uW2, d1), 0.0, 1.0);
  float dentro = smoothstep(uR + uW2, uR, d);
  b = b*b; b2 = b2*b2*b2;
  float e = b + b2*3.0 + dentro*0.4;
  e += snoise(vec3(s*6.0+vec2(11.4,12.9), t)) * dentro * 0.5;
  float nS = snoise(vec3(s*0.4+vec2(18.4,72.9), t));
  e += pow((nS + 1.5) * 0.5, 2.0) * 0.6;

  // Empuje hacia afuera sobre el borde
  vec2 pos = aPos + disp + (aPos - uRing) * pow(b2, 0.75) * 0.12;

  // Color por manchas de ruido (c1 dominante → c2 → c3)
  float nc = (snoise(vec3(s*0.35+vec2(74.6,91.5), t)) + 1.0) * 0.5;
  float prog = smoothstep(0.0, 0.75, nc*nc);
  vec3 col = prog < 0.8 ? mix(uC1, uC2, prog/0.8) : mix(uC2, uC3, (prog-0.8)/0.2);
  // En tema claro las pequeñas se oscurecen sin perder el tono
  col *= mix(clamp(0.3 + e*0.45, 0.0, 1.0), 1.0, uDark);
  vColor = col;

  vAng = atan(pos.y - uRing.y, pos.x - uRing.x) + snoise(vec3(s*2.0+vec2(18.4,72.9), uTime*0.85)) * 0.5;
  vAlpha = smoothstep(0.12, 0.3, e);
  float largo = uTam * e * 2.3;                         // px de largo del guion
  vRatio = 0.36;
  gl_PointSize = max(largo, 1.0) * uDpr;
  vec2 clip = (pos / uRes) * 2.0 - 1.0;
  gl_Position = vec4(clip.x, -clip.y, 0.0, 1.0);
}`

  const FRAG = `
precision highp float;
varying float vAng, vAlpha, vRatio;
varying vec3 vColor;
void main(){
  // Cápsula orientada: largo a lo largo de vAng, ancho = vRatio del largo
  vec2 uv = gl_PointCoord - 0.5;
  uv.y = -uv.y;
  float c = cos(vAng), s = sin(vAng);
  vec2 q = vec2(c*uv.x + s*uv.y, -s*uv.x + c*uv.y);
  float r = vRatio * 0.5;
  vec2 a = abs(q) - vec2(0.5 - r, 0.0);
  float sd = length(max(a, 0.0)) + min(max(a.x, a.y), 0.0) - r;
  float alpha = vAlpha * smoothstep(0.04, -0.04, sd);
  if (alpha < 0.01) discard;
  gl_FragColor = vec4(vColor * alpha, alpha);
}`

  const hex = h => [parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255]
  // Paleta InGot sobre crema: gris cálido dominante → gris oscuro → cobre solo de acento
  const COLORES = ['#B9B2A6', '#857E72', '#A4471F'].map(hex)

  // Reparto aleatorio pero parejo (Poisson aproximado)
  function repartir(W, H, sep) {
    const celda = sep / Math.SQRT2
    const cols = Math.ceil(W / celda), filas = Math.ceil(H / celda)
    const rej = new Int32Array(cols * filas).fill(-1)
    const xs = []
    for (let n = 0; n < cols * filas * 4; n++) {
      const x = Math.random() * W, y = Math.random() * H
      const cx = Math.floor(x / celda), cy = Math.floor(y / celda)
      let libre = true
      for (let yy = Math.max(0, cy - 2); yy <= Math.min(filas - 1, cy + 2) && libre; yy++)
        for (let xx = Math.max(0, cx - 2); xx <= Math.min(cols - 1, cx + 2); xx++) {
          const k = rej[yy * cols + xx]
          if (k >= 0 && Math.hypot(xs[k * 2] - x, xs[k * 2 + 1] - y) < sep) { libre = false; break }
        }
      if (!libre) continue
      rej[cy * cols + cx] = xs.length / 2
      xs.push(x, y)
    }
    return new Float32Array(xs)
  }

  let gl = null
  try { gl = canvas.getContext('webgl', { antialias: false, alpha: true, premultipliedAlpha: true }) } catch (e) { gl = null }
  if (!gl) return // sin WebGL: la página se ve igual, solo sin partículas

  const compilar = (tipo, src) => {
    const sh = gl.createShader(tipo)
    gl.shaderSource(sh, src); gl.compileShader(sh)
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) { console.error(gl.getShaderInfoLog(sh)); return null }
    return sh
  }
  const vs = compilar(gl.VERTEX_SHADER, VERT), fs = compilar(gl.FRAGMENT_SHADER, FRAG)
  if (!vs || !fs) return
  const prog = gl.createProgram()
  gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog)
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { console.error(gl.getProgramInfoLog(prog)); return }
  gl.useProgram(prog)
  const u = n => gl.getUniformLocation(prog, n)
  const U = { res: u('uRes'), time: u('uTime'), U: u('uU'), R: u('uR'), w1: u('uW1'), w2: u('uW2'), tam: u('uTam'), dpr: u('uDpr'), dark: u('uDark'), ring: u('uRing'), c1: u('uC1'), c2: u('uC2'), c3: u('uC3') }
  const buf = gl.createBuffer()
  const aPos = gl.getAttribLocation(prog, 'aPos')
  gl.enable(gl.BLEND)
  gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA)

  const reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  let W = 0, H = 0, dpr = 1, n = 0, raf = 0, enPantalla = true
  const mouse = { x: 0, y: 0, activo: false }
  const anillo = { x: 0, y: 0 }
  canvas.estado = { anillo, mouse }          // solo lectura, para pruebas
  const inicio = performance.now()

  // Ruido 1D barato para el deambular del anillo (en el procesador, 2 valores por cuadro)
  const r1 = x => Math.sin(x * 1.3) * 0.6 + Math.sin(x * 0.7 + 1.7) * 0.4

  function crear() {
    dpr = Math.min(window.devicePixelRatio || 1, 2)
    W = canvas.clientWidth; H = canvas.clientHeight
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr)
    gl.viewport(0, 0, canvas.width, canvas.height)
    const pts = repartir(W, H, Math.max(22, H * 0.04))
    n = pts.length / 2
    gl.bindBuffer(gl.ARRAY_BUFFER, buf)
    gl.bufferData(gl.ARRAY_BUFFER, pts, gl.STATIC_DRAW)
    gl.enableVertexAttribArray(aPos)
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0)
    if (!anillo.x) { anillo.x = W * 0.5; anillo.y = H * 0.55 }
  }

  function cuadro(ahora) {
    const t = (ahora - inicio) / 1000
    const Uu = H / 2.25
    const cx = W / 2, cy = H / 2
    let ox, oy, k
    if (mouse.activo) {
      ox = cx + (mouse.x - cx) * 0.875 + r1(t * 0.66 + 9) * 0.1 * Uu
      oy = cy + (mouse.y - cy) * 0.875 + r1(t * 0.75 + 3) * 0.1 * Uu
      k = 0.03
    } else {
      ox = cx + r1(t * 0.33 + 9) * 0.45 * Uu
      oy = cy + r1(t * 0.38 + 3) * 0.22 * Uu
      k = 0.012
    }
    anillo.x += (ox - anillo.x) * k
    anillo.y += (oy - anillo.y) * k

    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT)
    gl.uniform2f(U.res, W, H)
    gl.uniform1f(U.time, t)
    gl.uniform1f(U.U, Uu)
    gl.uniform1f(U.R, Uu * (0.88 + Math.sin(t) * 0.15 + Math.cos(t * 3) * 0.1))
    gl.uniform1f(U.w1, Uu * 0.75)
    gl.uniform1f(U.w2, Uu * 0.25)
    gl.uniform1f(U.tam, Math.min(1.6, Math.max(1, W / 1200)))
    gl.uniform1f(U.dpr, dpr)
    gl.uniform1f(U.dark, 0)                  // ingot.mx es clara: las partículas pequeñas se oscurecen
    gl.uniform2f(U.ring, anillo.x, anillo.y)
    gl.uniform3fv(U.c1, COLORES[0]); gl.uniform3fv(U.c2, COLORES[1]); gl.uniform3fv(U.c3, COLORES[2])
    gl.drawArrays(gl.POINTS, 0, n)
    if (!reducir && !document.hidden && enPantalla) raf = requestAnimationFrame(cuadro)
  }

  function arrancar() { if (!reducir && !document.hidden && enPantalla) { cancelAnimationFrame(raf); raf = requestAnimationFrame(cuadro) } }
  function mover(e) {
    const r = canvas.getBoundingClientRect()
    mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top
    mouse.activo = mouse.x >= 0 && mouse.y >= 0 && mouse.x <= r.width && mouse.y <= r.height
    if (reducir) cuadro(performance.now())
  }
  const salir = () => { mouse.activo = false }
  const redimensionar = () => { crear(); if (reducir) cuadro(performance.now()) }

  crear()
  raf = requestAnimationFrame(cuadro)
  window.addEventListener('resize', redimensionar)
  // La portada también cambia de alto sin que cambie la ventana (p. ej. al cargar las fuentes)
  if ('ResizeObserver' in window) {
    let ultimo = ''
    new ResizeObserver(() => {
      const t = canvas.clientWidth + 'x' + canvas.clientHeight
      if (t !== ultimo) { ultimo = t; redimensionar() }
    }).observe(canvas)
  }
  window.addEventListener('pointermove', mover, { passive: true })
  document.documentElement.addEventListener('pointerleave', salir)
  document.addEventListener('visibilitychange', arrancar)
  // Pausa cuando la portada sale de la pantalla al hacer scroll
  if ('IntersectionObserver' in window)
    new IntersectionObserver(es => { enPantalla = es[0].isIntersecting; arrancar() }).observe(canvas)
})()
