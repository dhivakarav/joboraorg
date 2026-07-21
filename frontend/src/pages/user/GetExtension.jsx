const RELEASE_BASE = "https://github.com/dhivakarav/joboraorg/releases/download/v1.0";

const EXTENSIONS = [
  {
    name: "Jobora — LinkedIn Copilot",
    tagline: "Honest match scoring + bulk auto-apply on LinkedIn",
    zip: "jobora-linkedin-extension.zip",
    features: [
      "Ruthlessly honest resume-match score on every job",
      "Bulk auto-apply through LinkedIn Easy Apply",
      "AI answers screening questions from your resume",
      "Ban-safety meter — stops at a safe daily limit",
    ],
  },
  {
    name: "Jobora — Internshala Copilot",
    tagline: "Auto-apply to eligible Internshala internships",
    zip: "jobora-internshala-extension.zip",
    features: [
      "Scores every internship against your resume",
      "Walks Apply → Proceed → cover letter → Submit for you",
      "Skips roles you're not eligible for",
      "Loud alert if a form needs your input",
    ],
  },
];

function ExtCard({ ext }) {
  return (
    <div className="flex flex-col rounded-2xl border border-edge bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand text-2xl font-extrabold text-white">
          J
        </div>
        <div>
          <h3 className="text-base font-bold text-ink">{ext.name}</h3>
          <p className="text-sm text-ink-soft">{ext.tagline}</p>
        </div>
      </div>

      <ul className="mt-5 space-y-2">
        {ext.features.map((f) => (
          <li key={f} className="flex gap-2 text-sm text-ink">
            <span className="text-brand">✓</span>
            <span>{f}</span>
          </li>
        ))}
      </ul>

      <a
        href={`${RELEASE_BASE}/${ext.zip}`}
        className="mt-6 inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white transition hover:opacity-90"
      >
        ⬇ Download for Chrome
      </a>
    </div>
  );
}

export default function GetExtension() {
  return (
    <div>
      <h1 className="text-2xl font-extrabold tracking-tight text-ink">Browser extensions</h1>
      <p className="mt-2 max-w-2xl text-ink-soft">
        Install the copilot for your job board. It scores each role against your resume and
        auto-applies to the good ones — honestly, and only where you're eligible. You're already
        signed in — just sign in inside the extension with the same account.
      </p>

      <div className="mt-8 grid gap-6 md:grid-cols-2">
        {EXTENSIONS.map((ext) => (
          <ExtCard key={ext.zip} ext={ext} />
        ))}
      </div>

      <div className="mt-8 max-w-2xl rounded-2xl border border-edge bg-white p-6">
        <h2 className="text-base font-bold text-ink">Install in 4 steps</h2>
        <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-ink">
          <li>Download the <b>.zip</b> above and <b>unzip</b> it to a folder you'll keep.</li>
          <li>Open <code className="rounded bg-brand-soft px-1 text-brand">chrome://extensions</code> and turn on <b>Developer mode</b> (top-right).</li>
          <li>Click <b>Load unpacked</b> and select the unzipped folder.</li>
          <li>Open the Jobora side panel on the job site, sign in, turn on Auto-apply, and press <b>Start</b>.</li>
        </ol>
        <p className="mt-3 text-xs text-ink-soft">
          It applies to matching, eligible roles and pauses — with a loud alert — only when a
          question genuinely needs you. Chrome may show an "unpacked extension" note; that's normal.
        </p>
      </div>
    </div>
  );
}
