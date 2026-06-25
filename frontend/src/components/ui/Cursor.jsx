import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { motion, useMotionValue, useSpring, useReducedMotion } from "framer-motion";

// Routes that must keep the native cursor and never get a decorative overlay.
const NO_CURSOR_ROUTES = [
  "/login", "/register", "/forgot-password",
  "/reset-password", "/verify-email", "/pending-approval",
];

// Tasteful premium cursor: a soft blended dot that springs after the pointer and
// grows over interactive elements. Additive (native cursor stays for precision),
// desktop/fine-pointer only, disabled under reduced-motion.
export default function Cursor() {
  const reduce = useReducedMotion();
  const { pathname } = useLocation();
  const disabledHere = NO_CURSOR_ROUTES.some((r) => pathname.startsWith(r));
  const [enabled, setEnabled] = useState(false);
  const [hot, setHot] = useState(false);
  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const rx = useSpring(x, { stiffness: 500, damping: 38, mass: 0.4 });
  const ry = useSpring(y, { stiffness: 500, damping: 38, mass: 0.4 });

  useEffect(() => {
    if (reduce || disabledHere || !window.matchMedia?.("(pointer: fine)").matches) {
      setEnabled(false);
      return;
    }
    setEnabled(true);
    const move = (e) => {
      x.set(e.clientX);
      y.set(e.clientY);
      const el = e.target?.closest?.("a, button, [role='button'], input, select, textarea, [data-cursor]");
      setHot(!!el);
    };
    window.addEventListener("mousemove", move, { passive: true });
    return () => window.removeEventListener("mousemove", move);
  }, [reduce, disabledHere, x, y]);

  if (!enabled || disabledHere) return null;
  return (
    <motion.div
      aria-hidden
      className="pointer-events-none fixed left-0 top-0 z-[9999] rounded-full"
      style={{
        x: rx,
        y: ry,
        translateX: "-50%",
        translateY: "-50%",
        width: hot ? 38 : 12,
        height: hot ? 38 : 12,
        background: hot ? "rgba(79,126,255,0.9)" : "rgba(255,255,255,0.85)",
        mixBlendMode: "difference",
        transition: "width .22s ease, height .22s ease, background-color .22s ease",
      }}
    />
  );
}
