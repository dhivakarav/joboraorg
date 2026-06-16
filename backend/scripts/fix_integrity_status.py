"""One-time integrity data fix for the dev SQLite DB (jobora.db).

Mirrors the Alembic migration `a1b2c3d4e5f6` for the local zero-setup DB:
  1. ensure columns application_id + evidence_available exist
  2. backfill application_id from external_application_id
  3. set evidence_available where a confirmation artifact is actually stored
  4. downgrade any "Verified Submitted" lacking complete evidence -> "Submitted"
  5. relabel legacy Applied/Submitted rows WITHOUT verified evidence ->
     status='Tracked', submission_status='Draft', evidence_available=0

Prints a before/after report. Idempotent.
"""
import sqlite3

DB = "jobora.db"


def colset(cur, table):
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})")}


def snapshot(cur, label):
    print(f"\n--- {label} ---")
    print("  status:")
    for r in cur.execute("SELECT status, COUNT(*) FROM applications GROUP BY status ORDER BY 2 DESC"):
        print(f"    {r[0] or '(null)':22} : {r[1]}")
    print("  submission_status:")
    for r in cur.execute("SELECT submission_status, COUNT(*) FROM applications GROUP BY submission_status ORDER BY 2 DESC"):
        print(f"    {r[0] or '(null)':22} : {r[1]}")
    v = cur.execute("""SELECT COUNT(*) FROM applications
        WHERE submission_status='Verified Submitted'
          AND COALESCE(application_id,'')<>'' AND COALESCE(confirmation_url,'')<>''
          AND evidence_available=1""").fetchone()[0]
    print(f"  truly Verified Submitted (id+url+evidence): {v}")


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cols = colset(cur, "applications")
    if "application_id" not in cols:
        cur.execute("ALTER TABLE applications ADD COLUMN application_id VARCHAR DEFAULT ''")
        print("added column application_id")
    if "evidence_available" not in cols:
        cur.execute("ALTER TABLE applications ADD COLUMN evidence_available BOOLEAN DEFAULT 0")
        print("added column evidence_available")

    snapshot(cur, "BEFORE")

    cur.execute("""UPDATE applications
        SET application_id = COALESCE(NULLIF(application_id,''), external_application_id)
        WHERE COALESCE(application_id,'')=''""")

    cur.execute("""UPDATE applications SET evidence_available = 1
        WHERE submission_evidence LIKE '%"screenshot"%'
           OR submission_evidence LIKE '%"screenshot_key"%'
           OR submission_evidence LIKE '%"html"%'""")

    down = cur.execute("""UPDATE applications SET submission_status='Submitted'
        WHERE submission_status='Verified Submitted'
          AND NOT (COALESCE(application_id,'')<>'' AND COALESCE(confirmation_url,'')<>''
                   AND evidence_available=1)""").rowcount

    relabel = cur.execute("""UPDATE applications
        SET status='Tracked', submission_status='Draft', evidence_available=0
        WHERE status IN ('Applied','Submitted')
          AND NOT (submission_status='Verified Submitted'
                   AND COALESCE(application_id,'')<>'' AND COALESCE(confirmation_url,'')<>''
                   AND evidence_available=1)""").rowcount

    con.commit()
    print(f"\ndowngraded (Verified->Submitted, no evidence): {down}")
    print(f"relabelled (Applied/Submitted -> Tracked/Draft/unverified): {relabel}")
    snapshot(cur, "AFTER")
    con.close()


if __name__ == "__main__":
    main()
