"use client";

/**
 * Pure-CSS animated gradient mesh — no WebGL.
 *
 * The 3D manifold elsewhere on the page already owns one WebGL context, and
 * Safari refuses to host two on the same page (context-lost crash). So we use
 * stacked, blurred, slowly-drifting radial-gradients to fake a shader mesh.
 * Visual budget is ~1ms/frame on the GPU compositor.
 */
export default function ShaderBackground() {
  return (
    <div className="fixed inset-0 -z-10 pointer-events-none overflow-hidden" aria-hidden>
      {/* Drifting blobs */}
      <div className="absolute -top-32 -left-24 w-[640px] h-[640px] rounded-full opacity-60 blur-[140px]"
           style={{ background: "radial-gradient(circle, #ec4899, transparent 65%)", animation: "blobA 24s ease-in-out infinite" }} />
      <div className="absolute top-10 right-0 w-[560px] h-[560px] rounded-full opacity-50 blur-[140px]"
           style={{ background: "radial-gradient(circle, #8b5cf6, transparent 65%)", animation: "blobB 30s ease-in-out infinite" }} />
      <div className="absolute top-1/3 left-1/3 w-[520px] h-[520px] rounded-full opacity-45 blur-[140px]"
           style={{ background: "radial-gradient(circle, #06b6d4, transparent 70%)", animation: "blobC 28s ease-in-out infinite" }} />
      <div className="absolute bottom-0 -right-24 w-[600px] h-[600px] rounded-full opacity-30 blur-[140px]"
           style={{ background: "radial-gradient(circle, #14b8a6, transparent 70%)", animation: "blobA 36s ease-in-out infinite reverse" }} />

      {/* Subtle grid overlay */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(148,163,184,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.05) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage: "radial-gradient(ellipse at 50% 30%, rgba(0,0,0,0.85), transparent 75%)",
          WebkitMaskImage: "radial-gradient(ellipse at 50% 30%, rgba(0,0,0,0.85), transparent 75%)",
        }}
      />

      {/* Heavy bottom vignette so content stays readable */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-ink-950/40 to-ink-950/85" />
    </div>
  );
}
