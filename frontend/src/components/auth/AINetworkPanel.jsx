import { lazy, Suspense } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { useCountUp } from "../../hooks/useCountUp";

// Three.js is heavy — load the globe only when this panel mounts (login page).
const Globe3D = lazy(() => import("./Globe3D"));

// Left split-screen panel (LIGHT theme): an "AI preparing your career" scene —
// a living neural network (blue nodes + drawing connection lines on a soft blue
// gradient mesh), slowly drifting white job cards whose match scores count up,
// ambient particles, and live hiring stats. Transform/opacity only for 60fps;
// honors prefers-reduced-motion.

const VB = { w: 440, h: 560 };
const NODES = [
  [70, 90], [200, 60], [350, 110], [120, 210], [270, 195],
  [380, 280], [80, 340], [220, 320], [160, 450], [330, 420],
];
const EDGES = [
  [0, 1], [1, 2], [0, 3], [1, 4], [2, 5], [3, 4], [3, 6],
  [4, 7], [5, 9], [6, 7], [7, 8], [7, 9], [8, 9], [4, 5],
];

const JOB_CARDS = [
  { title: "Senior Frontend Engineer", company: "Northwind", score: 96, top: "12%", left: "6%", dur: 9 },
  { title: "ML Engineer", company: "Helix AI", score: 92, top: "31%", left: "44%", dur: 11 },
  { title: "Product Designer", company: "Arcadia", score: 89, top: "50%", left: "9%", dur: 10 },
];

const STATS = [
  { label: "Jobs matched today", to: 12480, fmt: (v) => Math.round(v).toLocaleString() },
  { label: "Interviews booked", to: 3215, fmt: (v) => Math.round(v).toLocaleString() },
  { label: "Avg match accuracy", to: 98, fmt: (v) => Math.round(v) + "%" },
];

function CountUp({ to, fmt = (v) => Math.round(v), duration, delay }) {
  return <>{fmt(useCountUp(to, { duration, delay }))}</>;
}

export default function AINetworkPanel({ boosted = false }) {
  const reduce = useReducedMotion();

  return (
    <div className="relative h-full w-full overflow-hidden bg-canvas">
      {/* Soft blue gradient mesh */}
      <div className="absolute inset-0" style={{
        background:
          "radial-gradient(70% 55% at 25% 18%, rgba(37,99,235,0.12), transparent 60%)," +
          "radial-gradient(60% 60% at 85% 85%, rgba(37,99,235,0.10), transparent 60%)," +
          "linear-gradient(180deg, #F8FAFC 0%, #EEF4FF 100%)",
      }} />

      {/* Rotating 3D globe (Three.js) — the panel's hero backdrop */}
      <motion.div
        className="absolute inset-0"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: boosted ? 1 : 0.92, scale: 1 }}
        transition={{ duration: 1.2, ease: "easeOut" }}
      >
        <Suspense fallback={null}><Globe3D className="h-full w-full" /></Suspense>
      </motion.div>

      {/* Scrims — fade the globe behind the foreground copy so text stays crisp */}
      <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-[58%]" style={{
        background: "linear-gradient(to top, #EEF4FF 4%, rgba(238,244,255,0.86) 34%, rgba(238,244,255,0) 100%)",
      }} />
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[18%]" style={{
        background: "linear-gradient(to bottom, #F8FAFC 0%, rgba(248,250,252,0) 100%)",
      }} />

      {/* Floating job cards (white, drift + counting match score) */}
      {JOB_CARDS.map((j, i) => (
        <motion.div key={i}
          className="absolute w-[220px] rounded-[18px] border border-edge bg-white p-4 shadow-lift-l"
          style={{ top: j.top, left: j.left }}
          initial={{ opacity: 0, y: 16 }}
          animate={reduce ? { opacity: 1, y: 0 } : { opacity: 1, y: [0, -14, 0] }}
          transition={reduce ? { duration: 0.6, delay: 0.4 + i * 0.15 }
            : { opacity: { duration: 0.8, delay: 0.5 + i * 0.2 }, y: { duration: j.dur, repeat: Infinity, ease: "easeInOut" } }}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider text-ink-soft">{j.company}</span>
            <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-semibold text-brand">
              <CountUp to={j.score} fmt={(v) => Math.round(v) + "%"} duration={1.6} delay={0.8 + i * 0.2} /> match
            </span>
          </div>
          <div className="mt-2 text-sm font-semibold text-ink">{j.title}</div>
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-canvas">
            <motion.div className="h-full rounded-full bg-brand"
              initial={{ width: 0 }} animate={{ width: `${j.score}%` }}
              transition={{ duration: 1.6, delay: 0.8 + i * 0.2, ease: "easeOut" }} />
          </div>
        </motion.div>
      ))}

      {/* Copy + live stats */}
      <div className="absolute inset-x-0 bottom-0 p-10">
        <motion.h2 className="max-w-sm text-[26px] font-semibold leading-snug tracking-tight text-ink"
          initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.3 }}>
          Your AI is preparing<br />your career journey.
        </motion.h2>
        <motion.p className="mt-2 max-w-sm text-sm text-ink-soft"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.7, delay: 0.5 }}>
          Matching your skills to real openings across India, Dubai &amp; Singapore — in real time.
        </motion.p>
        <div className="mt-7 grid grid-cols-3 gap-4">
          {STATS.map((s, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.6 + i * 0.12 }}>
              <div className="text-xl font-bold tracking-tight text-ink tabular-nums">
                <CountUp to={s.to} fmt={s.fmt} duration={2} delay={0.8 + i * 0.15} />
              </div>
              <div className="mt-0.5 text-[11px] text-ink-soft">{s.label}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
