"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";

const VERT = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

// 3-color flowing gradient mesh, à la Linear / Stripe / Vercel landing pages.
const FRAG = /* glsl */ `
  precision highp float;
  varying vec2 vUv;
  uniform float uTime;
  uniform vec2  uMouse;
  uniform vec3  uA;
  uniform vec3  uB;
  uniform vec3  uC;

  // simplex-ish noise — cheap and good enough for backdrops
  vec3 mod289(vec3 x){return x - floor(x * (1.0 / 289.0)) * 289.0;}
  vec2 mod289(vec2 x){return x - floor(x * (1.0 / 289.0)) * 289.0;}
  vec3 permute(vec3 x){return mod289(((x*34.0)+1.0)*x);}
  float snoise(vec2 v){
    const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
    vec2 i  = floor(v + dot(v, C.yy));
    vec2 x0 = v -   i + dot(i, C.xx);
    vec2 i1; i1 = (x0.x > x0.y) ? vec2(1.0,0.0) : vec2(0.0,1.0);
    vec4 x12 = x0.xyxy + C.xxzz; x12.xy -= i1;
    i = mod289(i);
    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
    vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
    m = m*m; m = m*m;
    vec3 x = 2.0 * fract(p * C.www) - 1.0;
    vec3 h = abs(x) - 0.5;
    vec3 ox = floor(x + 0.5);
    vec3 a0 = x - ox;
    m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
    vec3 g;
    g.x  = a0.x  * x0.x   + h.x  * x0.y;
    g.yz = a0.yz * x12.xz + h.yz * x12.yw;
    return 130.0 * dot(m, g);
  }

  void main() {
    vec2 uv = vUv;
    float t = uTime * 0.07;
    float n1 = snoise(uv * 1.7 + vec2(t, -t * 0.6));
    float n2 = snoise(uv * 2.3 + vec2(-t * 0.8, t * 1.1) + uMouse * 0.2);
    float n3 = snoise(uv * 1.1 + vec2(t * 0.4, t * 0.5));

    float a = 0.5 + 0.5 * n1;
    float b = 0.5 + 0.5 * n2;
    float c = 0.5 + 0.5 * n3;

    vec3 col = mix(uA, uB, smoothstep(0.0, 1.0, a));
    col = mix(col, uC, smoothstep(0.2, 0.9, b));
    col *= 0.6 + 0.5 * c;

    // Heavy vignette so the background fades out at edges
    float d = distance(vUv, vec2(0.5));
    col *= smoothstep(0.95, 0.2, d);

    gl_FragColor = vec4(col, 1.0);
  }
`;

function Plane() {
  const ref = useRef<THREE.ShaderMaterial>(null);
  const mouse = useRef<THREE.Vector2>(new THREE.Vector2(0, 0));

  useFrame(({ pointer, clock }) => {
    if (!ref.current) return;
    mouse.current.lerp(pointer, 0.05);
    ref.current.uniforms.uMouse.value = mouse.current;
    ref.current.uniforms.uTime.value = clock.getElapsedTime();
  });

  return (
    <mesh>
      <planeGeometry args={[5, 3, 1, 1]} />
      <shaderMaterial
        ref={ref}
        vertexShader={VERT}
        fragmentShader={FRAG}
        uniforms={{
          uTime:  { value: 0 },
          uMouse: { value: new THREE.Vector2(0, 0) },
          uA:     { value: new THREE.Color("#ec4899") },
          uB:     { value: new THREE.Color("#8b5cf6") },
          uC:     { value: new THREE.Color("#06b6d4") },
        }}
      />
    </mesh>
  );
}

export default function ShaderBackground() {
  return (
    <div className="fixed inset-0 -z-10 opacity-50 pointer-events-none" aria-hidden>
      <Canvas
        orthographic
        camera={{ position: [0, 0, 1], zoom: 100 }}
        gl={{ antialias: false, alpha: true }}
        dpr={[1, 1.5]}
      >
        <Plane />
      </Canvas>
      {/* Grid overlay */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(148,163,184,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.06) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage: "radial-gradient(ellipse at 50% 35%, rgba(0,0,0,0.85), transparent 75%)",
          WebkitMaskImage: "radial-gradient(ellipse at 50% 35%, rgba(0,0,0,0.85), transparent 75%)",
        }}
      />
    </div>
  );
}
