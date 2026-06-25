import { useMotionValue, useSpring, useReducedMotion } from "framer-motion";

// Magnetic hover: an element gently follows the cursor, springing back on leave.
// Returns spring-backed x/y motion values + the handlers to spread on the element.
export function useMagnetic({ strengthX = 0.25, strengthY = 0.4 } = {}) {
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 300, damping: 20 });
  const sy = useSpring(y, { stiffness: 300, damping: 20 });

  function onMouseMove(e) {
    if (reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    x.set((e.clientX - (r.left + r.width / 2)) * strengthX);
    y.set((e.clientY - (r.top + r.height / 2)) * strengthY);
  }
  function onMouseLeave() {
    x.set(0);
    y.set(0);
  }
  return { x: sx, y: sy, onMouseMove, onMouseLeave };
}
