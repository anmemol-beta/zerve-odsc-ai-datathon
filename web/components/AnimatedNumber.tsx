"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Counts up from 0 to `value` once on mount, easing-out.
 * Tries to be visually present without jank — 1.2s spring, then locks.
 */
export default function AnimatedNumber({
  value,
  duration = 1200,
  format = (n: number) => Math.round(n).toLocaleString(),
}: {
  value: number;
  duration?: number;
  format?: (n: number) => string;
}) {
  const [display, setDisplay] = useState(0);
  const start = useRef<number | null>(null);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    const animate = (t: number) => {
      if (start.current === null) start.current = t;
      const elapsed = t - start.current;
      const k = Math.min(1, elapsed / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - k, 3);
      setDisplay(value * eased);
      if (k < 1) raf.current = requestAnimationFrame(animate);
      else setDisplay(value);
    };
    raf.current = requestAnimationFrame(animate);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [value, duration]);

  return <>{format(display)}</>;
}
