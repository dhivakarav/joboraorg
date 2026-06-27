interface SkillsPanelProps {
  missingSkills: string[];
  resumeSkills: string[];
  jobSkills: string[];
}

export default function SkillsPanel({ missingSkills, resumeSkills, jobSkills }: SkillsPanelProps) {
  if (missingSkills.length === 0 && jobSkills.length === 0) return null;

  return (
    <div className="jbr-card p-4 space-y-3">
      <h3 className="text-xs font-semibold text-ink-soft uppercase tracking-wide">Skills</h3>

      {missingSkills.length > 0 && (
        <div>
          <div className="text-xs font-medium text-err mb-1.5">
            Missing from your resume ({missingSkills.length})
          </div>
          <div className="flex flex-wrap gap-1.5">
            {missingSkills.map(s => (
              <span key={s}
                className="jbr-badge border-err/30 bg-err/5 text-err">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {jobSkills.length > 0 && (
        <div>
          <div className="text-xs font-medium text-ink-soft mb-1.5">
            Job requires
          </div>
          <div className="flex flex-wrap gap-1.5">
            {jobSkills.map(s => {
              const have = resumeSkills.some(r => r.toLowerCase() === s.toLowerCase());
              return (
                <span key={s}
                  className={`jbr-badge ${have
                    ? 'border-ok/30 bg-ok/5 text-ok'
                    : 'border-edge text-ink-soft'}`}>
                  {have ? '✓ ' : ''}{s}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
