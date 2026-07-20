import { Link } from "react-router-dom";

/**
 * Public install page for the Jobora browser extensions.
 *
 * ▶ AFTER you publish each extension to the Chrome Web Store, paste its store
 *   URL below. Until then the button shows "Coming soon" and offers the raw
 *   .zip (Developer-mode load) as a fallback.
 */
const STORE_URLS = {
  linkedin: "",     // e.g. "https://chromewebstore.google.com/detail/<id>"
  internshala: "",  // e.g. "https://chromewebstore.google.com/detail/<id>"
};

const EXTENSIONS = [
  {
    key: "linkedin",
    name: "Jobora — LinkedIn Copilot",
    tagline: "Honest match scoring + bulk auto-apply on LinkedIn",
    zip: "/downloads/jobora-linkedin-extension.zip",
    features: [
      "Ruthlessly honest resume-match score on every job",
      "Bulk auto-apply that walks LinkedIn Easy Apply for you",
      "AI answers screening questions from your resume",
      "Ban-safety meter — stops at a safe daily limit",
    ],
  },
  {
    key: "internshala",
    name: "Jobora — Internshala Copilot",
    tagline: "Auto-apply to eligible Internshala internships",
    zip: "/downloads/jobora-internshala-extension.zip",
    features: [
      "Scores every internship against your resume",
      "Walks Apply → Proceed → cover letter → Submit automatically",
      "Skips jobs you're not eligible for",
      "Loud alert if a form needs your input",
    ],
  },
];

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <svg width="30" height="30" viewBox="0 0 34 34" fill="none" aria-hidden>
        <circle cx="24" cy="8" r="3" fill="#2563EB" />
        <path d="M24 8 V21 A9 9 0 0 1 6 21" stroke="#0F172A" strokeWidth="3" strokeLinecap="round" fill="none" />
      </svg>
      <span className="text-xl font-extrabold tracking-tight text-slate-900">Jobora</span>
    </div>
  );
}

function ExtCard({ ext }) {
  const store = STORE_URLS[ext.key];
  return (
    <div className="flex flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#2563EB] text-2xl font-extrabold text-white">
          J
        </div>
        <div>
          <h3 className="text-lg font-bold text-slate-900">{ext.name}</h3>
          <p className="text-sm text-slate-500">{ext.tagline}</p>
        </div>
      </div>

      <ul className="mt-5 space-y-2">
        {ext.features.map((f) => (
          <li key={f} className="flex gap-2 text-sm text-slate-700">
            <span className="text-[#2563EB]">✓</span>
            <span>{f}</span>
          </li>
        ))}
      </ul>

      <div className="mt-6 flex flex-col gap-2">
        {store ? (
          <a
            href={store}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#2563EB] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700"
          >
            Add to Chrome
          </a>
        ) : (
          <span className="inline-flex items-center justify-center rounded-xl bg-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-500">
            Coming soon to the Chrome Web Store
          </span>
        )}
        <a href={ext.zip} className="text-center text-xs text-slate-500 underline hover:text-slate-700">
          or download .zip (advanced: Developer mode → Load unpacked)
        </a>
      </div>
    </div>
  );
}

export default function Extensions() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
        <Link to="/"><Logo /></Link>
        <Link to="/login" className="text-sm font-semibold text-[#2563EB] hover:underline">
          Sign in
        </Link>
      </header>

      <main className="mx-auto max-w-5xl px-6 pb-20">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
            Jobora browser extensions
          </h1>
          <p className="mt-3 text-slate-600">
            Install the copilot for your job board. It scores each role against your
            resume and auto-applies to the good ones — honestly, and only where you're eligible.
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Requires a free{" "}
            <Link to="/register" className="text-[#2563EB] underline">Jobora account</Link>{" "}
            — sign in inside the extension after installing.
          </p>
        </div>

        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {EXTENSIONS.map((ext) => (
            <ExtCard key={ext.key} ext={ext} />
          ))}
        </div>

        <div className="mx-auto mt-12 max-w-2xl rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="text-base font-bold text-slate-900">How it works</h2>
          <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-slate-700">
            <li>Install the extension for your job board (button above).</li>
            <li>Open the Jobora side panel on that site and sign in with your Jobora account.</li>
            <li>Turn on Auto-apply, open a search list, and press Start.</li>
            <li>It applies to matching, eligible roles and pauses (with a loud alert) only when a question genuinely needs you.</li>
          </ol>
          <p className="mt-4 text-xs text-slate-500">
            Your data is handled per our{" "}
            <a href="/privacy" className="underline">Privacy Policy</a>. You review your
            profile and resume; Jobora never fabricates experience on your behalf.
          </p>
        </div>
      </main>
    </div>
  );
}
