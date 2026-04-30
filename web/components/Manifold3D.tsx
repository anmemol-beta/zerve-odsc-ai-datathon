"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls, Line, Text } from "@react-three/drei";
import { useMemo, useRef, useState, useEffect } from "react";
import * as THREE from "three";
import type { Manifold, ManifoldPoint, Stage } from "@/lib/types";
import { STAGE_COLORS, STAGE_LABELS } from "@/lib/types";

function Axes({ length = 2.2 }: { length?: number }) {
  const axes: { dir: [number, number, number]; color: string; label: string }[] = [
    { dir: [1, 0, 0], color: "#ec4899", label: "PC1" },
    { dir: [0, 1, 0], color: "#8b5cf6", label: "PC2" },
    { dir: [0, 0, 1], color: "#06b6d4", label: "PC3" },
  ];
  return (
    <group>
      {axes.map(({ dir, color, label }) => {
        const tip: [number, number, number] = [dir[0] * length, dir[1] * length, dir[2] * length];
        const labelPos: [number, number, number] = [dir[0] * (length + 0.28), dir[1] * (length + 0.28), dir[2] * (length + 0.28)];
        // Cone rotation: default cone points +Y, rotate to match dir
        let rot: [number, number, number] = [0, 0, 0];
        if (dir[0] === 1) rot = [0, 0, -Math.PI / 2];
        else if (dir[2] === 1) rot = [Math.PI / 2, 0, 0];
        return (
          <group key={label}>
            <Line points={[[0, 0, 0], tip]} color={color} lineWidth={1.6} transparent opacity={0.85} />
            <mesh position={tip} rotation={rot}>
              <coneGeometry args={[0.045, 0.16, 12]} />
              <meshBasicMaterial color={color} />
            </mesh>
            <Text
              position={labelPos}
              fontSize={0.18}
              color={color}
              anchorX="center"
              anchorY="middle"
              outlineWidth={0.008}
              outlineColor="#000"
            >
              {label}
            </Text>
          </group>
        );
      })}
    </group>
  );
}

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
          vec2 uv = gl_PointCoord - vec2(0.5);
          float d = length(uv);
          if (d > 0.5) discard;
          // hot core + soft halo for fake bloom
          float core = smoothstep(0.18, 0.0, d);
          float halo = smoothstep(0.5, 0.18, d);
          float alpha = clamp(core + halo * 0.6, 0.0, 1.0);
          vec3 col = vColor * (1.0 + core * 1.4) + vec3(core * 0.35);
          gl_FragColor = vec4(col, alpha * 0.95);
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
      <div
        className="rounded-2xl overflow-hidden h-[600px] relative border border-slate-800/60"
        style={{ background: "#03060f" }}
      >
        <Canvas
          camera={{ position: [3.5, 3.5, 3.5], fov: 50 }}
          dpr={[1, 2]}
          gl={{ antialias: true, alpha: false }}
          style={{ background: "#03060f" }}
        >
          <ambientLight intensity={0.3} />
          <Axes length={2.2} />
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
