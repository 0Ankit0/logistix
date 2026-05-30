# Requirements Document — Logistics Tracking System

**Version:** 2.0  
**Status:** Approved  
**Owner:** Product & Engineering — Logistics Platform Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Stakeholders](#stakeholders)
4. [Functional Requirements](#functional-requirements)
5. [Non-Functional Requirements](#non-functional-requirements)
6. [Scope and Phasing](#scope-and-phasing)
7. [Constraints and Assumptions](#constraints-and-assumptions)
8. [Requirement Coverage Matrix](#requirement-coverage-matrix)

---

## Executive Summary

The Logistics Tracking System is a production-grade, multi-carrier shipment visibility platform that provides end-to-end tracking for parcels, freight, and specialised cargo (hazardous materials, temperature-sensitive goods). The platform integrates with global carriers (FedEx, UPS, DHL, USPS) and local last-mile providers through a unified carrier adapter layer, and exposes a real-time tracking API consumed by shipper portals, consumer-facing tracking pages, carrier dashboards, and third-party e-commerce platforms.

The system processes upward of 500,000 shipment events per day at peak, maintains a 99.9 % availability SLO, and guarantees tracking updates are visible to end-users within 30 seconds of a physical scan or GPS ping. The platform also manages exception detection and resolution, customs compliance, returns orchestration, and a full analytics suite for operational reporting.

---

## Problem Statement

### Pain Points of Traditional Logistics Tracking

1. **Fragmented carrier data** — Each carrier exposes a different polling API with inconsistent event schemas, forcing operations teams to maintain separate integrations and reconcile conflicting statuses manually.
2. **Polling latency** — Traditional webhook-free carrier integrations rely on periodic polling (every 15–60 minutes), resulting in stale tracking pages and reactive (not proactive) exception management.
3. **No unified exception workflow** — Exceptions (delays, customs holds, failed delivery attempts, damaged goods) are detected late, tracked in spreadsheets, and escalated inconsistently, eroding customer trust and increasing support ticket volume.
4. **Last-mile visibility gap** — Visibility frequently disappears once a shipment leaves the hub and enters last-mile delivery. Consignees receive no live ETA or driver location, leading to missed deliveries and redelivery costs.
5. **Manual proof of delivery** — Paper-based or photograph-only POD processes are slow to upload, difficult to dispute, and not legally defensible in high-value cargo claims.
6. **Returns friction** — Reverse logistics is treated as an afterthought: RMA issuance, return label generation, and refund triggering are disconnected workflows with no single source of truth.
7. **Customs documentation bottlenecks** — International shipments frequently stall because customs declarations are incomplete, HS codes are misclassified, or dangerous-goods manifests are missing, causing delays and fines.
8. **Siloed analytics** — Carrier performance, SLA compliance, and delivery success rates exist in separate reporting silos with no cross-carrier benchmarking or drill-down capability.
9. **No programmatic notification framework** — Shippers must build their own notification logic by polling tracking APIs, leading to inconsistent customer communication and missed SLA-breach alerts.

---

## Stakeholders

| Role | Organisation | Responsibilities | Primary Interaction |
|---|---|---|---|
| Shipper | Merchant / 3PL | Creates shipments, tracks outbound orders, disputes exceptions, reviews analytics | API, shipper portal |
| Consignee / Recipient | End customer | Tracks incoming delivery, provides delivery preferences, signs/confirms POD | Tracking portal, SMS, email |
| Driver | Last-mile carrier partner | Executes pickups and deliveries, captures POD, raises exceptions | Driver mobile app |
| Dispatcher | Carrier operations | Assigns drivers to runs, manages route plans, monitors real-time driver locations | Dispatch dashboard |
| Customs Agent | Freight forwarder / government | Reviews and approves customs declarations, HS code classification, ADR/IATA compliance | Customs module, document portal |
| Customer Service Agent | Support team | Resolves exception tickets, reships or refunds on lost/damaged claims, provides status updates | CRM integration, exception dashboard |
| Operations Manager | Platform owner | Monitors SLA dashboards, approves exception escalations, reviews carrier performance | Analytics portal, alerting console |
| Finance / Billing | Internal finance | Reviews carrier invoicing, reconciles freight charges, processes refunds and claims | Billing integration, reports |
| Integration Engineer | Partner or internal | Connects e-commerce platforms, WMS, or ERP systems to the tracking API | REST API, webhooks, SDK |
| Compliance Officer | Legal / risk | Ensures ADR, IATA, GDPR, and customs-regulation compliance; reviews audit logs | Compliance module, audit export |

---

## Functional Requirements

### Module 1: Shipment Management (FR-001 – FR-010)

**FR-001 — Create Shipment**  
The system shall accept a `POST /shipments` request containing origin address, destination address, cargo dimensions/weight, service level (standard, express, overnight, same-day), declared value, and cargo description. The API shall validate all mandatory fields, normalise and validate addresses against a geocoding service, and return a `shipment_id` and `tracking_number` on success.

**FR-002 — Confirm Shipment**  
The system shall transition a shipment from `Draft` to `Confirmed` only after carrier capacity allocation succeeds and address validation passes. Confirmation shall emit `shipment.confirmed.v1` and start the SLA clock.

**FR-003 — Update Shipment Details**  
The system shall allow shippers to update cargo dimensions, declared value, special instructions, or delivery preferences on shipments in `Draft` or `Confirmed` state. Updates to address shall require re-validation. Updates after `PickedUp` are rejected with HTTP 409.

**FR-004 — Cancel Shipment**  
The system shall allow cancellation of shipments in any non-terminal state except `PickedUp` and `InTransit`, subject to carrier-specific cut-off windows. Cancellation requires a reason code and shall trigger refund calculation. `shipment.cancelled.v1` is emitted with cancellation metadata.

**FR-005 — Place Shipment on Hold**  
The system shall allow authorised users to place a shipment on hold (e.g., for compliance review or payment hold) before it transitions to `PickupScheduled`. A hold reason and expiry timestamp are required. The system shall automatically release the hold at expiry or when manually resolved.

**FR-006 — Schedule Pickup**  
The system shall allow shippers to request a pickup window. The planning service shall attempt to find a carrier slot within the requested window, confirm it, and emit `shipment.pickup_scheduled.v1` with driver ID and estimated pickup time.

**FR-007 — Re-schedule Pickup**  
The system shall allow pickup rescheduling up to 2 hours before the original slot. Rescheduling emits `shipment.pickup_rescheduled.v1` and notifies the assigned driver.

**FR-008 — Batch Shipment Creation**  
The system shall support bulk creation of up to 1,000 shipments in a single API call via `POST /shipments/batch`. Each shipment is processed independently; the response includes per-item success/failure with validation errors for failed items.

**FR-009 — Shipment Label Generation**  
The system shall generate a carrier-formatted shipping label (ZPL or PDF) upon shipment confirmation. Labels shall be retrievable via `GET /shipments/{id}/label` and stored in S3 for 90 days.

**FR-010 — Shipment Search and Filtering**  
The system shall provide a search endpoint supporting filters by tracking number, carrier, origin/destination, date range, status, and shipper reference. Results shall be paginated (max 100 per page) and sortable. Full-text search on cargo description and address fields shall be powered by OpenSearch.

---

### Module 2: Carrier Integration (FR-011 – FR-020)

**FR-011 — FedEx Integration**  
The system shall integrate with FedEx Ship API v1 and Track API v1 to create shipments, generate labels, subscribe to tracking events, and retrieve POD. The adapter shall map FedEx status codes to canonical tracking event types.

**FR-012 — UPS Integration**  
The system shall integrate with UPS Developer API (Shipping, Tracking, Address Validation). The adapter shall support UPS My Choice delivery preferences and handle UPS-specific exception codes.

**FR-013 — DHL Integration**  
The system shall integrate with DHL Express Unified API for international shipments, including customs pre-clearance document submission and Piece tracking.

**FR-014 — USPS Integration**  
The system shall integrate with USPS Web Tools API for domestic US shipments, supporting Priority Mail, First-Class, and Media Mail services. The adapter shall handle USPS XML responses and map them to canonical events.

**FR-015 — Local Carrier Plug-in Framework**  
The system shall provide a carrier adapter interface (`CarrierAdapter`) that allows new local or regional carriers to be integrated without modifying core domain logic. Each adapter must implement: `createShipment`, `cancelShipment`, `getTrackingEvents`, `generateLabel`, and `getProofOfDelivery`.

**FR-016 — Carrier Allocation Engine**  
The system shall automatically allocate a carrier to a shipment based on: origin/destination lane availability, service level requirements, carrier rates, carrier current capacity, and shipper preferences. The allocation engine shall support manual override by dispatchers.

**FR-017 — Carrier Capacity Management**  
The system shall maintain a real-time view of carrier capacity by lane and service level. When capacity is exhausted, the allocation engine shall fall back to the next preferred carrier. Low-capacity alerts shall be sent to dispatchers.

**FR-018 — Carrier Rate Shopping**  
The system shall query all eligible carriers for a given shipment and return a ranked list of rates, transit times, and service levels. Shippers may select a specific carrier/service or defer to the allocation engine.

**FR-019 — Carrier Webhook Ingestion**  
The system shall provide inbound webhook endpoints for carriers that support push notifications (DHL, FedEx), verifying HMAC signatures, deduplicating events, and routing them through the canonical tracking event pipeline.

**FR-020 — Carrier Performance Tracking**  
The system shall record carrier-level metrics including on-time pickup rate, on-time delivery rate, exception rate, and average transit time by lane. Metrics shall be aggregated daily and available via the analytics API.

---

### Module 3: Real-Time Tracking (FR-021 – FR-030)

**FR-021 — Tracking Event Ingestion**  
The system shall ingest tracking events from: carrier API polling, carrier webhooks, driver app scans (barcode/NFC), GPS telemetry pings, hub scanner EDI feeds, and manual overrides by operations staff. All events shall be normalised to the canonical `TrackingEvent` schema before persistence.

**FR-022 — Tracking Event Deduplication**  
The system shall deduplicate tracking events using a composite key of `(carrier_id, tracking_number, event_code, event_timestamp)`. Duplicate events shall be acknowledged without insertion and flagged in the audit log.

**FR-023 — Public Tracking Page**  
The system shall expose a public tracking URL (`/track/{tracking_number}`) that renders the current shipment status, event timeline, estimated delivery date, and a map of the last known location. The page shall receive live updates via Server-Sent Events (SSE) without requiring page refresh.

**FR-024 — GPS Telemetry Ingestion**  
The system shall ingest GPS coordinates from driver mobile apps via MQTT at a cadence of at least once every 30 seconds when a driver is on an active run. Coordinates shall be stored in TimescaleDB with `recorded_at` timestamp, accuracy radius, and battery level. Telemetry gaps > 5 minutes shall trigger a monitoring alert.

**FR-025 — Breadcrumb Trail Storage**  
The system shall store the full GPS breadcrumb trail for each shipment leg. The trail shall be queryable by time range and shall be used to reconstruct the route on the tracking map. Breadcrumb data shall be retained for 90 days.

**FR-026 — Estimated Delivery Date (EDD) Calculation**  
The system shall calculate and continuously update the EDD for each shipment using: the current state, historical lane performance data (P50/P95 transit times), current carrier network conditions, time-of-day cutoffs, and weather/event overlays. EDD shall be recalculated on every custody scan and published as `shipment.eta_updated.v1`.

**FR-027 — EDD Accuracy Monitoring**  
The system shall record the predicted EDD at the time of shipment confirmation and the actual delivery time for every delivered shipment. The analytics module shall report EDD accuracy (% delivered within predicted window) by carrier and lane.

**FR-028 — Geofence Monitoring**  
The system shall support configurable geofences around hub facilities and delivery addresses. When a driver's GPS position enters or exits a geofence, the system shall emit `shipment.geofence_entered.v1` or `shipment.geofence_exited.v1`. Hub arrival geofence events shall trigger scan reconciliation checks.

**FR-029 — Live Driver Location Sharing**  
The system shall allow consignees to view a live map of the assigned driver's location during the last-mile delivery window (when shipment is `OutForDelivery`). The shared location shall be anonymised beyond 500 m of the delivery address to protect driver privacy.

**FR-030 — Tracking Event Timeline**  
The system shall expose a `GET /shipments/{id}/events` endpoint returning the full ordered event timeline including: event type, event timestamp, location (facility name or lat/lng), carrier event code, and originating system. Events shall be immutable once stored.

---

### Module 4: Last-Mile Delivery (FR-031 – FR-038)

**FR-031 — Route Optimisation**  
The system shall compute an optimised delivery sequence for a driver's daily manifest using a TSP heuristic (nearest-neighbour + 2-opt improvement) with real-time traffic data. Route computation shall complete within 10 seconds for manifests of up to 100 stops.

**FR-032 — Dynamic Re-Routing**  
The system shall support dynamic stop insertion and removal from an active route without requiring a full recomputation. Re-routing shall be triggered by: new high-priority deliveries, failed delivery attempts, traffic incidents, and road closures.

**FR-033 — Driver Assignment**  
The system shall assign shipments to drivers based on: geographic proximity, driver capacity remaining, vehicle type constraints, and time-window requirements. Dispatchers may override automated assignments.

**FR-034 — Driver Mobile App Support**  
The system shall provide a driver-facing API (BFF layer) with endpoints for: retrieving the day's manifest, receiving optimised route instructions, updating stop status, capturing POD, reporting exceptions, and submitting GPS pings. The API shall support offline-first operation with sync on connectivity restoration.

**FR-035 — Delivery Attempt Recording**  
The system shall record every delivery attempt with: attempt timestamp, GPS coordinates, outcome (delivered, failed — reason code), POD artifact IDs, and next-attempt scheduling. Attempt records are immutable.

**FR-036 — Delivery Window Notification**  
The system shall send consignees a narrowed delivery window notification (2-hour window, then 30-minute window) when the driver is approaching the stop. Notifications shall be sent via SMS and push notification.

**FR-037 — Safe Place / Access Instructions**  
The system shall allow consignees to specify safe place instructions (e.g., "leave in porch", "with neighbour at No. 42") and access codes that are surfaced to the driver app at the delivery stop. Instructions shall be encrypted at rest.

**FR-038 — Delivery Preference Management**  
The system shall allow consignees to set preferences including: reschedule delivery date, redirect to a collection point, authorise a neighbour to receive, or require an age verification check. Preferences must be captured before the shipment reaches `OutForDelivery`.

---

### Module 5: Proof of Delivery (FR-039 – FR-045)

**FR-039 — Electronic Signature Capture**  
The system shall allow drivers to capture a consignee's electronic signature on a touchscreen device. The signature image (PNG, min 200×100 px) shall be uploaded to S3 and linked to the delivery attempt record with a cryptographic hash.

**FR-040 — Geo-Stamped Photo Capture**  
The system shall allow drivers to capture a photo of the delivered package at the drop location. The photo shall be embedded with GPS coordinates and timestamp EXIF data, uploaded to S3, and linked to the delivery record.

**FR-041 — OTP-Based Delivery Confirmation**  
For high-value or age-verified shipments, the system shall generate a 6-digit OTP sent to the consignee's registered mobile number. The driver shall enter the OTP in the delivery app to confirm receipt. OTPs expire after 10 minutes.

**FR-042 — POD Document Generation**  
The system shall generate a PDF Proof of Delivery document combining: shipment details, delivery timestamp, consignee name, signature image, photo thumbnail, GPS coordinates, and OTP confirmation (if applicable). The PDF shall be available via `GET /shipments/{id}/pod` and emailed to the shipper automatically.

**FR-043 — POD Tampering Detection**  
The system shall store a SHA-256 hash of each POD document at generation time. Any subsequent retrieval shall verify the hash and return HTTP 422 with an integrity error if the document has been modified.

**FR-044 — Offline POD Capture**  
The driver app shall support offline POD capture when no network connectivity is available. Captured data (signature, photo, GPS, timestamp) shall be stored locally with encryption and automatically synced to the server when connectivity is restored within 4 hours.

**FR-045 — POD Dispute Management**  
The system shall allow shippers and consignees to raise a POD dispute within 14 days of delivery. Dispute records shall capture the reason, disputing party, timestamps, and resolution outcome. Customer service agents shall have a dispute resolution interface.

---

### Module 6: Exception Management (FR-046 – FR-052)

**FR-046 — Automatic Exception Detection**  
The system shall automatically detect exceptions using rule-based checks including: missed pickup (driver not scanned within threshold), telemetry gap (GPS silent > 4 h while InTransit), customs hold (carrier event code maps to customs exception), failed delivery attempt, damaged goods report, and address undeliverable.

**FR-047 — Exception Classification**  
Detected exceptions shall be classified by type (delay, damage, address, customs, weather, carrier, capacity) and severity (SEV-1: delivery at risk today; SEV-2: delivery at risk this week; SEV-3: advisory). Classification drives notification urgency and SLA clocks.

**FR-048 — Exception Assignment and Ownership**  
Every open exception shall have an assigned owner (customer service agent or operations manager) and a resolution ETA. Unassigned exceptions older than 30 minutes shall be auto-escalated to the team lead.

**FR-049 — Exception Escalation Workflow**  
The system shall define escalation tiers: (1) auto-notification to owner, (2) escalation to team lead if unresolved at 50 % of resolution SLA, (3) escalation to operations manager at 100 % SLA breach. Each tier sends a notification via the configured channel.

**FR-050 — Exception Resolution Recording**  
When an exception is resolved, the resolving agent shall record: resolution action taken, new EDD (if changed), and any carrier credit or compensation triggered. `shipment.exception_resolved.v1` shall be emitted and the shipment returned to the appropriate state.

**FR-051 — Exception Analytics**  
The system shall report exception rates by carrier, lane, exception type, and time period. Dashboards shall show average resolution time, escalation rate, and SLA breach rate by severity.

**FR-052 — Damage Claims Initiation**  
For exceptions of type `damage`, the system shall initiate a damage claim workflow: notify the carrier, generate a claim reference, collect evidence (POD photos, manifest), and track claim status through to resolution.

---

### Module 7: Customs and Compliance (FR-053 – FR-058)

**FR-053 — Customs Declaration Creation**  
The system shall generate an electronic customs declaration (CN22/CN23 for postal, commercial invoice for courier) from shipment data including: shipper/consignee details, cargo description, HS code, declared value, country of origin, and incoterms.

**FR-054 — HS Code Classification**  
The system shall provide an HS code lookup and validation API. Shippers may search by product description; the system shall suggest the most likely HS code using a classification model. Validated HS codes shall be stored against the cargo record.

**FR-055 — Customs Document Submission**  
The system shall electronically submit customs pre-clearance documents to carriers (DHL, FedEx) that support pre-filing. Submission status (`submitted`, `accepted`, `query`, `rejected`) shall be tracked and surfaced in the customs dashboard.

**FR-056 — ADR Compliance (Dangerous Goods)**  
The system shall validate shipments containing dangerous goods against ADR (road transport) and IATA (air transport) regulations: permitted packing groups, quantity limits, label requirements, and documentation. Non-compliant shipments shall be rejected with a detailed error list.

**FR-057 — Customs Hold Management**  
When a carrier reports a customs hold, the system shall raise an exception of type `customs`, notify the customs agent and shipper, and surface the required action (submit additional documentation, pay duty, etc.). The system shall track document submission and hold release.

**FR-058 — Sanctions and Restricted Party Screening**  
The system shall screen shipper, consignee, and cargo against restricted-party lists (OFAC SDN, EU sanctions, UK FCDO) at shipment creation. Matches shall block shipment confirmation and create a compliance alert requiring manual review.

---

### Module 8: Returns Management (FR-059 – FR-063)

**FR-059 — RMA Issuance**  
The system shall allow shippers to issue a Return Merchandise Authorization (RMA) for delivered shipments within a configurable return window (default 30 days). RMA issuance requires: order reference, return reason, and item condition declaration.

**FR-060 — Return Label Generation**  
Upon RMA issuance, the system shall generate a pre-paid return shipping label and email it to the consignee. The return shipment shall be created automatically with the carrier allocated by the shipper's return routing rules.

**FR-061 — Reverse Logistics Tracking**  
The return shipment shall be tracked through the same tracking pipeline as forward shipments, with a `return_of` reference linking it to the original shipment. All tracking events shall be visible in both the shipper portal and the consignee tracking page.

**FR-062 — Automated Refund Trigger**  
When a return shipment reaches `Delivered` state at the returns warehouse, the system shall emit `return.received.v1`. Downstream financial systems subscribing to this event shall initiate the refund workflow. The system shall not process refunds directly.

**FR-063 — Returns Analytics**  
The system shall report return rates by product category, carrier, lane, and return reason. The analytics module shall compute average return transit time and return label usage rate.

---

### Module 9: Analytics and Reporting (FR-064 – FR-068)

**FR-064 — Carrier Performance Dashboard**  
The system shall provide a real-time dashboard showing per-carrier KPIs: on-time pickup rate, on-time delivery rate (by SLA class), exception rate, damage rate, and average transit time by lane. Data shall refresh every 15 minutes.

**FR-065 — Delivery Performance Reporting**  
The system shall generate scheduled reports (daily, weekly, monthly) covering: total shipments by status, first-attempt delivery success rate, redelivery rate, and average delivery attempts per shipment. Reports shall be exportable as CSV and PDF.

**FR-066 — Exception Report**  
The system shall provide an exception analytics report showing: exception volume by type, average detection-to-resolution time, SLA breach rate by severity, and top 10 exception root causes. Drill-down to individual shipment exceptions shall be available.

**FR-067 — SLA Compliance Report**  
The system shall generate SLA compliance reports by shipper account, showing: shipments within SLA, shipments in breach, breach root-cause distribution (carrier delay, weather, address issue, customs), and financial impact.

**FR-068 — Custom Report Builder**  
The system shall provide an analytics API allowing operations managers to define custom queries over shipment, event, and exception data filtered by date range, carrier, lane, shipper, and service level. Results shall be paginated and exportable.

---

### Module 10: Notifications (FR-069 – FR-072)

**FR-069 — SMS Notifications**  
The system shall send SMS notifications to consignees (and optionally shippers) at configurable lifecycle milestones: shipment confirmed, out for delivery, delivery attempted, delivered, exception raised. SMS shall be dispatched via a configurable SMS gateway (Twilio, AWS SNS). Delivery receipts shall be stored.

**FR-070 — Push Notifications**  
The system shall send push notifications to consignees who have installed the carrier or shipper mobile app. Push notifications shall use FCM (Android) and APNs (iOS). Notification payloads shall include a deep-link to the tracking page.

**FR-071 — Webhook Notifications**  
The system shall dispatch webhook POST requests to shipper-registered endpoints for every shipment event. Webhooks shall include a HMAC-SHA256 signature in the `X-Logistics-Signature` header. Failed deliveries shall be retried per the retry policy (FR-073). Shipper must acknowledge with HTTP 2xx within 10 seconds.

**FR-072 — Email Notifications**  
The system shall send transactional emails to shippers and consignees at key milestones: shipment confirmed (with label), out for delivery (with tracking link), delivered (with POD link), and exception raised (with action required). Email templates shall be configurable per shipper brand.

---

### Module 11: API and Integrations (FR-073 – FR-077)

**FR-073 — REST API**  
The system shall expose a versioned REST API (v1) conforming to OpenAPI 3.1 specification. All mutating endpoints shall require Bearer token authentication (JWT) and the `Idempotency-Key` header. Responses shall use `application/json` with consistent error envelope (`code`, `message`, `details`, `trace_id`).

**FR-074 — Webhook Management API**  
The system shall provide CRUD endpoints for webhook endpoint registration: `POST /webhooks`, `GET /webhooks`, `PUT /webhooks/{id}`, `DELETE /webhooks/{id}`. Each registration includes: URL, secret, active event types, and retry configuration.

**FR-075 — Carrier API Abstraction Layer**  
All carrier-specific API calls shall be encapsulated within carrier adapters. The domain layer shall depend only on the `CarrierAdapter` interface; adapter implementations are injected at runtime. New carriers shall be addable without changes to domain services.

**FR-076 — E-Commerce Platform Connectors**  
The system shall provide pre-built integration connectors for Shopify, WooCommerce, and Magento that: automatically create shipments from orders, update order fulfilment status on delivery, and surface tracking links in order confirmation emails.

**FR-077 — ERP / WMS Integration Support**  
The system shall support EDI (EDIFACT 214) and API-based integration with warehouse management systems and ERPs for: inbound shipment manifests, inventory-level booking, and fulfilment status synchronisation.

---

## Non-Functional Requirements

| ID | Category | Requirement | Target | Measurement |
|---|---|---|---|---|
| NFR-001 | Availability | Platform availability | 99.9 % | Rolling 30-day uptime |
| NFR-002 | Latency | P95 scan-to-tracking-visibility | < 30 seconds | Rolling 24 h |
| NFR-003 | Latency | P95 API response time (read) | < 200 ms | Rolling 1 h |
| NFR-004 | Latency | P95 API response time (write) | < 500 ms | Rolling 1 h |
| NFR-005 | Latency | P95 carrier API round-trip | < 2 seconds | Rolling 1 h |
| NFR-006 | Latency | P95 outbox commit-to-publish | < 5 seconds | Rolling 1 h |
| NFR-007 | Latency | GPS telemetry ingest lag | < 60 seconds | Rolling 1 h |
| NFR-008 | Latency | P95 exception-detection-to-notification | < 3 minutes | Rolling 24 h |
| NFR-009 | Throughput | Peak event ingest rate | 10,000 events/s | Sustained 5 min |
| NFR-010 | Throughput | API requests per second | 5,000 req/s | Sustained 5 min |
| NFR-011 | Accuracy | GPS location accuracy | ≤ 50 metres | Median across all pings |
| NFR-012 | Accuracy | EDD prediction accuracy | ≥ 85 % within ±1 day | Rolling 30-day cohort |
| NFR-013 | Scalability | Horizontal scale-out | Zero-downtime scaling in < 5 min | Load test verified |
| NFR-014 | Durability | Event log durability | No data loss on single node failure | Kafka RF=3, acks=all |
| NFR-015 | Security | Authentication | JWT RS256, 1-hour token TTL | All endpoints |
| NFR-016 | Security | Data encryption in transit | TLS 1.3 minimum | All API and broker traffic |
| NFR-017 | Security | Data encryption at rest | AES-256 for S3 and RDS | Storage layer |
| NFR-018 | Security | PII anonymisation | Driver location anonymised > 500 m | Location sharing feature |
| NFR-019 | Compliance | GDPR right to erasure | PII erasable within 30 days of request | Data deletion workflow |
| NFR-020 | Compliance | Audit log retention | 7 years for financial and customs events | Immutable log store |
| NFR-021 | Reliability | Idempotency | Duplicate API calls produce no side-effects | All mutating endpoints |
| NFR-022 | Reliability | At-least-once delivery | Events delivered at least once to all consumers | Kafka + consumer ACK |
| NFR-023 | Reliability | DLQ redrive success | > 99 % within 4 hours | Daily measurement |
| NFR-024 | Observability | Distributed tracing | 100 % of requests traced | OpenTelemetry |
| NFR-025 | Observability | Structured logging | JSON logs with `trace_id`, `span_id`, `tenant_id` | All services |

---

## Scope and Phasing

| Feature Area | MVP (Phase 1) | Phase 2 | Phase 3 |
|---|---|---|---|
| Shipment CRUD (FR-001–009) | ✅ Full | — | — |
| Carrier Integration — FedEx, UPS | ✅ Full | — | — |
| Carrier Integration — DHL, USPS | ✅ Full | — | — |
| Local Carrier Plug-in Framework (FR-015) | ⬜ Partial (interface only) | ✅ Full + 2 local carriers | — |
| Carrier Rate Shopping (FR-018) | ⬜ Not in scope | ✅ Full | — |
| Tracking Event Ingestion (FR-021) | ✅ Polling + manual | ✅ + Carrier webhooks | — |
| Public Tracking Page (FR-023) | ✅ Static refresh | ✅ SSE live updates | — |
| GPS Telemetry (FR-024–025) | ✅ Ingest + store | — | — |
| EDD Calculation (FR-026) | ⬜ Rule-based P50 | ✅ ML model | — |
| Live Driver Location Sharing (FR-029) | ⬜ Not in scope | ✅ Full | — |
| Route Optimisation (FR-031) | ✅ Basic nearest-neighbour | ✅ TSP + traffic | — |
| POD — Signature + Photo (FR-039–040) | ✅ Full | — | — |
| POD — OTP Verification (FR-041) | ⬜ Not in scope | ✅ Full | — |
| Offline POD (FR-044) | ⬜ Not in scope | ✅ Full | — |
| Exception Detection (FR-046) | ✅ Rule-based | — | — |
| Exception Escalation (FR-049) | ⬜ Email only | ✅ Multi-channel | — |
| Customs — Declarations (FR-053) | ✅ CN22/CN23 | ✅ Full commercial invoice | — |
| Customs — ADR/IATA (FR-056) | ⬜ Not in scope | ✅ Full | — |
| Sanctions Screening (FR-058) | ⬜ Not in scope | ⬜ Not in scope | ✅ Full |
| Returns — RMA + Label (FR-059–060) | ✅ Full | — | — |
| Returns — Reverse Tracking (FR-061) | ⬜ Not in scope | ✅ Full | — |
| SMS + Email Notifications (FR-069, FR-072) | ✅ Full | — | — |
| Push Notifications (FR-070) | ⬜ Not in scope | ✅ Full | — |
| Webhooks (FR-071) | ✅ Full | — | — |
| Carrier Performance Dashboard (FR-064) | ⬜ Basic table | ✅ Full dashboard | — |
| Custom Report Builder (FR-068) | ⬜ Not in scope | ⬜ Not in scope | ✅ Full |
| E-Commerce Connectors (FR-076) | ⬜ Not in scope | ✅ Shopify | ✅ WooCommerce + Magento |
| ERP/WMS Integration (FR-077) | ⬜ Not in scope | ⬜ Not in scope | ✅ Full |

---

## Constraints and Assumptions

### Constraints

1. **Carrier API rate limits** — FedEx, UPS, and DHL impose rate limits on their APIs (typically 100–500 req/min per credential). The integration layer must implement throttling, credential rotation, and back-pressure mechanisms.
2. **GDPR and data residency** — Personal data (consignee name, address, phone) for EU shipments must be stored in EU-region infrastructure. The platform must support multi-region data isolation.
3. **Driver device constraints** — Driver mobile devices may run Android 8+ or iOS 14+. The driver app must function on 3G networks and in areas with intermittent connectivity.
4. **Carrier data latency** — Carriers that expose only polling APIs (USPS) will have a minimum tracking update latency of their polling interval (typically 15–30 min). The system must accurately represent polling-derived data freshness to end-users.
5. **Label format dependency** — Carrier label formats (ZPL, PDF) are carrier-controlled. Changes to carrier label specifications require adapter updates; the system cannot generate labels without a valid carrier API credential.
6. **Third-party geocoding dependency** — Address normalisation and validation depend on a third-party geocoding API (Google Maps Platform or HERE). Service outages will degrade address validation; the system must handle degraded mode gracefully.

### Assumptions

1. Each tenant (shipper account) has pre-established carrier API credentials that are provisioned into the platform before shipment creation.
2. The platform operates within a single cloud provider (AWS) for Phase 1 and Phase 2, with multi-region capability introduced in Phase 3.
3. Customs regulation data (duty rates, restricted items by HS code) is sourced from a licensed third-party tariff database and updated weekly.
4. The driver mobile app is developed separately (by the mobile team) and consumes the BFF API defined in FR-034.
5. Financial settlement (invoicing, refunds, carrier debits) is handled by a separate billing service; this platform emits events that trigger billing workflows.
6. Shipment weight and dimensions are declared by the shipper; volume-weight discrepancy disputes with carriers are resolved outside this platform.
7. SMS and push notification delivery SLAs are governed by the respective gateway providers (Twilio, FCM, APNs) and are outside platform control.

---

## Requirement Coverage Matrix

| Module | Functional Requirements | NFRs Applicable | Phase 1 Coverage |
|---|---|---|---|
| Shipment Management | FR-001 – FR-010 | NFR-001–004, NFR-015–017, NFR-021 | 10/10 |
| Carrier Integration | FR-011 – FR-020 | NFR-001, NFR-005, NFR-009, NFR-022 | 7/10 (rate shopping, plug-in, capacity: Phase 2) |
| Real-Time Tracking | FR-021 – FR-030 | NFR-002, NFR-007, NFR-011–012 | 7/10 (live sharing, ML EDD: Phase 2) |
| Last-Mile Delivery | FR-031 – FR-038 | NFR-002, NFR-011, NFR-018 | 5/8 (offline, OTP, prefs: Phase 2) |
| Proof of Delivery | FR-039 – FR-045 | NFR-016–017, NFR-020 | 4/7 (OTP, offline, disputes: Phase 2) |
| Exception Management | FR-046 – FR-052 | NFR-008, NFR-024–025 | 4/7 (multi-channel escalation, claims: Phase 2) |
| Customs & Compliance | FR-053 – FR-058 | NFR-019–020 | 3/6 (ADR, sanctions: Phase 2/3) |
| Returns Management | FR-059 – FR-063 | NFR-001, NFR-021 | 2/5 (reverse tracking, analytics: Phase 2) |
| Analytics & Reporting | FR-064 – FR-068 | NFR-003, NFR-013 | 2/5 (basic only; full dashboards Phase 2/3) |
| Notifications | FR-069 – FR-072 | NFR-001, NFR-009 | 3/4 (push: Phase 2) |
| API & Integrations | FR-073 – FR-077 | NFR-015–016, NFR-021, NFR-024 | 3/5 (connectors, ERP: Phase 2/3) |
