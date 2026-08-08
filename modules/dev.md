RailRo — Phase 1 Development Plan
Horizon: 7 calendar days (1 sprint)
Team: 6 engineers — 4 backend + 2 frontend
Architecture: Modular Monolith — FastAPI backend, Next.js 14 frontend
Goal: Working B2B booking flow on REJN→JOS and REJN→KEBG corridors, flat pricing, manual ops, email notifications

Team Roles & Domain Ownership
Handle	Role	Owns exclusively
BE1	Backend — Auth + DevOps	modules/auth/, modules/users/, core/ (all shared infra), Docker, CI/CD, DB migrations, deployment
BE2	Backend — Payments + Notifications	modules/payments/, modules/notifications/, tasks/reminder_tasks.py, Razorpay, SendGrid, Celery reminder tasks
BE3	Backend — Bookings + E-way Bill + Vehicles + QR + Invoice + Ops	modules/bookings/ (ALL), modules/eway_bill/, modules/vehicles/, modules/invoicing/, modules/operations/ (ALL)
BE4	Backend — Admin + Inventory + Pricing	modules/inventory/, modules/pricing/, modules/admin/, slot reservations (Redis), fare calculator, rake management, tasks/cleanup_tasks.py
FE1	Frontend — Customer Flow	Registration, login, booking wizard (all 5 steps), bookings list/detail, vehicles library, dashboard, invoices
FE2	Frontend — Ops + Admin UI	/ops/gate QR scanner, /ops/loading, all /admin/* pages, shared components, QA smoke tests
Module Ownership Rule
Each engineer writes code only inside their own module directories. Cross-module calls go through the public *_service.py interface only — never direct model or repository imports from another module.

# BE2 (payments) calling BE3 (bookings) — CORRECT
from modules.bookings.services.bookings_service import transition_to_confirmed

# BE2 reaching into BE3 internals — WRONG
from modules.bookings.models import Booking        # forbidden
from modules.bookings.repository import repo       # forbidden
Coordination Rules
Daily sync at 9:30 AM, 15 min max — each lane: shipped yesterday / blocked on today.
All PRs target dev. Every PR needs 1 review. BE1 reviews anything touching core/. Peer review within lane for isolated module work.
FE1 and FE2 use msw (Mock Service Worker) mock handlers from Day 1 — frontend is never blocked on backend being live.
BE1 must merge core/security.py by EOD Day 1 — BE2 needs JWT/HMAC utilities on Day 2.
BE1 must merge initial migration by EOD Day 1 — BE3 and BE4 need table definitions to write real models.
BE2 calls BE3's bookings_service public interface for payment → booking state transitions (not bookings internals).
BE4's admin departure/arrival endpoints call BE3's bookings_service.bulk_transition_*() public methods.
Pre-Sprint Checklist (must complete before Day 1)
Item	Owner	Status
Razorpay test account created + keys distributed to BE2	BE1	[ ]
SendGrid account + domain authentication started (1–2 day lead time)	BE1	[ ]
AWS S3 bucket provisioned (or Cloudflare R2) + credentials to BE1	BE1	[ ]
.env values distributed to all 6 engineers	BE1	[ ]
GitHub repo: master (prod) + staging + dev branches live	BE1	[x]
Docker Desktop confirmed on all 6 machines	All	[ ]
msw added as frontend dev dependency	FE1	[ ]
Design handoff link (Figma or equivalent) shared with FE1, FE2	Product	[ ]
Day 1 — Monday: Infrastructure & Foundation
Theme: Zero blocked days after today. All 6 engineers have a running local stack.

BE1 — Auth + DevOps
[ ] Confirm repo scaffold matches backend/, frontend/, docs/ structure
[ ] docker-compose.yml — PostgreSQL 16 + Redis 7 + API + Worker + Beat services verified
[ ] GitHub Actions pipeline: ruff check . → mypy --strict core/ modules/ → pytest --cov --cov-fail-under=80 → docker build
[ ] alembic init migrations; configure migrations/env.py for async SQLAlchemy engine
[ ] Write initial migration 0001_initial_schema.py — all 16 tables from PRD §14 with indexes and CHECK constraints
[ ] Seed script scripts/seed.py — 3 terminals (REJN, JOS, KEBG), 2 routes (REJN-JOS, REJN-KEBG), 1 admin user
[ ] Verify: alembic upgrade head runs clean on fresh Docker DB; uvicorn main:app --reload starts
[ ] Write core/config.py, core/database.py, core/redis.py, core/s3.py, core/events.py, core/exceptions.py, core/dependencies.py stubs — ready for Day 2 service wiring
[ ] Write core/security.py — JWT, bcrypt, OTP hash, QR HMAC, AES-256-GCM encrypt/decrypt [needed by BE2 Day 2]
BE2 — Payments + Notifications
[ ] modules/payments/models.py — Payment model
[ ] modules/notifications/models.py — Notification log model
[ ] Read PRD §S6 (payment flow) and §10 (all notification triggers) — document all webhook scenarios in comment block at top of payments_service.py stub; list all 16 notification triggers in notifications_service.py stub
BE3 — Bookings + E-way Bill + Vehicles + QR + Invoice + Ops
[ ] modules/bookings/models.py — Booking, SlotReservation, Feedback SQLAlchemy models
[ ] modules/eway_bill/models.py — no standalone table; eway bill data lives in bookings.eway_bill_data JSONB; confirm mock adapter fixture coverage (331*, 332*, 333*, 334*, 999*)
[ ] modules/vehicles/models.py — Vehicle model
[ ] modules/invoicing/models.py — Invoice model
[ ] modules/operations/models.py — GateEntry, LoadingPlan, LoadingPlanItem models
[ ] Read PRD §S3 (eligibility), §S5 (booking creation), §S7 (QR), §S9 (loading plan), §S12 (invoice) — write domain rule comments in respective service stubs
BE4 — Admin + Inventory + Pricing
[ ] modules/inventory/models.py — Rake, Route, Terminal models
[ ] modules/pricing/models.py — PricingRule model
[ ] Read PRD §S4 (slot availability), §9 (pricing formula) — write spec comments in service stubs
[ ] Verify seed data: terminals and routes exist after alembic upgrade head
FE1 — Customer Flow Scaffold
[ ] cd frontend && npx create-next-app@latest . --typescript --tailwind --app --src-dir
[ ] Install: shadcn/ui, react-hook-form, zod, zustand, @tanstack/react-query, axios, msw
[ ] Configure next.config.ts — NEXT_PUBLIC_API_URL, NEXT_PUBLIC_WS_URL, NEXT_PUBLIC_RAZORPAY_KEY_ID
[ ] Root layout.tsx: QueryClientProvider, toast/sonner provider, Navbar shell
[ ] middleware.ts — protect /dashboard, /bookings, /vehicles, /invoices, /profile
[ ] src/mocks/handlers.ts — empty handler file, MSW worker wired in _app for dev
[ ] Verify: npm run dev starts on :3000; TypeScript strict mode passes
FE2 — Design System + Ops/Admin Scaffold
[ ] Tailwind theme tokens: brand colours, border-radius, typography scale
[ ] Shared components: StatusBadge, LoadingSpinner, PageContainer, ErrorBanner, ConfirmModal
[ ] Scaffold all route directories: /ops/gate, /ops/loading/[rake_id], /admin/dashboard, /admin/rakes, /admin/rakes/[id], /admin/users, /admin/pricing-rules
[ ] /ops/gate layout shell — full-screen, high-contrast (tablet-first: 768px, large touch targets ≥ 48×48 px)
Day 1 Done when: docker compose up --build starts cleanly; alembic upgrade head runs; seed inserts terminals and routes; npm run dev starts; GitHub CI pipeline goes green on a test PR.

Day 2 — Tuesday: Auth & Identity (S1)
Theme: A company can register, verify OTP, get KYC reviewed, invite team members, and log in.

BE1 — Full Auth + Users Module
[ ] modules/auth/services/auth_service.py — register_company(), login(), verify_otp(), refresh_token(), logout(), forgot_password(), reset_password(), accept_invite()
[ ] OTP: 6-digit random, SHA-256 hash in Redis, 5-min TTL, 3-attempt lockout → 30-min block
[ ] Password: bcrypt cost 12; enforce uppercase + number + special char (Pydantic validator)
[ ] GSTIN format validation — regex + mock GST portal response stub
[ ] modules/users/services/users_service.py — get_user_profile(), update_user_profile(), invite_company_user(), create_internal_user(), update_company_kyc()
[ ] modules/users/repository.py — get_by_id, get_by_email, get_by_gstin, list_by_company
[ ] core/dependencies.py — get_current_user, require_role(*roles), require_verified_company() fully wired
[ ] Endpoint: PATCH /companies/{id}/kyc — admin approve/reject; fires kyc.approved / kyc.rejected event
BE2 — Payments + Notifications Foundation
[ ] modules/payments/services/razorpay_client.py skeleton — create_order() signature, verify_webhook_signature() using core/security.py
[ ] modules/notifications/services/sendgrid_client.py — send_email(to, subject, html_body, attachments=[]) wrapper; configure SendGrid API key; test delivery via Mailtrap
[ ] Wire first notification: kyc.approved event → send_email() with KYC approved template [unblocks BE1 KYC flow Day 2]
[ ] Wire kyc.rejected event → rejection email with reason
[ ] Create modules/notifications/services/templates/ — add kyc_approved.html, kyc_rejected.html
BE3 — E-way Bill + Vehicle + Bookings Foundation
[ ] modules/eway_bill/services/eway_bill_service.py — fetch_and_validate_bill(): mock (USE_MOCK_GST_API=true) or real NIC API; HSN check; validity check (reject expired, warn <48h); cache Redis 15 min
[ ] modules/eway_bill/services/gst_api_client.py — real NIC client skeleton (guarded by flag)
[ ] modules/vehicles/repository.py — get_by_id, get_by_user, get_by_registration
[ ] Eligibility engine modules/vehicles/services/eligibility.py — run pytest tests/test_eligibility.py; all 12 cases pass
[ ] modules/bookings/repository.py — get_by_id, get_by_user, update_booking_status, bulk_update_status_by_rake
[ ] modules/bookings/services/bookings_service.py skeleton — create_booking() stub; transition_state() state machine guard (all valid transitions per PRD §6 with assertions)
BE4 — Inventory Models + Admin Rake CRUD
[ ] modules/inventory/repository.py — get_rakes_by_route_and_date_range, get_confirmed_count_for_rake
[ ] modules/admin/services/admin_service.py — create_rake(), list_rakes(), update_rake(), update_rake_status()
[ ] GET/POST/PATCH/DELETE /admin/rakes — full rake CRUD, verified in Swagger
[ ] Seed at least 3 test rakes on each route for the next 14 days (so FE slot picker has data to display)
FE1 — Registration + Login
[ ] /register — 4-step wizard (company profile → business verification → bank details → admin contact) — all S1A fields per PRD §7
[ ] GSTIN + PAN inline validation via Zod (mirrors backend validators)
[ ] File upload component — drag-and-drop for cancelled cheque (reused across the app)
[ ] /login — email + password → OTP step → JWT stored in authStore
[ ] OTP countdown timer (5-min expiry indicator)
[ ] authStore — setAuth, clearAuth, role helpers (useCanBook, useIsAdmin, useIsOpsStaff)
[ ] msw handlers: POST /auth/register, POST /auth/login, POST /auth/verify-otp, GET /users/me
FE2 — Registration Supporting UI + Admin Users
[ ] /settings/team — invite form (name, email, role dropdown) + pending invites list (S1B)
[ ] /admin/users — KYC queue: pending companies table + approve button + reject button + rejection reason modal
[ ] /profile — account settings (name, mobile, designation, password change)
[ ] msw handlers: GET /users/company-members, POST /users/company-members/invite, PATCH /companies/{id}/kyc
Day 2 Done when: Full registration → OTP verify → KYC pending → admin approves (KYC approved email sent via SendGrid/Mailtrap) → login → JWT issued → /dashboard accessible.

Day 3 — Wednesday: E-way Bill, Vehicles & Eligibility (S2, S3)
Theme: A verified user can fetch an e-way bill, add a vehicle, see eligibility, and enter driver details.

BE1 — Internal Users + File Uploads
[ ] POST /users/internal — admin provisions OPS_STAFF and OPS_SUPERVISOR with terminal assignment
[ ] POST /users/company-members/invite — generate invite token hash, store in user_invites, send invite email via BE2's sendgrid_client
[ ] POST /auth/accept-invite — full implementation: validate token, create user, set password, verify mobile OTP
[ ] File upload: cancelled cheque → S3 via core/s3.py; pre-signed URL returned to frontend
BE2 — Payment Flow Preparation
[ ] modules/payments/services/razorpay_client.py — create_order(booking_id, amount) full signature with idempotency key {booking_id}-{attempt_number}
[ ] POST /payments/initiate skeleton — ready for wiring on Day 4
[ ] Notification templates draft: booking_confirmation.html, payment_failed.html, booking_cancelled.html — HTML structure ready
[ ] tasks/reminder_tasks.py stubs — send_t48_reminder, send_t24_reminder, send_t6_reminder, send_gate_open_reminder task signatures defined
BE3 — Vehicles Full + Booking Creation
[ ] modules/vehicles/services/vehicles_service.py — add_vehicle(), list_user_vehicles() (most-recent-first), get_vehicle(), update_vehicle(), soft_delete_vehicle(), run_eligibility_check()
[ ] POST /vehicles, GET /vehicles, GET /vehicles/{id}, PATCH /vehicles/{id}, DELETE /vehicles/{id}, POST /vehicles/{id}/check-eligibility
[ ] POST /eway-bill/fetch — fully wired: mock adapter → validation → cache; response includes validity_status and hours_remaining
[ ] modules/bookings/services/bookings_service.py — create_booking() full implementation:
Validate active Redis reservation (calls BE4's inventory_service via interface)
Fetch e-way bill from cache (own module)
Run eligibility via own vehicles_service
Compute price snapshot (calls BE4's pricing_service via interface)
Write booking at RESERVED status; return price_snapshot JSONB
[ ] Booking number generation: RR-BKG-YYYYMMDD-XXXXXX
[ ] POST /bookings, GET /bookings, GET /bookings/{id}, GET /bookings/{id}/status
BE4 — Pricing + Slot Availability
[ ] modules/pricing/services/calculator.py — already scaffolded; run pytest tests/test_pricing.py — all 8 cases pass
[ ] modules/pricing/services/pricing_service.py — calculate_booking_price() (fetches route base_rate + driver_accommodation_charge from DB, calls calculator.py)
[ ] modules/pricing/repository.py — get_active_promo(), get_base_rate_for_route()
[ ] POST /pricing/calculate, POST /pricing/validate-promo
[ ] GET /slots/availability — query rakes in date range; compute available = total_wagons - confirmed_bookings - active_reservations; include estimated fare per slot
FE1 — Booking Wizard Steps 1 & 2
[ ] /bookings/new?step=1 — e-way bill input; auto-fill display card (consignor, consignee, commodity, GVW, route distance, validity countdown timer)
[ ] Validity states: green (>48 hrs) / amber warning banner (<48 hrs, must acknowledge) / red error (expired, links to GST portal)
[ ] /bookings/new?step=2 — vehicle picker: card grid from library (most-recent first) + "Add new vehicle" slide-over modal
[ ] Add vehicle form: live FMP eligibility preview as user types specs (height, length, width, GVW)
[ ] Eligibility result banner: green ELIGIBLE / amber CONDITIONALLY_ALLOWED (with acknowledgement checkbox) / red NOT_ALLOWED (with specific rejection reason)
[ ] Driver details form: name, mobile, licence, "driver accompanying" toggle
[ ] BookingWizardStore — setEwayBillData, setSelectedVehicle, setEligibilityResult, setDriverDetails
[ ] msw handlers: POST /eway-bill/fetch, GET /vehicles, POST /vehicles, POST /vehicles/{id}/check-eligibility
FE2 — Vehicle Library + Ops Gate Shell
[ ] /vehicles — vehicle library: cards with eligibility badge, last-used date, quick "Book again" CTA
[ ] /vehicles/add — standalone add-vehicle page (same form as wizard modal, for direct library management)
[ ] /ops/gate — QR scanner shell using html5-qrcode: camera permission request on load, scan viewfinder, result card area (booking number, vehicle reg, status change message, parking bay)
[ ] /ops/gate — manual booking ID fallback input (supervisor role only, below scanner)
[ ] msw handlers: POST /ops/gate/scan, POST /ops/gate/override
Day 3 Done when: User enters mock e-way bill → data auto-fills → selects/adds vehicle → sees eligibility verdict → enters driver details → POST /bookings returns RESERVED booking in DB.

Day 4 — Thursday: Slot Reservations, Pricing & Payment Initiation (S4, S5, S6 start)
Theme: A user can see live departure slots, reserve one with a countdown, confirm pricing, and initiate payment.

BE1 — Auth Polish + Rate Limiting
[ ] Rate limiting middleware in core/dependencies.py — Redis sliding window: 10 req/min per IP on auth endpoints; 300 req/min per user on authenticated endpoints
[ ] OTP resend: max 3 OTP sends per user per session; cooldown between resends
[ ] GET /health — checks DB connectivity, Redis ping, S3 list-bucket; returns structured JSON
[ ] Write tests/conftest.py — shared pytest fixtures (test DB session, async client, seed helper)
BE2 — Payment Initiation + Webhook
[ ] POST /payments/initiate — full implementation: creates Razorpay order; returns { order_id, key_id, amount, currency }
[ ] POST /payments/webhook — HMAC-SHA256 verify on raw body; on payment.captured → calls bookings_service.transition_to_confirmed(booking_id) (BE3 public interface); on payment.failed → calls bookings_service.transition_to_payment_failed(booking_id) (BE3 public interface)
[ ] Confirmation email: subscribe booking.confirmed event → send_email() with confirmation template + QR PNG attachment (QR URL comes from booking.qr_code_url field set by BE3)
[ ] tasks/reminder_tasks.py — full implementation: send_t48_reminder, send_t24_reminder, send_t6_reminder, send_gate_open_reminder — scheduled from confirmed_at + rake.scheduled_departure via Celery Beat
BE3 — QR Generation + Booking Confirmation PDF + Public Transition Methods
[ ] modules/bookings/services/qr_service.py — generate_qr(booking_id, vehicle_reg, departure_iso) → HMAC-SHA256 signed JSON → qrcode lib → PNG bytes; validate_qr(signed_json) → verify signature + return payload
[ ] modules/invoicing/services/pdf_service.py — WeasyPrint booking confirmation PDF: booking ID, QR image, vehicle details, terminal address, gate-open time, price receipt
[ ] Both upload to S3; pre-signed URLs written to bookings.qr_code_url + bookings.confirmation_pdf_url
[ ] GET /bookings/{id}/qr — returns pre-signed S3 URL for QR PNG
[ ] transition_to_confirmed(booking_id) public method — RESERVED → CONFIRMED; sets confirmed_at; publishes booking.confirmed; triggers QR + PDF generation
[ ] transition_to_payment_failed(booking_id) public method — RESERVED → PAYMENT_FAILED; publishes payment.failed
[ ] PATCH /bookings/{id}/cancel — guard: CONFIRMED + departure ≥ 24h; → CANCELLED; publishes booking.cancelled
BE4 — Slot Reservation (Redis) + WebSocket
[ ] modules/inventory/services/reservation_service.py — create_reservation(): Redis SETNX slot_reserve:{rake_id}:{user_id} with 15-min TTL + decrement slot_count:{rake_id}; release_reservation(): delete Redis key + increment count
[ ] POST /slots/reserve + DELETE /slots/reserve/{reservation_id}
[ ] WebSocket /ws/slots/{route_id} — on every reserve/release broadcasts { event: "slot_updated", rake_id, available } to all connected clients on that route
[ ] Celery task tasks/cleanup_tasks.py — expire_reservations(): runs every 60s, releases expired Redis keys + marks slot_reservations rows EXPIRED
FE1 — Booking Wizard Steps 3, 4 & 5
[ ] /bookings/new?step=3 — 14-day departure calendar; slot cards with availability badge (🟢 >10 / 🟡 4–10 / 🔴 1–3 / ⛔ SOLD OUT); WebSocket connection via useSlotAvailability hook
[ ] 15-minute countdown timer component: starts on reservation; "Slot expired" toast + re-select prompt when hits 0
[ ] /bookings/new?step=4 — pricing breakdown card: base freight, driver accommodation, discount, subtotal, GST (rate + amount), total; promo code input with inline validation
[ ] 3× mandatory T&C checkboxes; "Proceed to Pay" disabled until all 3 checked + reservation still active
[ ] /bookings/new?step=5 — Razorpay checkout: load razorpay script, open Razorpay({key, order_id, amount}), handle payment.failed inline
[ ] On Razorpay redirect (not webhook) — show "Payment processing..." state; poll GET /bookings/{id}/status every 3s for up to 60s until CONFIRMED
[ ] msw handlers: GET /slots/availability, POST /slots/reserve, POST /pricing/calculate, POST /payments/initiate
FE2 — Admin Rake + Slot UI
[ ] /admin/rakes — rake management table: rake number, route, departure, arrival, status badge, wagon count, "Edit" + "View Loading Plan" actions
[ ] /admin/rakes/new — create rake form: rake number, route selector, departure datetime, arrival datetime, wagon count
[ ] /admin/rakes/[id] — rake detail: booking count by status, "Mark Departed" + "Mark Arrived" CTA buttons with confirmation modal showing affected bookings count + email preview
[ ] msw handlers: GET /admin/rakes, POST /admin/rakes, PATCH /admin/rakes/{id}/status
Day 4 Done when: User selects slot → 15-min timer starts → pricing displayed → initiates Razorpay payment → booking_confirmed() fires on webhook → booking status CONFIRMED → QR PNG + confirmation PDF in S3 → confirmation email in Mailtrap.

Day 5 — Friday: Booking Confirmation UI + Operations Endpoints (S7, S8, S9)
Theme: User receives QR + PDF confirmation. Ops staff can scan QR and manage loading.

Phase 1 ops scope: Gate = QR scan + state transitions only. No digital weighbridge or GVW entry — physical measurements stay at the terminal.

BE1 — Tests
[ ] Write tests/test_auth.py — register → OTP → login → JWT decode → protected endpoint access
[ ] Write tests/test_booking_state_machine.py — all valid transitions succeed; all invalid transitions raise InvalidStateTransitionException; cancellation guard (<24h) raises correctly
BE2 — Full Notification Suite + Refund
[ ] Email templates in modules/notifications/services/templates/ — HTML for: booking_confirmation, t48_reminder, t24_reminder, t6_reminder, gate_open, loading_sequence, rake_departed, rake_arrived, journey_completed, invoice, payment_failed, booking_cancelled, storage_charge, refund_processed
[ ] Wire all remaining event subscribers:
booking.cancelled → cancellation email
rake.departed → departure email (vehicle reg, rake number, expected arrival)
rake.arrived → arrival email ("collect within 4 hrs")
booking.unloaded → journey completed email (invoice attached when ready)
payment.failed → payment failed email with retry link
[ ] POST /admin/refunds — initiate Razorpay refund; transition CANCELLED → REFUNDED; send refund confirmation email
[ ] GET /payments/{id}/status — payment status lookup
[ ] Write tests/test_payments.py — payment.captured webhook → CONFIRMED; payment.failed → PAYMENT_FAILED; tampered signature → 400; duplicate webhook → idempotent (no double confirmation)
BE3 — Ops Gate + Loading Plan + Invoice Service
[ ] modules/operations/services/operations_service.py — full implementation: scan_gate_qr() (QR HMAC check, gate window, IN/OUT routing, state transitions), override_gate_entry() (supervisor only, full audit log)
[ ] modules/operations/repository.py — create_gate_entry(), get_or_create_loading_plan(), mark_loading_item_loaded()
[ ] modules/operations/services/loading_plan_service.py — auto-generate on first GET /ops/loading/{rake_id}: weight-balance across wagons; JOS wagons 1–15, KEBG wagons 16–25; heavy vehicles (GVW >35T) in central wagons
[ ] POST /ops/loading/{rake_id}/mark-loaded — marks item loaded; when all loaded → publishes rake.all_loaded
[ ] transition_to_loaded(booking_id) public method — GATE_ENTRY → LOADED
[ ] transition_to_unloaded(booking_id) public method — LOADED → UNLOADED; publishes booking.unloaded
[ ] bulk_transition_to_in_transit(rake_id) public method — bulk LOADED → IN_TRANSIT (called by BE4 admin)
[ ] bulk_transition_to_arrived(rake_id) public method — bulk IN_TRANSIT → ARRIVED (called by BE4 admin)
[ ] transition_to_no_show(booking_id) public method — ARRIVED → NO_SHOW (called by BE4 cleanup task)
[ ] modules/invoicing/services/invoice_service.py — generate_invoice(): IGST vs CGST+SGST split; invoice number INV-RR-YYYYMMDD-XXXXX; IRP flag check (mock → always irn_required: false)
[ ] Invoice PDF via WeasyPrint: SAC 996511, GST fields, IRN placeholder, charge breakdown; upload to S3; GET /invoices, GET /invoices/{id}/pdf
BE4 — Departure/Arrival Cascade + No-Show
[ ] PATCH /admin/rakes/{id}/status DEPARTED — calls bookings_service.bulk_transition_to_in_transit(rake_id) (BE3 interface); sets booking.departed_at; fires rake.departed event
[ ] PATCH /admin/rakes/{id}/status ARRIVED — calls bookings_service.bulk_transition_to_arrived(rake_id) (BE3 interface); sets booking.arrived_at; fires rake.arrived event
[ ] tasks/cleanup_tasks.py — mark_no_shows(): every 15 min; query ARRIVED bookings where arrived_at + 4h < NOW(); calls bookings_service.transition_to_no_show(booking_id) (BE3 interface)
FE1 — Booking Confirmation + Status + Invoices
[ ] /bookings/[id]/confirmation — confirmation page: booking number, QR code <img>, departure details, terminal address + Google Maps link, PDF download button, "Add to calendar" link
[ ] Payment failure screen — "Retry" CTA, reservation TTL remaining, "Choose different slot" link after 3 failures
[ ] /bookings/[id] — booking detail: status timeline stepper (all 10 statuses), vehicle snapshot, pricing summary, QR download, PDF download
[ ] /bookings — bookings list with status filter chips (Active / Completed / Cancelled) and search by booking number
[ ] /dashboard — active bookings cards (next departure first), quick stats (active bookings, total spent, next departure countdown)
[ ] /invoices — invoice list with download button per row
[ ] /invoices/[id] — invoice detail with @media print CSS; download PDF button
FE2 — Ops Gate Full + Loading Plan
[ ] /ops/gate — fully functional QR scanner (html5-qrcode): camera permission flow; scan result card shows booking number, vehicle reg, new status, parking bay; error states (invalid QR, expired booking, wrong terminal)
[ ] /ops/gate — IN vs OUT mode toggle (entry scan changes booking to GATE_ENTRY; exit scan changes to UNLOADED)
[ ] /ops/loading/[rake_id] — loading plan table: wagon number, sequence, vehicle reg, GVW, loaded checkbox; sorted by load_sequence; "All loaded — confirm departure ready" CTA at bottom
[ ] msw handlers: POST /ops/gate/scan, GET /ops/loading/{rake_id}, POST /ops/loading/{rake_id}/mark-loaded
Day 5 Done when: QR scan on /ops/gate transitions booking to GATE_ENTRY; admin marks DEPARTED (all bookings → IN_TRANSIT, departure emails fire); admin marks ARRIVED; exit scan → UNLOADED → invoice generation triggered.

Day 6 — Saturday: Invoice Delivery + Admin Polish + End-to-End Wiring
Theme: Full journey completes. Invoice delivered. Admin has all tools needed for launch.

BE1 — Security Hardening + Deploy Prep
[ ] Verify AES-256-GCM encryption applied to PAN (companies.pan) and bank account (companies.bank_account) on write; decrypt on read in KYC admin view
[ ] Verify GATE_QR_SECRET ≠ SECRET_KEY — enforced in Settings validator
[ ] Monthly bookings partition creation: tasks/cleanup_tasks.py — create_next_month_partition() cron on 25th of each month
[ ] Production Dockerfile verified — fonts-liberation installed for WeasyPrint; no dev dependencies in image
[ ] Write staging docker-compose.prod.yml — no hot-reload, gunicorn worker, env from Railway secrets
BE2 — Storage Charges + Invoice Notification
[ ] Storage charge alert: mark_no_shows Celery task extended — when ARRIVED booking hits 4-hr grace, send storage charge alert email (₹500/day; driver + company user)
[ ] Wire booking.unloaded event → fire tasks/invoice_tasks.py — generate_invoice_async() Celery task → calls BE3's invoice_service.generate_invoice(); on completion sends invoice email with PDF attachment
[ ] Refund processed email: when PATCH /admin/refunds completes → send refund confirmation email with amount + timeline
[ ] Verify all 16 notification types from PRD §10 are wired (audit each trigger)
BE3 — Invoice + Ops Final
[ ] Subscribe booking.unloaded → generate_invoice_async task; verify invoice is generated within 30s
[ ] GET /invoices — scoped by user (company users see own company's invoices; admin sees all)
[ ] Write tests/test_gate_operations.py — valid QR → GATE_ENTRY; forged QR signature → 403; supervisor override → audit log written; exit scan → UNLOADED; booking.unloaded event fires
[ ] E-way bill Part-B update stub — modules/eway_bill/services/eway_bill_service.py add update_part_b() function (mock implementation; real NIC API call stubbed for Phase 2)
BE4 — Analytics + Pricing Admin + Final Polish
[ ] GET /admin/analytics/overview — booking counts by status, total revenue (sum of total_amount where CONFIRMED+), rake utilisation % per route
[ ] GET /admin/analytics/utilisation — utilisation per rake (confirmed_bookings / total_wagons × 100)
[ ] GET /admin/analytics/revenue — revenue breakdown by route and date range
[ ] GET/POST/PATCH /admin/pricing-rules — manage base rates, GST rate, driver accommodation charge, extra charge rules, promo codes (admin-configurable without code changes)
[ ] Write tests/test_slot_reservation.py — concurrent reservation race; TTL expiry releases slot; slot count reconciliation
FE1 — Feedback + Final Polish
[ ] Feedback form on /bookings/[id] — shows after COMPLETED; 5-star ratings (overall, booking process, staff, transit, vehicle condition) + optional comment + "Interested in return trip?" toggle
[ ] POST /bookings/{id}/feedback wired
[ ] Empty states: no bookings → "Start your first booking" CTA; no vehicles → "Add a vehicle" CTA; no invoices → "Complete a journey to see invoices here"
[ ] Mobile responsiveness pass on booking wizard (375px breakpoint — must be fully usable)
[ ] Error boundary components — friendly error screen for unexpected failures with "Contact support" link
FE2 — Admin Dashboard + Pricing + Analytics
[ ] /admin/dashboard — key metrics cards: total bookings, revenue, utilisation rate; active rakes table; KYC queue count badge
[ ] /admin/pricing-rules — pricing rules table with inline edit; "Add promo code" modal (code, discount type, value, validity dates, usage limit)
[ ] /admin/analytics — utilisation chart per route (bar chart), revenue over time (line chart) — use recharts or shadcn/ui chart components
[ ] /admin/users/internal — internal user management: provision OPS_STAFF / OPS_SUPERVISOR with terminal assignment
[ ] Service worker for /ops/gate — cache today's expected arrival list (booking number + vehicle reg) for offline fallback; queue scan results; sync on reconnect
Day 6 Done when: Full journey confirmed on staging — register → book → pay → gate scan → load → depart → arrive → exit scan → invoice generated and emailed. All 16 notification types verified in Mailtrap.

Day 7 — Sunday: Testing, Staging Deploy & Launch Readiness
Theme: System is production-deployable. All critical paths tested. Ops team can be trained.

BE1 — Staging Deploy + Health Check
[ ] Deploy backend to Railway (or Render) from master branch
[ ] Configure all production env vars in Railway: real Razorpay test keys, SendGrid live, S3 production bucket, strong SECRET_KEY and GATE_QR_SECRET
[ ] Run alembic upgrade head on production DB
[ ] Run seed script on production DB (terminals, routes, admin user)
[ ] GET /health extended — DB query round-trip ms, Redis ping ms, S3 head-object check; return { status, db, redis, s3 }
[ ] Write scripts/smoke_test.sh — hits /health, /auth/login (test creds), /slots/availability; asserts 200s
BE2 — Final Notification Audit + Webhook Test
[ ] Use Razorpay webhook simulator — fire payment.captured, payment.failed against staging; verify booking state transitions correctly each time
[ ] Verify all Celery Beat schedules registered: expire_reservations (60s), mark_no_shows (15m), create_next_month_partition (25th 00:00)
[ ] Verify delivery webhooks from SendGrid are logged in notifications.delivery_status
[ ] Final notification audit: walk through every row in PRD §10 table; verify trigger, recipient, content are correct
BE3 — Integration Tests + E-way Bill Audit
[ ] Write tests/test_invoice.py — booking UNLOADED → invoice generated within 30s; IGST vs CGST+SGST split correct for interstate vs intrastate; invoice number format correct
[ ] Write tests/test_eway_bill.py — mock adapter: each bill prefix (331*, 332*, 333*, 334*, 999*) triggers correct validation branch
[ ] Verify QR HMAC: tampered payload → verify_qr_payload raises ValueError; correct payload → returns booking data
[ ] pytest tests/ full run — 0 failures; ≥ 80% coverage on modules/
BE4 — Load Test + Cleanup
[ ] locust load test: 50 concurrent users hitting GET /slots/availability and POST /slots/reserve — verify no race conditions; check slot count stays consistent after test
[ ] Verify nightly Redis reconciliation would correctly re-sync slot counts against DB
[ ] Confirm bookings_2026_07 and bookings_2026_08 partitions created; verify insert to each succeeds
[ ] GET /admin/analytics/overview verified against known seed data — numbers are correct
FE1 — Playwright E2E + Polish
[ ] Playwright test: register → verify OTP → login → fetch e-way bill → add vehicle → select slot → pricing → mock payment → confirmation screen (QR visible + PDF download link present)
[ ] Playwright test: booking cancellation flow (CONFIRMED → cancel → CANCELLED status shown)
[ ] Fix any bugs found during staging walkthrough
[ ] Accessibility pass on booking wizard: keyboard navigation, ARIA labels on form fields, error messages announced to screen readers
FE2 — Playwright Ops Tests + Final Deploy
[ ] Deploy frontend to Vercel (production domain or preview URL)
[ ] Playwright test: /ops/gate — mock valid QR scan → success result card shown; mock invalid QR → error message shown
[ ] Playwright test: /ops/loading/[rake_id] — loading plan renders; check wagon loaded → counter updates
[ ] /admin/pricing-rules — full CRUD verified manually in staging
[ ] Tablet test: open /ops/gate on iPad or Chrome DevTools tablet emulation — QR scanner activates, touch targets are usable
Day 7 Done when: All sprint completion criteria below are met on staging.

Sprint Completion Criteria
All of the following must pass before declaring Phase 1 complete:

[ ] pytest suite: 0 failures, ≥ 80% coverage on core modules (auth, eligibility, pricing, state machine, payments webhook, invoice, gate ops)
[ ] Full E2E journey verified on staging: register → e-way bill → vehicle → slot → pay → QR → gate scan → load → depart → arrive → exit scan → invoice emailed
[ ] Razorpay webhook: payment.captured → booking CONFIRMED within 5 seconds
[ ] Slot reservation TTL: expired reservation releases Redis slot within 60 seconds
[ ] QR scan: valid QR transitions booking within 2 seconds; forged/invalid QR returns 403
[ ] Invoice PDF: generated within 30 seconds of UNLOADED status
[ ] Confirmation email: delivered within 60 seconds of payment webhook
[ ] All 7 active user roles enforce correct permissions per PRD §3 role matrix
[ ] GET /health returns 200 with DB, Redis, S3 all healthy
[ ] docker compose up --build succeeds in < 5 minutes on a clean machine
[ ] /ops/gate QR scanner works on Chrome tablet (768px) — camera activates, scan result renders
Dependency Map
Day 1:  BE1 (migrations + core/) ──► BE2, BE3, BE4 write real models from Day 2
        BE1 (core/security.py)   ──► BE2 uses JWT + HMAC utilities from Day 2
        FE1 (scaffold + msw)     ──► FE2 builds on shared layout from Day 1

Day 2:  BE1 (get_current_user dep) ──► BE2, BE3, BE4 apply role guards to routers
        BE2 (sendgrid_client)    ──► BE1 fires KYC emails
        BE3 (bookings skeleton)  ──► full booking flow possible from Day 3
        BE4 (seed rakes)         ──► FE1/FE2 slot picker has real data

Day 3:  BE3 (vehicles_service.run_eligibility_check) ──► called inside BE3's own create_booking()
        BE4 (pricing_service.calculate_booking_price) ──► called by BE3's create_booking() via interface
        BE3 (POST /bookings)     ──► FE1 wizard steps 1→3 complete end-to-end

Day 4:  BE4 (slot reservation endpoints)       ──► BE3 create_booking() validates active reservation
        BE3 (transition_to_confirmed public)   ──► BE2 webhook calls it on payment.captured
        BE3 (qr_service / qr_code_url on booking) ──► BE2 attaches QR URL to confirmation email

Day 5:  BE3 (ops/gate/scan)                    ──► FE2 wires real API into /ops/gate
        BE3 (bulk_transition_to_in_transit)    ──► BE4 admin DEPARTED endpoint calls it
        BE3 (bulk_transition_to_arrived)       ──► BE4 admin ARRIVED endpoint calls it
        BE2 (departure/arrival email events)   ──► all post-booking notifications fire

Day 6:  BE3 (invoice_service.generate_invoice) ──► BE2 Celery task calls it; FE1 invoice page has data
        BE4 (analytics endpoints)              ──► FE2 admin dashboard shows real numbers

Day 7:  BE1 (staging deploy) ──► all testing runs on real infra
        Playwright tests depend on all backend + frontend being live on staging
Risk Log
Risk	Who it hits	Mitigation
NIC GST API credentials not ready	BE3	USE_MOCK_GST_API=true; mock adapter covers all branches; real API is a one-line config swap
SendGrid domain auth takes > 1 day	BE2	Start pre-sprint; use Mailtrap in dev — all email logic testable from Day 2 regardless
Razorpay webhook not received in test	BE2	Razorpay webhook simulator tool in dashboard; unit test covers all event types with mocked payload
WeasyPrint fonts on Linux/Docker	BE3	fonts-liberation in Dockerfile; test PDF generation inside Docker on Day 3 — not Day 7
Redis slot count drift (crash mid-reserve)	BE4	Nightly reconciliation cron; DB count fallback when Redis key missing
BE3 module load is heaviest — owns 5 modules including bookings (most complex)	BE3	Stub create_booking() early (Day 2) so Day 3 is refinement. Eligibility + pricing stay in own modules so complexity is distributed.
BE2 webhook blocked if BE3 transition_to_confirmed not ready	BE2	BE3 exposes public method stub with correct signature by EOD Day 3; BE2 mocks it locally until Day 4
FE blocked waiting for backend endpoints	FE1, FE2	msw mock handlers — frontend development never stops for backend availability
Concurrent reservation race condition	BE4	Redis pipeline + WATCH; locust load test on Day 7 before marking done
Post-Sprint (Day 8+)
Task	Owner	Priority
Write incident runbook (payment stuck, QR fails, webhook timeout)	BE1 + BE2	HIGH
Admin enters first 4 weeks of rake schedules	Ops team	HIGH
Ops staff training session on /ops/gate and /ops/loading	FE2 + BE3	HIGH
Finalise cancellation refund policy (>24h = 100%, 12–24h = 50%, <12h = 0%) and update T&Cs	Product + Legal	HIGH
GSTIN registration with NIC for production GST API access	Business	MEDIUM
WhatsApp WABA registration (Phase 2 — 7–10 day approval) — apply now	Business	MEDIUM
Playwright full regression suite	FE1	LOW
Admin analytics chart components (recharts)	FE2	LOW