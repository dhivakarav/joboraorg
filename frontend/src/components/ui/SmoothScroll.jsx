import { useEffect } from "react";
import Lenis from "lenis";
import { useReducedMotion } from "framer-motion";

// App-wide buttery scrolling (Lenis). Disabled under reduced-motion. Internal
// scroll containers can opt out with `data-lenis-prevent`.
export default function SmoothScroll({ children }) {
  const reduce = useReducedMotion();
  useEffect(() => {
    if (reduce) return;
    const lenis = new Lenis({ duration: 1.05, lerp: 0.1, smoothWheel: true });
    let raf;
    const loop = (t) => {
      lenis.raf(t);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      lenis.destroy();
    };
  }, [reduce]);
  return children;
}
