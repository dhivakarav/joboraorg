// Premium, reusable auth shell — monochrome spotlight + masked grid texture,
// glassmorphic card, animated wordmark. Used by the redesigned auth screens.
// Pure CSS animations (GPU-friendly, reduced-motion aware). No logic here.
export default function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-bg text-ink flex items-center justify-center px-4 py-10">
      {/* Ambient background: drifting white spotlight + edge-masked grid */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div
          className="absolute left-1/2 top-[-25%] h-[70vmax] w-[70vmax] -translate-x-1/2 rounded-full blur-3xl opacity-[0.10] animate-spotlight"
          style={{
            background:
              "radial-gradient(circle at 50% 50%, rgba(255,255,255,0.9), rgba(255,255,255,0.15) 38%, transparent 70%)",
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.05]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.8) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.8) 1px, transparent 1px)",
            backgroundSize: "46px 46px",
            WebkitMaskImage: "radial-gradient(circle at 50% 42%, black, transparent 72%)",
            maskImage: "radial-gradient(circle at 50% 42%, black, transparent 72%)",
          }}
        />
      </div>

      <div className="relative w-full max-w-md">
        <div className="text-center mb-8 animate-fade-up">
          <div className="text-[2.6rem] leading-none font-extrabold tracking-tight bg-gradient-to-b from-white to-white/55 bg-clip-text text-transparent">
            Jobora
          </div>
          <div className="text-sm text-muted mt-2">Auto Job Applier</div>
        </div>

        <div className="glass rounded-card p-8 animate-fade-up delay-1">
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="text-sm text-muted mt-1 mb-6">{subtitle}</p>}
          {children}
        </div>

        {footer && (
          <div className="mt-6 text-center text-sm text-muted animate-fade-up delay-2">{footer}</div>
        )}
      </div>
    </div>
  );
}
