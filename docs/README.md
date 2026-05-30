# Logistics Tracking System

A production-grade, multi-carrier shipment tracking platform built around an event-driven architecture. The system provides end-to-end visibility across the entire shipment lifecycle — from order creation through last-mile delivery — with support for carrier integrations, GPS telemetry, proof of delivery, exception management, customs compliance, and reverse logistics.

## Domain Description

Modern logistics operations span multiple carriers, geographies, and regulatory regimes. Shippers demand real-time visibility; consignees expect accurate ETAs and proactive exception alerts; operations managers require SLA adherence dashboards and exception escalation workflows; compliance officers need customs documentation and audit trails. This platform unifies those concerns under a single tracking domain backed by event sourcing, a canonical shipment state machine, and carrier-agnostic integration adapters.

**Core domain concepts:**
- **Shipment** — the primary aggregate: identifies cargo, route, carrier, SLA class, and lifecycle state.
- **Tracking Event** — immutable custody record emitted at every scan, GPS ping, or status change.
- **Leg** — a single transport segment (origin → hub, hub → hub, hub → destination).
- **Carrier Allocation** — binding of a shipment to a specific carrier and service level.
- **Proof of Delivery (POD)** — cryptographically signed collection of delivery artifacts (signature, photo, OTP).
- **Exception** — any deviation from the expected transit plan, requiring an owner and resolution ETA.
- **Return Merchandise Authorization (RMA)** — authorisation record for reverse-logistics flow.

## Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| API Gateway | Kong / AWS API Gateway | Rate limiting, JWT validation, mTLS for carrier callbacks |
| Backend Services | Go (core domain), Node.js (driver app BFF) | Hexagonal architecture; domain logic isolated from infrastructure |
| Event Broker | Apache Kafka (MSK) | Topic-per-event-type; 7-day retention; compacted state topics |
| Database | PostgreSQL 15 (OLTP) + TimescaleDB (telemetry) | Row-level tenant isolation; hypertable partitioning on `recorded_at` |
| Cache | Redis Cluster | Shipment state hot-path, idempotency key store, rate-limit counters |
| Object Storage | AWS S3 | POD photos, customs documents, audit exports |
| Search | OpenSearch | Full-text shipment search, exception dashboards |
| GPS / Telemetry | MQTT broker (EMQX) → Kafka bridge | Driver app publishes location at 30 s cadence |
| CDN / Tracking Page | CloudFront + React SPA | Public tracking portal with SSE for live updates |
| Infrastructure | Terraform + EKS | GitOps via ArgoCD; Helm charts per service |
| Observability | OpenTelemetry → Grafana / Loki / Tempo | Distributed tracing, structured logs, Prometheus metrics |
| CI/CD | GitHub Actions + Docker | Contract tests (Pact), integration tests in ephemeral namespaces |

## Documentation Structure

Project root artifact: [`traceability-matrix.md`](./traceability-matrix.md) provides cross-phase requirement-to-implementation linkage.


```
Logistics Tracking System/
├── traceability-matrix.md
├── requirements/
│   ├── requirements-document.md   ← Full functional & non-functional requirements
│   └── user-stories.md            ← 40+ user stories with acceptance criteria
├── analysis/
│   ├── actors-and-roles.md        ← Stakeholder map, permissions matrix
│   ├── business-rules.md          ← Invariants, SLA rules, carrier policies
│   └── event-contracts.md         ← CloudEvents schema catalogue
├── high-level-design/
│   ├── architecture-overview.md   ← C4 context + container diagrams
│   ├── system-sequence-diagrams.md← Key flows as sequence diagrams
│   └── data-flow.md               ← Data movement, retention, privacy
├── detailed-design/
│   ├── api-specification.md       ← OpenAPI 3.1 endpoint catalogue
│   ├── schema-definitions.md      ← DB schema, Kafka message schemas
│   └── state-machine.md           ← Full FSM with guards and actions
├── infrastructure/
│   ├── deployment-architecture.md ← EKS topology, scaling policies
│   ├── slo-and-alerting.md        ← SLO budget, alert rules, runbooks
│   └── disaster-recovery.md       ← RTO/RPO targets, DR playbook
├── edge-cases/
│   ├── exception-playbooks.md     ← Detection, fallback, escalation
│   └── failure-scenarios.md       ← Chaos experiments, degraded-mode behaviour
└── implementation/
    └── implementation-playbook.md ← Sprint plan, ADRs, cutover checklist
```

## Key Features

- **Canonical shipment lifecycle** with 11 explicit states and guarded transition rules — no direct jumps between non-adjacent states.
- **Multi-carrier integration adapters** for FedEx, UPS, DHL, USPS, and pluggable local carrier connectors via a unified carrier API contract.
- **Real-time GPS telemetry pipeline** ingesting driver location at 30-second cadence with breadcrumb trail storage and geofence-triggered events.
- **Machine-learning ETA engine** recalculating estimated delivery dates on every custody scan using historical lane performance data.
- **Last-mile route optimisation** with Travelling Salesman Problem (TSP) solver, traffic-aware re-routing, and dynamic stop insertion.
- **Proof of Delivery (POD)** capturing electronic signature, geo-stamped photo, and OTP verification with offline-first mobile support.
- **Exception management workflow** with auto-detection rules, severity classification, SLA-breach escalation, and resolution tracking.
- **Customs & compliance module** handling HS-code classification, customs declarations, ADR dangerous-goods manifests, and IATA compliance checks.
- **Returns / reverse-logistics** with RMA issuance, carrier label generation, and automated refund trigger on POD receipt.
- **Event-driven notification engine** dispatching SMS, push, email, and webhooks with deduplication and delivery receipts.
- **End-to-end event sourcing** — every state change is a first-class domain event; full audit trail is reconstructable from the event log.
- **Integration retry and idempotency** — transactional outbox, exponential backoff, and consumer-side deduplication at every boundary.
- **Production SLOs and runbooks** — P95 tracking latency < 30 s, 99.9 % platform availability, alerting from SEV-1 to SEV-3 with on-call routing.

## Getting Started

- Review [`traceability-matrix.md`](./traceability-matrix.md) first to navigate requirement-to-implementation coverage across phases.
1. **Read requirements first** — `requirements/requirements-document.md` defines all functional requirements, NFRs, MVP scope, and constraints.
2. **Review user stories** — `requirements/user-stories.md` provides role-based acceptance criteria used to drive feature implementation and QA.
3. **Understand the domain** — `analysis/actors-and-roles.md` maps every stakeholder to permissions; `analysis/business-rules.md` captures invariants that must never be violated.
4. **Study the event contracts** — `analysis/event-contracts.md` is the authoritative schema catalogue; all services produce and consume events conforming to this catalogue.
5. **Architecture overview** — `high-level-design/architecture-overview.md` shows C4 context and container diagrams; start here before touching detailed design.
6. **API and schema** — `detailed-design/api-specification.md` and `detailed-design/schema-definitions.md` are the implementation source of truth for REST endpoints and data models.
7. **State machine** — `detailed-design/state-machine.md` defines every guard, action, and side-effect for shipment lifecycle transitions.
8. **Deploy** — follow `infrastructure/deployment-architecture.md` for cluster topology, then `implementation/implementation-playbook.md` for sprint plan and cutover checklist.
9. **Validate edge cases** — run `edge-cases/` playbooks in staging before production rollout to verify degraded-mode behaviour and chaos recovery.

## End-to-End Event Flow

### Phase 1 — Create and Validate

1. Shipper submits `POST /shipments` with `Idempotency-Key` header.
2. API Gateway validates JWT, enforces rate limit, and forwards to Shipment Service.
3. Shipment Service validates origin/destination addresses, SLA class, weight/dimensions, and regulatory constraints (ADR, IATA).
4. Service writes shipment aggregate to PostgreSQL and inserts outbox record `shipment.created.v1` in the same transaction.
5. Outbox relay worker publishes the event to Kafka topic `logistics.shipments.v1`.
6. Notification service consumes event and dispatches "Shipment confirmed" email/SMS to shipper.

### Phase 2 — Plan and Pickup

7. Planning service consumes `shipment.created.v1`, runs carrier allocation logic, and writes `carrier_allocation` record.
8. Planning service emits `shipment.pickup_scheduled.v1` with assigned driver and pickup window.
9. Driver app receives push notification with pickup task; driver navigates to origin.
10. Driver scans barcode / NFC tag; driver app POSTs scan event with GPS coords.
11. Shipment Service processes scan, transitions state `Confirmed → PickedUp`, emits `shipment.picked_up.v1`.

### Phase 3 — Line-Haul and Hub Progression

12. Hub scanner operator scans inbound manifest; each scan emits `shipment.location_updated.v1` with `location_type=HUB`.
13. ETA service consumes location events, recalculates EDD using lane model, emits `shipment.eta_updated.v1`.
14. Milestone service derives `arrived_at_hub` and `departed_hub` composite events and updates public tracking page.
15. Telemetry pipeline ingests GPS pings from line-haul truck at 30 s cadence; breadcrumbs stored in TimescaleDB.
16. Geofence monitor detects hub arrival zone entry and triggers `shipment.geofence_entered.v1` if scan not received within 10 min.

### Phase 4 — Last-Mile Delivery

17. Route optimiser receives manifest of deliveries for a driver's run; emits `shipment.out_for_delivery.v1` per shipment.
18. Driver app shows optimised stop sequence with live traffic; consignee receives "Out for delivery" notification with 2-hour window.
19. Driver arrives at delivery address; app captures electronic signature + geo-stamped photo.
20. POD submitted; Shipment Service transitions `OutForDelivery → Delivered`, emits `shipment.delivered.v1` with POD artifact IDs.
21. S3 stores signed POD documents; consignee receives delivery confirmation with download link.

### Phase 5 — Exception and Recovery

22. Any failed invariant (missed pickup, customs hold, damage, address issue) triggers `shipment.exception_detected.v1` with reason code and severity.
23. Exception service assigns owner, sets resolution SLA, and sends escalation notification.
24. On resolution, `shipment.exception_resolved.v1` is emitted; state machine resumes the normal path or routes to a terminal fallback.
25. If 3 delivery attempts fail, system automatically transitions to `ReturnedToSender` and initiates reverse-logistics workflow.

### Phase 6 — Closure

26. Terminal events (`delivered`, `returned_to_sender`, `cancelled`, `lost`) trigger settlement pipeline, analytics ingestion, and archival job.
27. Archival job moves shipment aggregate to cold storage after 90 days; event log retained for 7 years per audit requirements.

## Canonical State Machine Summary

| State | Entry Criteria | Allowed Next States | Exit Event | Operational Notes |
|---|---|---|---|---|
| `Draft` | Shipment request created but not committed | `Confirmed`, `Cancelled` | `shipment.confirmed` | No external notifications before confirmation. |
| `Confirmed` | Address validation and capacity check passed | `PickupScheduled`, `Cancelled` | `shipment.pickup_scheduled` | SLA clock starts at confirmation timestamp. |
| `PickupScheduled` | Pickup slot and driver assigned | `PickedUp`, `Exception`, `Cancelled` | `shipment.picked_up` | Missed pickup auto-raises Exception after configurable threshold. |
| `PickedUp` | Driver or hub scan confirms first-mile custody | `InTransit`, `Exception` | `shipment.in_transit` | Chain-of-custody record required; cannot skip to OutForDelivery. |
| `InTransit` | Shipment moving between sort facilities or line-haul | `OutForDelivery`, `Exception`, `Lost` | `shipment.out_for_delivery` | Telemetry gap > 4 h triggers automated Exception. |
| `OutForDelivery` | Last-mile run manifest committed for this shipment | `Delivered`, `Exception`, `ReturnedToSender` | `shipment.delivered` | Max 3 delivery attempts before auto-return; customer contact enforced. |
| `Exception` | Any invariant violation detected (delay, damage, customs, address) | `InTransit`, `OutForDelivery`, `ReturnedToSender`, `Cancelled`, `Lost` | `shipment.exception_resolved` | Owner and resolution ETA mandatory; SLA breach triggers SEV-2 alert. |
| `Delivered` | Proof of delivery accepted and recorded | *(terminal)* | `shipment.closed` | Record is immutable post-delivery; audit annotations only. |
| `ReturnedToSender` | Return workflow completed and RTS scan captured | *(terminal)* | `shipment.closed` | Financial settlement and carrier debit rules apply. |
| `Cancelled` | Shipment cancelled prior to any terminal state | *(terminal)* | `shipment.closed` | Cancellation reason code required; triggers refund if applicable. |
| `Lost` | Investigation concludes cargo is unrecoverable | *(terminal)* | `shipment.closed` | Insurance claims and compliance reporting path triggered automatically. |

## Integration Retry and Idempotency Specification

### Outbox Pattern
Command-handling transactions atomically write the domain aggregate mutation **and** the outbox record in a single database transaction. An outbox relay worker polls for unpublished records and publishes to Kafka with at-least-once semantics, then marks records as published.

### Retry Policy
| Boundary | Strategy | Parameters | Max Elapsed |
|---|---|---|---|
| Outbox relay → Kafka | Exponential backoff + jitter | base=500 ms, factor=2, max=5 min | 30 min |
| Carrier API calls | Exponential backoff + jitter | base=1 s, factor=2, max=60 s | 15 min |
| Webhook delivery | 3 fast + 8 slow retries | fast: 5/15/60 s; slow: 5/15/30/60/120/300/600/1800 s | 8 h |
| Notification dispatch | 3 retries | 30 s fixed | 5 min |

### Deduplication Contract
- **Event publishers:** Every event carries a globally unique `event_id` (UUIDv7) generated at write time.
- **Event consumers:** Before processing, consumers insert `(event_id, consumer_name, processed_at, outcome_hash)` into a dedup table. Duplicate `event_id` values are acknowledged without reprocessing.
- **API idempotency:** All mutating HTTP endpoints require the `Idempotency-Key` header, scoped by `(tenant_id, route, key)`. Duplicate requests within the TTL window (24 h) return the cached response without re-executing business logic.
- **Webhook replay protection:** Signed payloads include `delivery_id`; receivers reject duplicates by checking a sliding-window cache.
- **Replay safety:** Bulk replay jobs attach `replay_batch_id` to events; downstream handlers suppress duplicate notifications, billing triggers, and carrier API calls when `replay_batch_id` is present.

## Monitoring, SLOs, and Alerting

### SLO Targets

| SLO | Target | Measurement Window |
|---|---|---|
| Platform availability | 99.9 % | Rolling 30 days |
| P95 scan-to-tracking-visibility | < 30 seconds | Rolling 24 hours |
| P95 carrier API round-trip | < 2 seconds | Rolling 1 hour |
| P95 commit-to-publish (outbox) | < 5 seconds | Rolling 1 hour |
| P95 exception-detection-to-notification | < 3 minutes | Rolling 24 hours |
| GPS telemetry ingest lag | < 60 seconds | Rolling 1 hour |
| Daily DLQ redrive success rate | > 99 % within 4 hours | Daily |
| POD upload success rate | > 99.5 % | Rolling 7 days |

### Golden Signals Monitored

- **Latency:** event ingest latency, outbox publish latency, API response time (P50/P95/P99).
- **Traffic:** events/s per topic, API req/s per endpoint, GPS pings/s.
- **Errors:** API 5xx rate, Kafka publish error rate, carrier adapter error rate, DLQ depth.
- **Saturation:** broker partition lag per consumer group, DB connection pool utilisation, Redis memory %.

### Alert Severity Policy

| Severity | Trigger Condition | Response Time | Escalation |
|---|---|---|---|
| SEV-1 | Outbox relay stalled > 5 min; broker unavailable; state processor halted; tracking page down | Immediate page | On-call engineer + engineering manager |
| SEV-2 | DLQ depth growing > threshold for 15 min; ETA model stale > 10 min; webhook burst failure; GPS ingest lag > 5 min | 15-minute response | On-call engineer |
| SEV-3 | Schema drift warning; duplicate event spike; non-critical carrier adapter flapping; SLO budget < 20 % remaining | Next business day | Team Slack channel |

### Runbook Requirements
Every alert rule **must** link to: owning team, primary dashboard URL, 5-step triage checklist, mitigation steps, replay/redrive command, and a stakeholder communications template. Runbooks are stored in `infrastructure/slo-and-alerting.md` and reviewed quarterly.

## Documentation Status

- ✅ Traceability coverage is available via [`traceability-matrix.md`](./traceability-matrix.md).
| Document | Status | Last Updated |
|---|---|---|
| `requirements/requirements-document.md` | ✅ Complete — 77 requirements across 11 modules | Current |
| `requirements/user-stories.md` | ✅ Complete — 40+ stories with acceptance criteria | Current |
| `analysis/actors-and-roles.md` | ✅ Complete — stakeholder map and permissions matrix | Current |
| `analysis/business-rules.md` | ✅ Complete — 30+ invariants and SLA rules | Current |
| `analysis/event-contracts.md` | ✅ Complete — CloudEvents schema catalogue | Current |
| `high-level-design/architecture-overview.md` | ✅ Complete — C4 context + container Mermaid diagrams | Current |
| `high-level-design/system-sequence-diagrams.md` | ✅ Complete — 8 key flow sequence diagrams | Current |
| `detailed-design/api-specification.md` | ✅ Complete — OpenAPI 3.1 endpoint catalogue | Current |
| `detailed-design/schema-definitions.md` | ✅ Complete — DB schema and Kafka message schemas | Current |
| `detailed-design/state-machine.md` | ✅ Complete — FSM with guards, actions, side-effects | Current |
| `infrastructure/deployment-architecture.md` | ✅ Complete — EKS topology and scaling policies | Current |
| `infrastructure/slo-and-alerting.md` | ✅ Complete — SLO budgets, alert rules, runbooks | Current |
| `edge-cases/exception-playbooks.md` | ✅ Complete — detection, fallback, escalation | Current |
| `implementation/implementation-playbook.md` | ✅ Complete — sprint plan, ADRs, cutover checklist | Current |
