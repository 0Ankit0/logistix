# Implementation Playbook

This playbook defines the phased rollout plan for the Logistics Tracking System, covering 24 weeks from initial database setup to enterprise EDI integration. Each phase has explicit entry criteria, deliverables, and validation gates before the next phase begins.

---

## Phase 1: MVP — Core Shipment Management + Basic Tracking (Weeks 1–8)

**Goal:** A production-grade core that can create shipments, book with two carriers (FedEx + UPS), ingest GPS data, and show basic delivery status to customers.

**Entry criteria:** Dev environment Docker Compose working; PostgreSQL schema designed and reviewed; TimescaleDB provisioned.

### Week 1–2: Database Schema + Core APIs

- [ ] Create Flyway migration `V001__create_shipments_table.sql` with all shipment fields
- [ ] Create Flyway migration `V002__create_tracking_events_table.sql`
- [ ] Create Flyway migration `V003__create_carrier_allocations_table.sql`
- [ ] Create Flyway migration `V004__create_outbox_table.sql`
- [ ] Implement `POST /v1/shipments` — create shipment with address validation
- [ ] Implement `GET /v1/shipments/{id}` — fetch shipment by ID
- [ ] Implement `GET /v1/track/{trackingNumber}` — public tracking endpoint (no auth)
- [ ] Implement shipment state machine (Draft → Confirmed → PickupScheduled)
- [ ] Deploy Kong API Gateway with JWT plugin to staging
- [ ] Validation gate: `POST /v1/shipments` returns 201 with shipment ID; `GET /v1/track/` returns 200 with status

### Week 3–4: FedEx + UPS Carrier Adapters

- [ ] Register for FedEx Developer Portal sandbox account
- [ ] Register for UPS Developer Kit sandbox account
- [ ] Implement `ICarrierAdapter` interface (TypeScript)
- [ ] Implement `FedExAdapter`: `book()`, `getLabel()`, `getTrackingStatus()`
- [ ] Implement `UPSAdapter`: `book()`, `getLabel()`, `getTrackingStatus()`
- [ ] Configure Resilience4j circuit breakers for FedEx and UPS
- [ ] Write unit tests for both adapters against WireMock stubs
- [ ] Write integration tests against FedEx sandbox
- [ ] Write integration tests against UPS sandbox
- [ ] Implement `CarrierSelectionService` with basic scoring (price + transit time)
- [ ] Validation gate: Can book a shipment end-to-end in staging with FedEx sandbox; label PDF retrievable from S3

### Week 5–6: GPS Tracking Pipeline

- [ ] Provision TimescaleDB with `gps_breadcrumbs` hypertable
- [ ] Apply `chunk_time_interval = 1 hour` and `retention_policy = 90 days`
- [ ] Implement `POST /v1/gps/update` ingest endpoint in `gps-processing-service` (Go)
- [ ] Implement coordinate validation (lat/lon range checks)
- [ ] Implement deduplication (10m + 5s rule) backed by Redis
- [ ] Implement outlier filter (>500 km/h speed rejection)
- [ ] Implement buffered batch writer (100 breadcrumbs or 500ms flush)
- [ ] Deploy Kafka topic `logistics.gps.location.v1` with 10 partitions
- [ ] Implement Redis vehicle position cache with 5-min TTL
- [ ] Deploy `gps-processing-service` with 5 replicas + HPA (CPU-based)
- [ ] Validation gate: GPS pipeline processes 1,000 events/second in staging; P99 write latency < 100ms

### Week 7–8: Delivery Attempts + POD Capture

- [ ] Implement `POST /v1/shipments/{id}/delivery-attempts` — record attempt outcome
- [ ] Implement proof-of-delivery upload: `POST /v1/shipments/{id}/pod` (multipart, S3 upload)
- [ ] Implement shipment state transitions: InTransit → OutForDelivery → Delivered
- [ ] Implement failed delivery attempt → reschedule or Exception state
- [ ] Implement customer notification on delivery: email via SES + SMS via SNS
- [ ] Add `shipment_sla_breach_total` Prometheus metric and alert rule
- [ ] Validation gate: Full shipment lifecycle test in staging (create → book → GPS pings → deliver → POD uploaded)

---

## Phase 2: Advanced Features (Weeks 9–16)

**Goal:** Route optimisation, exception management, customs support, returns, and analytics dashboard.

**Entry criteria:** Phase 1 MVP passing all validation gates in staging; load test baseline established.

### Week 9–10: Route Optimization Service

- [ ] Set up Python 3.12 service skeleton with FastAPI
- [ ] Integrate Google OR-Tools for vehicle routing problem (VRP) solver
- [ ] Implement `POST /v1/routes/optimize` — input: list of delivery stops + vehicle constraints
- [ ] Implement real-time re-optimization on traffic updates (Kafka consumer for GPS events)
- [ ] Integrate HERE Maps or Google Maps Distance Matrix API for road distances
- [ ] Implement ETA recalculation: consume `logistics.gps.location.v1`, update ETA in Redis
- [ ] Expose ETA via `GET /v1/shipments/{id}/eta`
- [ ] Validation gate: Route optimization produces a solution for 50 stops in < 5 seconds

### Week 11–12: Exception Management + Notifications

- [ ] Implement `ExceptionDetectionService`: consumes state change events, evaluates SLA breach rules
- [ ] Implement exception types: MISSED_PICKUP, DELIVERY_FAILED, ADDRESS_UNDELIVERABLE, WEATHER_DELAY, CUSTOMS_HOLD
- [ ] Implement `POST /v1/shipments/{id}/exceptions` — manually raise exception
- [ ] Implement `PATCH /v1/shipments/{id}/exceptions/{exceptionId}` — resolve exception
- [ ] Implement SLA breach detection cron (every 5 minutes): compare `committed_delivery_date` to current state
- [ ] Implement notification templates: SMS (160 chars), email (HTML), push (JSON payload)
- [ ] Deploy `notification-service` with Kafka consumer for `logistics.notification.outbound.v1`
- [ ] Validation gate: SLA breach detected within 5 minutes of breach; customer notified within 3 minutes

### Week 13–14: Customs Declarations + Hazmat Support

- [ ] Implement `customs-service` with HS code lookup and duty calculation rules
- [ ] Implement `POST /v1/shipments/{id}/customs-declaration`
- [ ] Integrate with customs broker API (for cross-border shipments)
- [ ] Implement hazmat validation rules: ADR/IATA DGR classifications
- [ ] Add dangerous goods codes to shipment creation request schema
- [ ] Implement hazmat label generation (overlays on carrier label)
- [ ] Add customs-related exception types: CUSTOMS_HOLD, DUTY_UNPAID, DOCUMENT_MISSING
- [ ] Validation gate: Cross-border test shipment to UK generates correct customs declaration; hazmat shipment blocked without DG class

### Week 15–16: Returns Management + Analytics Dashboard

- [ ] Implement `returns-service`: `POST /v1/returns` — create return request linked to original shipment
- [ ] Implement return label generation (reuses carrier adapter `getLabel()` with return flag)
- [ ] Implement return tracking pipeline (same GPS ingest; separate return state machine)
- [ ] Implement `analytics-service`: index shipments + events to Elasticsearch
- [ ] Implement Grafana dashboards: delivery success rate by carrier, SLA compliance rate, exception aging
- [ ] Implement `GET /v1/analytics/carrier-performance` — aggregated carrier KPIs
- [ ] Validation gate: Analytics dashboard shows data within 5 minutes of shipment events; return shipment tracked end-to-end

---

## Phase 3: Enterprise Features (Weeks 17–24)

**Goal:** Multi-region deployment, ML-based EDD, white-label portal, EDI integration.

**Entry criteria:** Phase 2 complete; load test shows GPS pipeline at 10,000 events/second with P99 < 100ms.

### Week 17–18: Multi-Region Deployment

- [ ] Provision `eu-west-1` EKS cluster with identical configuration to `us-east-1`
- [ ] Configure Route53 GeoDNS: EU traffic → `eu-west-1`, APAC traffic → `ap-southeast-1`
- [ ] Deploy all services to `eu-west-1` with EU-specific ConfigMaps (GDPR PII isolation)
- [ ] Configure Kafka MirrorMaker2 for cross-region event replication (PII redaction transform)
- [ ] Configure CloudNativePG logical replication for analytics read replica in `eu-west-1`
- [ ] Configure S3 cross-region replication for labels (US buckets only; EU buckets GDPR-isolated)
- [ ] Run DR drill: simulate `us-east-1` failure; validate traffic shifts to `eu-west-1` within RTO=4hrs
- [ ] Validation gate: Shipment created via EU endpoint; consignee PII confirmed absent from US PostgreSQL

### Week 19–20: Advanced Analytics + ML-Based EDD

- [ ] Train XGBoost model for estimated delivery date (EDD) prediction using historical shipment data
- [ ] Features: carrier, service class, origin–destination pair, day of week, weather signal, historical carrier performance
- [ ] Deploy model as a FastAPI endpoint: `POST /v1/edd/predict`
- [ ] Replace static ETA calculation with ML EDD in shipment creation response
- [ ] Implement model retraining pipeline: weekly batch job reads last 90 days of delivery outcomes
- [ ] Implement A/B testing: 20% of requests use ML EDD vs 80% rule-based; compare RMSE
- [ ] Validation gate: ML EDD RMSE < 4 hours for standard domestic shipments

### Week 21–22: White-Label Tracking Portal

- [ ] Build React SPA with Tailwind CSS for customer-facing tracking page
- [ ] Implement tenant-scoped theming: logo, primary colour, font from tenant config API
- [ ] Expose at custom domain: `track.{tenantDomain}.com` via CloudFlare custom hostnames
- [ ] Implement real-time GPS map (Mapbox GL JS): shows vehicle position updating every 30s
- [ ] Implement delivery ETA widget pulling from `/v1/shipments/{id}/eta`
- [ ] Implement POD display: signature image + photo from S3 pre-signed URL
- [ ] Validation gate: White-label portal loads in < 2s (P95, CDN-cached); real-time map updates within 60s of GPS ping

### Week 23–24: EDI Integration for Enterprise Customers

- [ ] Implement EDI X12 214 (Transportation Carrier Shipment Status Message) inbound parser
- [ ] Implement EDI X12 856 (Advance Ship Notice) inbound → creates shipments in bulk
- [ ] Implement EDI X12 997 (Functional Acknowledgement) outbound
- [ ] Implement AS2 transport layer for EDI file exchange (Mendelson AS2 or similar)
- [ ] Deploy enterprise customer VPN/Direct Connect configuration
- [ ] Validation gate: Bulk EDI file with 1,000 ASNs processed within 2 minutes; 214 status updates reflected in tracking within 60s

---

## Carrier Integration Onboarding Process

Follow these eight steps for every new carrier added after MVP:

**Step 1: Register for carrier developer portal**
- FedEx: [developer.fedex.com](https://developer.fedex.com) → create app → obtain `client_id` and `client_secret`
- UPS: [developer.ups.com](https://developer.ups.com) → register → obtain `client_id` and access key
- DHL: [developer.dhl.com](https://developer.dhl.com) → create account → obtain API key

**Step 2: Obtain sandbox credentials**
Store credentials in AWS Secrets Manager under path `logistics/{env}/carriers/{carrierId}/credentials`. Never commit credentials to git.

**Step 3: Implement `ICarrierAdapter`**
Create `services/carrier-integration-service/src/adapters/{carrierId}-adapter.ts`. Implement all five methods. Map carrier-specific status codes to internal `TrackingEventCode` enum in `carrier-status-mapper.ts`.

**Step 4: Write adapter unit tests with carrier sandbox**
Create `__tests__/{carrierId}-adapter.spec.ts`. Use WireMock for unit tests; integration tests hit the real sandbox. Minimum 80% branch coverage.

**Step 5: Configure circuit breaker thresholds**
Add circuit breaker entry in `resilience4j.yaml` for the new carrier. Default: `failureRateThreshold=50`, `waitDurationInOpenState=60s`. Adjust based on observed sandbox reliability.

**Step 6: UAT in staging with test shipments**
Create 10 test shipments in staging using the new carrier adapter. Verify: booking succeeds, label generated, tracking status polled successfully, webhook received (if carrier supports it).

**Step 7: Production go-live with shadow mode (dual-write)**
Set carrier `active=false` and `shadowMode=true` in carrier config. Shadow mode books with both the new carrier and the primary carrier; compares results but only uses primary. Monitor for 48 hours.

**Step 8: Monitor error rates for 48 hours before full cutover**
Watch `carrier_api_request_duration_seconds{carrier_id="{carrierId}",status="error"}` in Grafana. If error rate < 1% over 48 hours with no circuit breaker trips, set `active=true` and `shadowMode=false`.

---

## GPS Tracking Pipeline Setup

**Step 1: Provision TimescaleDB**
```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE TABLE gps_breadcrumbs (
    id           UUID        NOT NULL DEFAULT gen_random_uuid(),
    vehicle_id   TEXT        NOT NULL,
    tenant_id    UUID        NOT NULL,
    latitude     DOUBLE PRECISION NOT NULL,
    longitude    DOUBLE PRECISION NOT NULL,
    speed_kmh    DOUBLE PRECISION,
    heading_deg  INTEGER,
    recorded_at  TIMESTAMPTZ NOT NULL,
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Step 2: Configure hypertable with 1-hour chunks**
```sql
SELECT create_hypertable('gps_breadcrumbs', 'recorded_at',
    chunk_time_interval => INTERVAL '1 hour');
```

**Step 3: Set compression policy**
```sql
ALTER TABLE gps_breadcrumbs SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'recorded_at DESC',
    timescaledb.compress_segmentby = 'vehicle_id'
);
SELECT add_compression_policy('gps_breadcrumbs', INTERVAL '24 hours');
```

**Step 4: Set retention policy**
```sql
SELECT add_retention_policy('gps_breadcrumbs', INTERVAL '90 days');
```

**Step 5: Deploy GPS ingest service with 5 replicas**
```bash
kubectl apply -f k8s/gps-processing-service/deployment.yaml
kubectl scale deployment gps-processing-service --replicas=5 -n logistics-prod
```

**Step 6: Configure Redis GPS cache with 5-min TTL**
No schema change needed. Key format documented in code guidelines. Verify cache hit rate in Grafana (`redis_keyspace_hits_total` / total lookups > 90% for active vehicles).

**Step 7: Deploy Kafka topic with 10 partitions**
```bash
kafka-topics.sh --create \
  --topic logistics.gps.location.v1 \
  --partitions 10 \
  --replication-factor 3 \
  --config retention.ms=86400000 \
  --config min.insync.replicas=2 \
  --bootstrap-server $KAFKA_BROKERS
```

**Step 8: Deploy GPS consumer group with lag monitoring**
```bash
kubectl apply -f k8s/tracking-service/deployment.yaml
# Verify consumer group is assigned to all 10 partitions
kafka-consumer-groups.sh --describe --group tracking-service-consumer \
  --bootstrap-server $KAFKA_BROKERS
```
Configure alert in Alertmanager: fire if `kafka_consumer_group_lag{group="tracking-service-consumer"}` > 50,000 for > 2 minutes.

---

## SLA Monitoring Setup

### Prometheus Metrics

| Metric | Collection Method | Notes |
|---|---|---|
| `shipment_sla_breach_total` | Incremented by SLA check cron job | Labels: `carrier_id`, `sla_class`, `breach_type` |
| `delivery_attempt_outcome_total` | Incremented by `delivery-attempt-handler` | Labels: `carrier_id`, `outcome` (delivered/failed/rescheduled) |
| `exception_age_seconds` | Gauge updated by exception monitor | Labels: `exception_type`, `carrier_id` |
| `sla_compliance_rate` | Computed gauge = 1 - (breach_total / committed_total) | Evaluated per hour |

### SLA Check Cron Job

Runs every 5 minutes via Kubernetes `CronJob`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: sla-breach-detector
  namespace: logistics-prod
spec:
  schedule: "*/5 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: sla-checker
              image: logistics/sla-checker:latest
              command: ["./sla-checker", "--publish-events"]
```

The job queries PostgreSQL for all shipments in non-terminal states where `committed_delivery_date < NOW()`, increments `shipment_sla_breach_total`, and publishes `SLABreachDetected` events to `logistics.shipment.exception.v1`.

### Grafana Dashboards

| Dashboard | Key Panels | Refresh |
|---|---|---|
| SLA Compliance | SLA compliance rate by carrier, breach count by hour, exception aging heatmap | 1 min |
| Carrier Performance | Booking success rate, label generation latency, tracking status polling errors | 5 min |
| GPS Pipeline | Consumer lag, events/second by partition, write latency percentiles | 30 sec |
| Exception Management | Open exceptions by type and age, resolution time P50/P95, escalation rate | 1 min |

### PagerDuty Alert Rules

| Alert Name | Condition | Severity | Response Time |
|---|---|---|---|
| `SLABreachRateHigh` | `sla_compliance_rate < 0.95` for 5 min | SEV-1 | 15 min |
| `GPSPipelineLagCritical` | Consumer lag > 300,000 events (30s at 10k/s) | SEV-1 | 15 min |
| `GPSPipelineLagWarning` | Consumer lag > 50,000 events | SEV-2 | 1 hour |
| `CarrierCircuitBreakerOpen` | Any carrier circuit breaker in OPEN state for > 2 min | SEV-2 | 1 hour |
| `ExceptionAgeBreached` | Any exception open > 4 hours without owner assigned | SEV-2 | 1 hour |
| `DLQDepthHigh` | DLQ message count > 1,000 | SEV-3 | Next biz day |

---

## Database Migration Runbook

1. **Before migration:** Take a PostgreSQL snapshot via CloudNativePG: `kubectl cnpg backup postgresql-primary -n infra`.
2. **Verify migration script:** Run `flyway validate` against staging first. Zero tolerance for checksum mismatches.
3. **Apply migration:** `flyway migrate` runs automatically on service startup. For large migrations (>1M rows), run manually during low-traffic window.
4. **Monitor:** Watch `pg_stat_activity` for long-running transactions during migration. Alert if any migration takes > 5 minutes.
5. **Rollback:** Flyway does not auto-rollback. Rollback migration = new Flyway migration that reverses the change (not undo script). Restore from snapshot only for data-loss scenarios.

---

## Rollback Procedures

### Service Rollback (Kubernetes)
```bash
# Roll back to previous deployment revision
kubectl rollout undo deployment/{service-name} -n logistics-prod

# Roll back to a specific revision
kubectl rollout undo deployment/{service-name} --to-revision=3 -n logistics-prod

# Verify rollback
kubectl rollout status deployment/{service-name} -n logistics-prod
```

### Feature Flag Rollback
All new features are guarded by feature flags in LaunchDarkly. To disable a feature without a deployment:
```bash
# Via LaunchDarkly API
curl -X PATCH https://app.launchdarkly.com/api/v2/flags/logistics/{flagKey} \
  -H "Authorization: $LD_API_KEY" \
  -d '[{"op":"replace","path":"/environments/production/on","value":false}]'
```

### Database Rollback
Only performed when data integrity is compromised. Requires approval from two senior engineers:
1. Stop the affected service: `kubectl scale deployment/{service} --replicas=0`
2. Restore PostgreSQL from snapshot: `kubectl cnpg restore postgresql-primary --backup=backup-{timestamp} -n infra`
3. Replay Kafka events from the snapshot timestamp to now using event replay tooling.
4. Restart the service with the previous image version.
5. Validate data consistency via integrity check queries.

