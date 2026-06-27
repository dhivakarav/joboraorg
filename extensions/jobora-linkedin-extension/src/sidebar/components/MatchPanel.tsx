import type { JobScore } from '../../types/job';

interface MatchPanelProps {
  score: JobScore;
}

const TIER_COLORS: Record<string, string> = {
  'Excellent Match': 'text-ok',
  'Good Match':      'text-brand',
  'Possible Match':  'text-warn',
  'Not Recommended': 'text-err',
};

function ScoreRing({ value }: { value: number }) {
  const radius = 28;
  const circ = 2 * Math.PI * radius;
  const offset = circ - (value / 100) * circ;

  const color =
    value >= 75 ? '#22C55E' :
    value >= 50 ? '#2563EB' :
    value >= 30 ? '#F59E0B' : '#EF4444';

  return (
    <svg width="72" height="72" viewBox="0 0 72 72" className="shrink-0">
      <circle cx="36" cy="36" r={radius} fill="none" stroke="#E2E8F0" strokeWidth="6" />
      <circle
        cx="36" cy="36" r={radius}
        fill="none"
        stroke={color}
        strokeWidth="6"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 36 36)"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
      <text x="36" y="36" textAnchor="middle" dominantBaseline="central"
            className="fill-ink" style={{ fontSize: 15, fontWeight: 700 }}>
        {value}%
      </text>
    </svg>
  );
}

export default function MatchPanel({ score }: MatchPanelProps) {
  const tierColor = TIER_COLORS[score.eligibility_tier] ?? 'text-ink-soft';

  return (
    <div className="jbr-card p-4 flex items-start gap-4">
      <ScoreRing value={score.match_score} />

      <div className="min-w-0 flex-1">
        <div className="text-xs font-semibold text-ink-soft uppercase tracking-wide mb-0.5">
          Resume Match
        </div>
        <div className={`text-sm font-semibold ${tierColor}`}>
          {score.eligibility_tier}
        </div>

        {score.match_reasons.length > 0 && (
          <ul className="mt-2 space-y-0.5">
            {score.match_reasons.map((r, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-ink-soft">
                <span className="text-ok mt-0.5 shrink-0">✓</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        )}

        {!score.eligible && score.eligibility_reason && (
          <p className="mt-2 text-xs text-err/80 leading-relaxed">
            ⚠ {score.eligibility_reason}
          </p>
        )}
      </div>
    </div>
  );
}
