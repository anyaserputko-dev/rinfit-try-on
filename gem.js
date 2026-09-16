// Ray-traced cut stone for the realtime views.
// A cut stone is a convex solid, so light inside it can be traced exactly against its facet planes:
// the ray enters through the front facet, refracts, bounces off the facets (total internal reflection or
// Fresnel) and leaves towards the environment. The environment is the same "light tent" used for the Blender
// renders (blender/rinfit.py _tent_world + soft boxes), set in view space, so web and renders read alike.
import * as THREE from "three";

// A 16-sector stone has ~180 facet planes; rectangles with split girdles can go higher, and a stone whose
// planes get truncated leaks light and renders pale, so keep headroom and say so when it still does not fit.
const MAX_PLANES = 384;

// Unique outward facet planes (normal, distance) of a convex mesh, in the mesh's local space.
export function facetPlanes(geometry) {
  const pos = geometry.attributes.position, idx = geometry.index;
  const count = idx ? idx.count : pos.count;
  const centre = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) centre.add(new THREE.Vector3().fromBufferAttribute(pos, i));
  centre.divideScalar(pos.count);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const planes = [];
  for (let i = 0; i < count; i += 3) {
    const ia = idx ? idx.getX(i) : i, ib = idx ? idx.getX(i + 1) : i + 1, ic = idx ? idx.getX(i + 2) : i + 2;
    a.fromBufferAttribute(pos, ia); b.fromBufferAttribute(pos, ib); c.fromBufferAttribute(pos, ic);
    const n = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(c, a));
    if (n.lengthSq() < 1e-10) continue;
    n.normalize();
    if (n.dot(new THREE.Vector3().subVectors(a, centre)) < 0) n.negate();
    const d = n.dot(a);
    if (!planes.some((p) => p.n.dot(n) > 0.99995 && Math.abs(p.d - d) < 0.01)) planes.push({ n, d });
  }
  return planes;
}

const vertexShader = /* glsl */ `
  varying vec3 vPos;
  varying vec3 vNormalLocal;
  varying vec3 vDirLocal;
  varying vec3 vR0;
  varying vec3 vR1;
  varying vec3 vR2;
  void main() {
    vec4 viewPos = modelViewMatrix * vec4(position, 1.0);
    mat3 R = mat3(normalize(normalMatrix[0]), normalize(normalMatrix[1]), normalize(normalMatrix[2]));
    vec3 dv = isOrthographic ? vec3(0.0, 0.0, -1.0) : viewPos.xyz;
    vDirLocal = transpose(R) * dv;
    vPos = position;
    vNormalLocal = normal;
    vR0 = R[0]; vR1 = R[1]; vR2 = R[2];
    gl_Position = projectionMatrix * viewPos;
  }
`;

const fragmentShader = /* glsl */ `
  #define MAX_PLANES ${MAX_PLANES}
  uniform vec4 uPlanes[MAX_PLANES];
  uniform int uCount;
  uniform float uIor;
  uniform float uDispersion;
  uniform int uBounces;
  uniform float uBody;        // how much light gets through the stone (1 clear, ~0 black)
  uniform vec3 uTint;
  uniform float uExposure;
  varying vec3 vPos;
  varying vec3 vNormalLocal;
  varying vec3 vDirLocal;
  varying vec3 vR0;
  varying vec3 vR1;
  varying vec3 vR2;

  // light tent in view space: z towards the viewer (where the camera and its dark stand are)
  float softbox(vec3 d, vec3 dir, float cosSize, float strength) {
    return strength * smoothstep(cosSize - 0.01, cosSize + 0.01, dot(d, normalize(dir)));
  }
  float tent(vec3 d) {
    float az = atan(d.y, d.x);
    // soft edges: hard steps alias into coloured speckles on small facets
    float card = smoothstep(0.5, 0.6, sin(az * 9.0));
    float band = 1.0 - smoothstep(0.55, 0.65, abs(d.z));
    float floorM = 1.0 - smoothstep(-0.65, -0.55, d.z);
    float v = (1.4 - floorM * (1.4 - 0.9)) * (1.0 - card * band * 0.97);
    v *= 1.0 - smoothstep(0.72, 0.78, d.z) * 0.96;
    v += softbox(d, vec3(0.34, -0.45, 0.8), 0.95, 2.0);
    v += softbox(d, vec3(-0.9, -0.25, 0.35), 0.93, 0.9);
    v += softbox(d, vec3(0.5, 0.8, 0.45), 0.94, 1.2);
    v += softbox(d, vec3(0.0, 0.0, 1.0), 0.94, 0.7);
    return v;
  }
  vec3 envLocal(vec3 dl) {
    vec3 dv = normalize(vR0 * dl.x + vR1 * dl.y + vR2 * dl.z);
    return vec3(tent(dv));
  }
  float schlick(float cosT, float ior) {
    float r0 = (ior - 1.0) / (ior + 1.0);
    r0 *= r0;
    return r0 + (1.0 - r0) * pow(clamp(1.0 - cosT, 0.0, 1.0), 5.0);
  }

  void main() {
    vec3 d = normalize(vDirLocal);
    vec3 n = normalize(vNormalLocal);
    if (dot(n, d) > 0.0) n = -n;
    float cosI = clamp(dot(-d, n), 0.0, 1.0);
    float F = schlick(cosI, uIor);
    vec3 color = F * envLocal(reflect(d, n));

    vec3 t = refract(d, n, 1.0 / uIor);
    vec3 p = vPos;
    float w = (1.0 - F) * uBody;
    int last = -1;
    for (int b = 0; b < 8; b++) {
      if (b >= uBounces || w < 0.01) break;
      float tmin = 1e9;
      int hit = -1;
      for (int i = 0; i < MAX_PLANES; i++) {
        if (i >= uCount) break;
        if (i == last) continue;
        vec3 pn = uPlanes[i].xyz;
        float den = dot(t, pn);
        if (den > 1e-5) {
          float s = (uPlanes[i].w - dot(p, pn)) / den;
          if (s > -1e-4 && s < tmin) { tmin = s; hit = i; }
        }
      }
      if (hit < 0) break;
      p += t * tmin;
      vec3 nn = uPlanes[hit].xyz;
      last = hit;
      vec3 outG = refract(t, -nn, uIor);
      if (dot(outG, outG) < 1e-6) { t = reflect(t, -nn); continue; }   // total internal reflection
      float Fi = schlick(dot(outG, nn), uIor);
      // a little fire: each colour channel leaves at its own angle
      vec3 outR = refract(t, -nn, uIor - uDispersion);
      vec3 outB = refract(t, -nn, uIor + uDispersion);
      vec3 e = vec3(envLocal(dot(outR, outR) > 1e-6 ? outR : outG).r, envLocal(outG).g,
                    envLocal(dot(outB, outB) > 1e-6 ? outB : outG).b);
      color += w * (1.0 - Fi) * e * uTint;
      w *= Fi;
      t = reflect(t, -nn);
    }
    // light still trapped after the last bounce: let it out along the current direction instead of going black
    color += w * envLocal(t) * uTint * 0.85;
    gl_FragColor = vec4(color * uExposure, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

export function stoneMaterial(geometry, { black = false } = {}) {
  const all = facetPlanes(geometry);
  if (all.length > MAX_PLANES) console.warn(`gem: stone has ${all.length} facet planes, only ${MAX_PLANES} traced`);
  const planes = all.slice(0, MAX_PLANES);
  const packed = Array.from({ length: MAX_PLANES }, (_, i) =>
    planes[i] ? new THREE.Vector4(planes[i].n.x, planes[i].n.y, planes[i].n.z, planes[i].d) : new THREE.Vector4());
  const material = new THREE.ShaderMaterial({
    name: black ? "CZ_Black_traced" : "CZ_traced",
    uniforms: {
      uPlanes: { value: packed },
      uCount: { value: planes.length },
      uIor: { value: 2.16 },
      uDispersion: { value: black ? 0 : 0.015 },
      uBounces: { value: black ? 0 : 7 },
      uBody: { value: black ? 0.0 : 1.0 },
      uTint: { value: new THREE.Color(black ? 0x000000 : 0xffffff) },
      uExposure: { value: black ? 0.9 : 1.0 }
    },
    vertexShader, fragmentShader
  });
  // the app multiplies these by the light it samples from the camera frame
  material.userData.baseTint = material.uniforms.uTint.value.clone();
  material.userData.baseExposure = material.uniforms.uExposure.value;
  return material;
}
