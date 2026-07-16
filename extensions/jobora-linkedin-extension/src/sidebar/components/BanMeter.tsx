import { useEffect, useState } from 'react';
import { getBanRisk, type BanRisk, type RiskLevel } from '../../autofill/banmeter';

/**
 * Live "applications today" meter with a ban-risk level. The user explicitly
 * wanted the account-ban risk visible in the extension. Explicit class strings
 * (not template interpolation) so Tailwind actually generates them.
 */
const STYLES: Record<RiskLevel, { text: string; bar: string; border: string; icon: string }> = {
  safe:    { text: 'text-ok',   bar: 'bg-ok',   border: 'border-ok/30',   icon: '✓ ' },
  caution: { text: 'text-warn', bar: 'bg-warn', border: 'border-warn/30', icon: '⚠ ' },
  high:    { text: 'text-err',  bar: 'bg-err',  border: 'border-err/30',  icon: '⛔ ' },
};

export default function BanMeter() {
  const [risk, setRisk] = useState<BanRisk | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () => getBanRisk().then(r => { if (alive) setRisk(r); });
    tick();
    const id = setInterval(tick, 4000);
    const onChange = (c: Record<string, chrome.storage.StorageChange>) => {
      if (c.jobora_apply_log) tick();
    };
    chrome.storage.onChanged.addListener(onChange);
    return () => {
      alive = false;
      clearInterval(id);
      chrome.storage.onChanged.removeListener(onChange);
    };
  }, []);

  if (!risk) return null;
  const s = STYLES[risk.level];
  const pct = Math.min(100, (risk.count / risk.limit) * 100);

  return (
    <div className={`jbr-card px-3 py-2 space-y-1.5 ${s.border}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-ink-soft uppercase tracking-wide">
          Applications today
        </span>
        <span className={`text-xs font-bold ${s.text}`}>
          {risk.count}/{risk.limit}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-edge overflow-hidden">
        <div className={`h-full ${s.bar} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <p className={`text-[11px] leading-snug ${s.text}`}>
        {s.icon}{risk.message}
      </p>
    </div>
  );
}
