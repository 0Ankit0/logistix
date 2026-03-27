# FastAPI Template

A reusable full-stack template with FastAPI, Next.js, and Flutter, built around feature flags, pluggable providers, and reusable project documentation.

The project is designed so that most customization starts with configuration and capability discovery, not code forks. The backend is the source of truth for enabled modules, active providers, public runtime settings, and operational behavior.

## What It Includes

- Config-driven modules for auth, multi-tenancy, notifications, websockets, finance, analytics, and social auth.
- Communications provider switching for email, push, and SMS.
- Runtime discovery APIs for clients and operators.
- Database-backed runtime settings overrides for safe operational config.
- Centralized operational config for cookies, hosts, rate limits, logging, observability, storage, Celery, and websocket behavior.
- Web and mobile clients that adapt to enabled modules and configured providers.
- A consolidated `DOCS.md` reference that combines the template docs and logistics tracking system design docs.

## Quick Start

1. Review [DOCS.md](/Users/ankit/Projects/Python/fastapi/logistix/DOCS.md).
2. Run `make setup`.
3. Read the onboarding and implementation sections in [DOCS.md](/Users/ankit/Projects/Python/fastapi/logistix/DOCS.md), then review [TEMPLATE_RELEASE_CHECKLIST.md](/Users/ankit/Projects/Python/fastapi/logistix/TEMPLATE_RELEASE_CHECKLIST.md).
4. Start local dependencies with `make infra-up`.
5. Run migrations with `make backend-migrate`.
6. Start the apps with `make backend-dev`, `make frontend-dev`, and `make mobile-dev`.
7. Verify the starter with `make health-check` and `make ci`.

## Validation

- Backend lint and tests: `make backend-lint` and `make backend-test`
- Frontend lint, typecheck, tests, and build: `make frontend-lint` and `make frontend-test`
- Mobile analyze and tests: `make mobile-lint` and `make mobile-test`
- Docs validation: `make docs`
- Full local quality bar: `make ci`
