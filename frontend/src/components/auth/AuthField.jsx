import { useState } from "react";
import { motion } from "framer-motion";

// Reusable premium auth input (LIGHT): floating label, blue focus glow,
// animated success checkmark when `valid`, optional password toggle.
export default function AuthField({
  id, label, type = "text", value, onChange,
  autoComplete, required, valid = false, isPassword = false,
}) {
  const [focused, setFocused] = useState(false);
  const [reveal, setReveal] = useState(false);
  const float = focused || (value && value.length > 0);
  const inputType = isPassword ? (reveal ? "text" : "password") : type;
  const pr = isPassword ? "pr-20" : valid ? "pr-10" : "pr-3.5";

  return (
    <div className="brand-glow relative rounded-[14px] border border-edge bg-white transition-[border-color,box-shadow] duration-200">
      <input
        id={id}
        type={inputType}
        value={value}
        onChange={onChange}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        autoComplete={autoComplete}
        required={required}
        placeholder=" "
        className={`peer w-full rounded-[14px] bg-transparent px-3.5 pt-5 pb-2 text-sm text-ink outline-none ${pr}`}
      />
      <label
        htmlFor={id}
        className={`pointer-events-none absolute left-3.5 origin-left font-medium transition-all duration-200 ${
          float
            ? `top-1.5 text-[11px] tracking-wide ${focused ? "text-brand" : "text-ink-soft"}`
            : "top-1/2 -translate-y-1/2 text-sm text-ink-soft"
        }`}
      >
        {label}
      </label>

      {valid && (
        <motion.svg
          className={`absolute top-1/2 -translate-y-1/2 ${isPassword ? "right-14" : "right-3.5"} text-ok`}
          width="16" height="16" viewBox="0 0 24 24" fill="none"
          initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 500, damping: 22 }}
        >
          <motion.path d="M4 12.5l5 5 11-11" stroke="currentColor" strokeWidth="2.5"
            strokeLinecap="round" strokeLinejoin="round"
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.35, delay: 0.05 }} />
        </motion.svg>
      )}

      {isPassword && (
        <button type="button" onClick={() => setReveal((v) => !v)}
          aria-label={reveal ? "Hide password" : "Show password"}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-2 py-1 text-xs font-medium text-ink-soft transition-colors hover:text-ink">
          {reveal ? "Hide" : "Show"}
        </button>
      )}
    </div>
  );
}
