# Environment Variables — Jobora Production

Set on the **API** service (and the **worker**, where noted). The app **refuses to
start** in production without `JWT_SECRET` and `CREDENTIAL_KEY`.

## Generate secrets
```bash
# JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(48))"
# CREDENTIAL_KEY  (Fernet — store in a vault; losing it = unrecoverable PII)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Required (production won't boot / function without these)
| Var | Example / source | Worker too? |
|---|---|---|
| `JOBORA_ENV` | `production` | ✅ |
| `JWT_SECRET` | generated (48-byte urlsafe) | ✅ |
| `CREDENTIAL_KEY` | generated Fernet key (stable, vaulted) | ✅ |
| `DATABASE_URL` | Railway Postgres reference | ✅ |
| `REDIS_URL` | Railway Redis reference | ✅ |
| `S3_BUCKET` | `jobora-prod` | ✅ |
| `AWS_ACCESS_KEY_ID` | bucket key | ✅ |
| `AWS_SECRET_ACCESS_KEY` | bucket secret | ✅ |
| `S3_REGION` | `us-east-1` (AWS) / `auto` (R2) | ✅ |
| `ADMIN_EMAIL` | `you@domain.com` (seeds admin) | — |
| `ADMIN_PASSWORD` | strong; change on first login | — |
| `CORS_ORIGINS` | `https://app.jobora.com` | — |
| `APP_BASE_URL` | `https://app.jobora.com` (email links) | — |

## Storage — R2 specifics
| Var | AWS S3 | Cloudflare R2 |
|---|---|---|
| `S3_ENDPOINT_URL` | *(empty)* | `https://<accountid>.r2.cloudflarestorage.com` |
| `S3_REGION` | real region | `auto` |
| `S3_PRESIGN_TTL` | `900` | `900` |

## Email (required to invite real users — else mail goes to console)
| Var | Example |
|---|---|
| `SMTP_HOST` | `smtp.resend.com` / `email-smtp.<region>.amazonaws.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | provider username |
| `SMTP_PASSWORD` | provider password / API key |
| `SMTP_FROM` | `Jobora <no-reply@jobora.app>` |
| `SMTP_TLS` | `1` |
| `EXPOSE_RESET_TOKEN` | `0` in prod (don't leak reset tokens in API responses) |

## Monitoring (recommended for beta — code is gated/no-op without these)
| Var | Example |
|---|---|
| `SENTRY_DSN` | `https://...ingest.sentry.io/...` |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` |
| `POSTHOG_API_KEY` | `phc_...` |
| `POSTHOG_HOST` | `https://us.i.posthog.com` |

## Closed beta
| Var | Example |
|---|---|
| `BETA_INVITE_REQUIRED` | `1` (registration needs an invite code) |

## Tuning / optional (sane defaults)
| Var | Default | Notes |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `1` | Redis-backed |
| `RL_LOGIN_PER_MIN` / `RL_REGISTER_PER_HOUR` | `10` / `10` | per IP |
| `RL_APPLY_PER_DAY` / `RL_APPLY_BURST_PER_MIN` | `30` / `3` | per user |
| `RL_SEARCH_PER_MIN` | `30` | per user |
| `INPROCESS_WORKER` | `1` | set `0` when running a separate RQ worker |
| `SUBMISSION_CONCURRENCY` | `2` | browser submissions |
| `JOB_CACHE_TTL` | `900` | provider cache seconds |
| `APP_VERSION` | `beta` | shown in logs/analytics |
| `JOBORA_LIVE` | `0` | keep `0` unless live Greenhouse submit is enabled |
| `ANTHROPIC_API_KEY` | *(empty)* | optional; heuristics used when unset |

## Provider keys (optional — discovery works without them)
`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_API_KEY`, `GREENHOUSE_BOARDS`,
`LEVER_COMPANIES`, `ASHBY_BOARDS`. (No new boards added; these only tune existing
providers.)
