# Seeded Full QA Runbook

## Purpose
This runbook provides a deterministic, repeatable QA process for frontend and backend workflows using seeded data.

## Environment Used
- Backend: FastAPI on `http://localhost:8000`
- Frontend: Vite preview/static serving on `http://localhost:3000`
- Mobile: Flutter web running on `http://localhost:4000`
- Database: local SQLite (after migrations)

## One-Time Setup
1. Apply migrations:
   - `cd backend && uv run task migrate`
2. Seed deterministic QA data:
   - `cd backend && uv run python -m src.db.seed_qa_data`
3. Start backend:
   - `uv --directory /media/ankit/Programming/Projects/python/fastapi/logistix/backend run uvicorn src.main:app --host 0.0.0.0 --port 8000`
4. Build frontend:
   - `npm --prefix /media/ankit/Programming/Projects/python/fastapi/logistix/frontend run build`
5. Start frontend preview:
   - `cd frontend && npx vite preview --host 0.0.0.0 --port 3000`
6. Start mobile web:
  - `cd mobile && flutter run -d web-server --web-hostname 0.0.0.0 --web-port 4000`

## Fresh Rerun Checklist
Use this order when you need to repeat QA from a clean baseline:
1. Apply migrations.
2. Seed QA data.
3. Start backend.
4. Start frontend preview.
5. Start mobile web.
6. Confirm `GET /api/v1/system/capabilities/` returns `200`.
7. Confirm frontend and mobile home/login pages load in the browser.

## Seeded Accounts and Tokens
- Admin user:
  - username: `qa_admin`
  - password: `Admin1234`
- Operator user:
  - username: `qa_operator`
  - password: `User12345`
- Dispatcher user:
  - username: `qa_dispatcher`
  - password: `User12345`
- Public tracking tokens:
  - `qa-track-001`
  - `qa-track-002`
  - `qa-track-003`

## Page-by-Page QA Checklist

### Auth/Public pages
- `/login`: PASS (renders login form)
- `/signup`: PASS
- `/forgot-password`: PASS
- `/reset-password`: PASS
- `/otp-verify`: PASS (page renders)
- `/verify-email`: PASS
- `/accept-invitation`: PASS
- `/auth-callback`: PASS (redirects to login with `oauth_failed` when no provider callback payload)
- `/payment-callback`: PASS (shows missing verification data guidance without callback params)
- `/track/qa-track-001`: PASS
- `/track/qa-track-002`: PASS
- `/track/qa-track-003`: PASS

### User dashboard pages (authenticated as `qa_admin`)
- `/dashboard`: PASS
- `/profile`: PASS
- `/tenants`: PASS
- `/shipments`: PASS
- `/dispatch`: PASS
- `/exceptions`: PASS
- `/tracking`: PASS
- `/hubs-routes`: PASS
- `/fleet`: PASS
- `/finances`: PASS
- `/notifications`: PASS
- `/tokens`: PASS
- `/settings`: PASS
- `/rbac`: PASS

### Admin pages
- `/admin/dashboard`: PASS
- `/admin/users`: PASS
- `/admin/security-review`: PASS
- `/admin/rbac`: PASS

### Mobile web pages
Run these after the app loads at `http://localhost:4000` and you sign in with `qa_admin` / `Admin1234`.
- `/login`: PASS
- `/register`: PASS
- `/forgot-password`: PASS
- `/reset-password`: PASS
- `/otp-verify`: PASS
- `/home`: PASS
- `/home/notifications`: PASS
- `/home/settings`: PASS
- `/home/profile`: PASS
- `/home/payments`: PASS
- `/home/driver-assignments`: PASS
- Protected routes redirect to `/login` when not authenticated: PASS

## Workflow QA Executed

### 1) Shipment creation workflow
- Navigate to `/shipments`
- Fill:
  - customer name: `QA Walkthrough Receiver`
  - customer contact: `9800000000`
  - origin: `Kathmandu QA Origin`
  - destination: `Pokhara QA Destination`
- Click `Create shipment`
- Expected:
  - table row count increases by 1
  - new row appears with generated reference (`SHP-...`) and status `created`
- Result: PASS

### 2) Dispatch assignment workflow
- Navigate to `/dispatch`
- In `Create Assignment`, select shipment, driver, vehicle
- Click `Assign`
- Expected:
  - assignment list increases by 1
  - new assignment visible with `assigned` state
- Result: PASS

### 3) Exception resolution workflow
- Navigate to `/exceptions`
- Click `Resolve` for open seeded exception
- Expected:
  - item updates from `Open` to resolved/cleared state
  - queue reflects no open exceptions
- Result: PASS

### 4) Notification state workflow
- Navigate to `/notifications`
- Click `Mark all read`
- Expected:
  - unread badge cleared
  - header state changes to all-clear message
- Result: PASS

### 5) Tracking token workflow
- Navigate to `/tracking`
- Enter `qa-track-001` and click `Open`
- Expected:
  - navigation to `/track/qa-track-001`
  - timeline of seeded checkpoint transitions rendered
- Result: PASS

### 6) Mobile login and navigation workflow
- Open `http://localhost:4000/#/login`
- Sign in with `qa_admin` / `Admin1234`
- Expected:
  - app navigates to `/home`
  - tab navigation shows Home, Notifications, Settings, Profile
  - protected routes stay accessible after login
- Result: PASS

### 7) Mobile quick actions workflow
- From Home, open:
  - Payments
  - Active Sessions
  - Driver Assignments
- Expected:
  - each screen loads without runtime error
  - the Back button returns to the home shell
- Result: PASS

### 8) Mobile logout / guard workflow
- From Profile, tap `Logout`
- Expected:
  - session is cleared
  - app returns to the login screen
  - direct access to `/home` redirects back to `/login`
- Result: PASS

## Automated Route Sanity Verification
A route sweep confirmed expected landing/heading on all mapped user/admin/public routes after login and seeding.

## Known Non-Blocking Warnings
- Browser console repeatedly logs `503` for push-notification capability endpoints when push providers are not configured.
- This behavior is currently expected from backend notification push config checks:
  - `backend/src/apps/notification/api/v1/push_devices.py` (explicit `HTTP 503` responses)
- Core shipment, dispatch, exceptions, tracking, admin pages, and notification list workflows remain functional.
- During mobile web QA, Flutter semantics may require enabling accessibility before browser automation can target text fields and buttons reliably.

## Troubleshooting
- If frontend routes suddenly redirect to `/login`, verify the backend is still running and the session token is present.
- If mobile web fails to start, rerun `flutter pub get` in `mobile/` and launch with the `web-server` device from the project root.
- If payment screens show type parsing errors, re-run the mobile app after the latest QA fixes and confirm the backend payment payload matches the model definitions.

## Notes
- A backend serialization issue in notification preferences was fixed to unblock dashboard/notification rendering during this QA run.
- If QA is rerun, always reseed before execution for deterministic expectations.
