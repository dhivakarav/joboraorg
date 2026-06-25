import { useCountUp } from "../../hooks/useCountUp";

// Renders a number counting from 0 → `to`. `format` controls display.
export default function CountUp({ to, duration, delay, start, format = (v) => Math.round(v).toLocaleString(), className }) {
  const val = useCountUp(to, { duration, delay, start });
  return <span className={className}>{format(val)}</span>;
}
