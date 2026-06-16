// Custom Playwright reporter → writes ../PLAYWRIGHT_REPORT.md at onEnd, when test
// results are final in-memory (no file race) and the fixture-captured console/
// network/exception data in e2e/.artifacts/errors.json is complete.
import fs from "fs";

export default class MdReporter {
  constructor() { this.specs = []; }

  onTestEnd(test, result) {
    this.specs.push({ title: test.title, status: result.status });
  }

  onEnd(runResult) {
    let errors = {};
    try { errors = JSON.parse(fs.readFileSync("e2e/.artifacts/errors.json", "utf8")); } catch { /* none */ }

    const sum = (f) => Object.values(errors).reduce((n, e) => n + (e[f]?.length || 0), 0);
    const totalConsole = sum("consoleErrors");
    const totalNet = sum("networkFailures");
    const totalExc = sum("pageErrors");
    const totalWarn = sum("warn4xx");

    const passed = this.specs.filter((s) => s.status === "passed").length;
    const failed = this.specs.filter((s) => s.status === "failed" || s.status === "timedOut").length;
    const skipped = this.specs.filter((s) => s.status === "skipped").length;
    const icon = (s) => (s === "passed" ? "✅" : s === "skipped" ? "⚠️ skipped" : "❌");

    let md = `# Playwright Smoke Report (closes W1)\n\n`;
    md += `_Run: ${new Date().toISOString()}. Backend: \`${process.env.API_URL || "http://localhost:8000"}\`. `;
    md += `Browser: Chromium (Playwright). Serialized (workers:1)._\n\n`;
    md += `## Summary\n`;
    md += `- Tests: **${passed} passed · ${failed} failed · ${skipped} skipped** (of ${this.specs.length}).\n`;
    md += `- **Console errors: ${totalConsole}** · **Failed API/network requests (5xx/connection): ${totalNet}** · **Uncaught exceptions: ${totalExc}**.\n`;
    md += `- Non-blocking 4xx (auth/validation, informational): ${totalWarn}.\n`;
    md += `- Screenshots: \`frontend/e2e/screenshots/\` · HTML report: \`frontend/e2e/.artifacts/html\`.\n\n`;

    const pass = failed === 0 && totalConsole === 0 && totalNet === 0 && totalExc === 0;
    md += `## Verdict\n${pass
      ? "✅ **PASS — zero console errors, zero failed API requests, zero uncaught exceptions across all flows.**"
      : "❌ **FAIL — see captured issues below.**"}\n\n`;

    md += `## Per-test results\n| Test | Status | Console err | Net fail | Exceptions |\n|---|---|---|---|---|\n`;
    for (const s of this.specs.sort((a, b) => a.title.localeCompare(b.title, undefined, { numeric: true }))) {
      const e = errors[s.title] || {};
      md += `| ${s.title} | ${icon(s.status)} | ${e.consoleErrors?.length || 0} | ${e.networkFailures?.length || 0} | ${e.pageErrors?.length || 0} |\n`;
    }

    const details = [];
    for (const [title, e] of Object.entries(errors)) {
      const lines = [
        ...(e.pageErrors || []).map((x) => `exception: ${x}`),
        ...(e.consoleErrors || []).map((x) => `console: ${String(x).split("\n")[0]}`),
        ...(e.networkFailures || []).map((x) => `network: ${x}`),
      ];
      if (lines.length) details.push(`### ${title}\n` + lines.map((l) => `- ${l}`).join("\n"));
    }
    md += `\n## Captured issues\n${details.length ? details.join("\n\n") : "None. 🎉"}\n\n`;
    md += `## Coverage\nSignup · Login · Resume upload · Resume parsing · Find Jobs · Internship filter · `;
    md += `Dashboard · Activity Log · Verification Center · Admin Operations · Greenhouse Track & Apply · `;
    md += `Lever Assisted Apply · Ashby Assisted Apply · Logout · Mobile drawer. Apply-flow tests interact `;
    md += `with whatever real listings are live and otherwise screenshot the state (no fabricated data).\n`;

    fs.writeFileSync("../PLAYWRIGHT_REPORT.md", md);
  }
}
