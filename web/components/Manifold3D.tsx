"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { useMemo, useRef, useState, useEffect } from "react";
import * as THREE from "three";
import type { Manifold, ManifoldPoint, Stage } from "@/lib/types";
import { STAGE_COLORS, STAGE_LABELS } from "@/lib/types";

function PointCloud({
  points,
  highlightedStage,
  highProbBoost,
}: {
  points: ManifoldPoint[];
  highlightedStage: Stage | null;
  highProbBoost: boolean;
}) {
  const ref = useRef<THREE.Points>(null);
  const t = useRef(0);

  // Auto-rotate slowly when not interacting (paused if user touches OrbitControls)
  useFrame((_, dt) => {
    if (ref.current) {
      t.current += dt;
      ref.current.rotation.y = t.current * 0.06;
    }
  });

  const { geometry, material } = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const positions = new Float32Array(points.length * 3);
    const colors    = new Float32Array(points.length * 3);
    const sizes     = new Float32Array(points.length);

    const maxProb = Math.max(...points.map((p) => p.prob), 1e-9);

    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      positions[i * 3 + 0] = p.x;
      positions[i * 3 + 1] = p.y;
      positions[i * 3 + 2] = p.z;
      const hex = STAGE_COLORS[p.stage] ?? "#666";
      const c = new THREE.Color(hex);
      const dim = highlightedStage && p.stage !== highlightedStage ? 0.18 : 1.0;
      colors[i * 3 + 0] = c.r * dim;
      colors[i * 3 + 1] = c.g * dim;
      colors[i * 3 + 2] = c.b * dim;

      const probBoost = highProbBoost ? Math.pow(p.prob / maxProb, 0.7) : 0;
      sizes[i] = 0.03 + probBoost * 0.16;
    }

    g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    g.setAttribute("color",    new THREE.BufferAttribute(colors, 3));
    g.setAttribute("size",     new THREE.BufferAttribute(sizes, 1));

    const m = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: `
        attribute float size;
        attribute vec3 color;
        varying vec3 vColor;
        void main() {
          vColor = color;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = size * (260.0 / -mv.z);
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        void main() {
          float d = length(gl_PointCoord - vec2(0.5));
          if (d > 0.5) discard;
          float alpha = smoothstep(0.5, 0.0, d);
          gl_FragColor = vec4(vColor * 1.6, alpha * 0.9);
        }
      `,
    });

    return { geometry: g, material: m };
  }, [points, highlightedStage, highProbBoost]);

  return <points ref={ref} geometry={geometry} material={material} />;
}

export default function Manifold3D({ manifold }: { manifold: Manifold }) {
  const [highlightedStage, setHighlightedStage] = useState<Stage | null>(null);
  const [highProbBoost, setHighProbBoost] = useState(true);

  const stages = useMemo(() => {
    const set = new Set<Stage>();
    manifold.points.forEach((p) => set.add(p.stage));
    return Array.from(set).sort();
  }, [manifold]);

  const evr = manifold.explained_variance;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_240px] gap-4">
      <div className="glass rounded-2xl overflow-hidden h-[600px] relative">
        <Canvas
          camera={{ position: [3.5, 3.5, 3.5], fov: 50 }}
          dpr={[1, 2]}
          gl={{ antialias: true, alpha: true }}
          style={{ background: "transparent" }}
        >
          <ambientLight intensity={0.3} />
          <Stars radius={60} depth={20} count={2200} factor={3.2} fade speed={0.4} />
          <PointCloud
            points={manifold.points}
            highlightedStage={highlightedStage}
            highProbBoost={highProbBoost}
          />
          <OrbitControls
            enableDamping
            dampingFactor={0.07}
            rotateSpeed={0.8}
            zoomSpeed={0.6}
            autoRotate={false}
          />
          <EffectComposer>
            <Bloom
              intensity={1.4}
              luminanceThreshold={0.18}
              luminanceSmoothing={0.45}
              mipmapBlur
            />
          </EffectComposer>
        </Canvas>
        <div className="absolute bottom-3 left-4 text-xs text-slate-400 pointer-events-none font-mono">
          PCA explains {(evr.reduce((a, b) => a + b, 0) * 100).toFixed(1)}% — drag to rotate, scroll to zoom
        </div>
      </div>

      <div className="space-y-4">
        <div className="glass rounded-2xl p-4">
          <div className="text-xs uppercase tracking-wider text-slate-400 mb-3">stages</div>
          <div className="space-y-1.5">
            {stages.map((s) => {
              const active = highlightedStage === s;
              return (
                <button
                  key={s}
                  onClick={() => setHighlightedStage(active ? null : s)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition ${
                    active ? "bg-slate-700/50" : "hover:bg-slate-700/30"
                  }`}
                >
                  <span
                    className="w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: STAGE_COLORS[s], boxShadow: `0 0 6px ${STAGE_COLORS[s]}` }}
                  />
                  <span className="flex-1 text-left text-slate-300">{STAGE_LABELS[s]}</span>
                  <span className="text-slate-500 font-mono">
                    {manifold.points.filter((p) => p.stage === s).length}
                  </span>
                </button>
              );
            })}
            {highlightedStage && (
              <button
                onClick={() => setHighlightedStage(null)}
                className="w-full mt-1 text-xs text-slate-500 hover:text-slate-300 py-1"
              >
                clear filter
              </button>
            )}
          </div>
        </div>
        <div className="glass rounded-2xl p-4">
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={highProbBoost}
              onChange={(e) => setHighProbBoost(e.target.checked)}
              className="accent-pink-500"
            />
            emphasize high upgrade-prob users
          </label>
        </div>
      </div>
    </div>
  );
}
