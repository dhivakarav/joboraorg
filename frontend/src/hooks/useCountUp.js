import { useEffect, useState } from "react";
import { animate, useReducedMotion } from "framer-motion";

// Counts a value from 0 → `to` with GPU-light state updates. Respects
// reduced-motion (snaps to final). Reusable across stats, match scores, etc.
export function useCountUp(to, { duration = 2, delay = 0, start = true } = {}) {
  const reduce = useReducedMotion();
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!start) return;
    if (reduce) { setVal(to); return; }
    const controls = animate(0, to, { duration, delay, ease: "easeOut", onUpdate: setVal });
    return () => controls.stop();
  }, [to, duration, delay, start, reduce]);
  return val;
}
