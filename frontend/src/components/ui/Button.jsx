import { useState } from "react";
import { motion } from "framer-motion";
import { useMagnetic } from "../../hooks/useMagnetic";

// Premium button: magnetic hover, ripple on click, press feedback, variants.
// variant: "primary" (white) | "accent" (electric blue) | "ghost"
export default function Button({
  variant = "primary",
  magnetic = true,
  className = "",
  children,
  onClick,
  ...props
}) {
  const mag = useMagnetic();
  const [ripples, setRipples] = useState([]);

  function handleClick(e) {
    const r = e.currentTarget.getBoundingClientRect();
    const id = Date.now() + Math.random();
    setRipples((rs) => [...rs, { id, x: e.clientX - r.left, y: e.clientY - r.top }]);
    setTimeout(() => setRipples((rs) => rs.filter((x) => x.id !== id)), 600);
    onClick?.(e);
  }

  const base =
    "relative overflow-hidden inline-flex items-center justify-center gap-2 rounded-btn px-4 py-2.5 text-sm font-semibold " +
    "transition-[transform,box-shadow,background-color] duration-200 active:scale-[0.98] " +
    "disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100";
  const variants = {
    primary: "bg-brand text-white hover:bg-brand-hover hover:shadow-glow-l hover:-translate-y-px",
    accent: "bg-brand text-white hover:shadow-glow-l hover:-translate-y-px",
    ghost: "border border-edge bg-white text-ink hover:bg-canvas hover:-translate-y-px",
  };

  return (
    <motion.button
      {...props}
      onClick={handleClick}
      style={magnetic ? { x: mag.x, y: mag.y } : undefined}
      onMouseMove={magnetic ? mag.onMouseMove : undefined}
      onMouseLeave={magnetic ? mag.onMouseLeave : undefined}
      className={`${base} ${variants[variant] || variants.primary} ${className}`}
    >
      <span className="relative z-10 inline-flex items-center justify-center gap-2">{children}</span>
      {ripples.map((rp) => (
        <span
          key={rp.id}
          className="pointer-events-none absolute z-0 rounded-full bg-current/25"
          style={{ left: rp.x, top: rp.y, width: 10, height: 10, animation: "ripple 0.6s ease-out forwards" }}
        />
      ))}
    </motion.button>
  );
}
