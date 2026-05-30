# Code Guidelines

## Development Environment Setup

All engineers run the full stack locally using Docker Compose. The compose file brings up every backing service so no cloud credentials are needed for feature development.

### docker-compose.yml (excerpt)

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: logistics
      POSTGRES_PASSWORD: logistics_dev
      POSTGRES_DB: logistics_db
    volumes: ["pg_data:/var/lib/postgresql/data"]

  timescaledb:
    image: timescale/timescaledb:latest-pg16
    ports: ["5433:5432"]
    environment:
      POSTGRES_USER: logistics
      POSTGRES_PASSWORD: logistics_dev
      POSTGRES_DB: gps_db
    volumes: ["tsdb_data:/var/lib/postgresql/data"]

  zookeeper:
    image: confluentinc/cp-zookeeper:7.6.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
    ports: ["2181:2181"]

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    depends_on: [zookeeper]
    ports: ["9092:9092"]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"

  redis:
    image: redis:7.2-alpine
    ports: ["6379:6379"]
    command: redis-server --appendonly yes

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    ports: ["9200:9200"]
    environment:
      discovery.type: single-node
      xpack.security.enabled: "false"
    volumes: ["es_data:/usr/share/elasticsearch/data"]

volumes:
  pg_data:
  tsdb_data:
  es_data:
```

### Starting the local environment

```bash
# Start all backing services
docker compose up -d

# Run database migrations (Flyway)
./gradlew flywayMigrate -Dflyway.url=jdbc:postgresql://localhost:5432/logistics_db

# Run a specific service locally
cd services/tracking-service
go run ./cmd/server -config=./config/local.yaml

# Run all tests
./gradlew test          # Java/Kotlin services
go test ./...           # Go services
pytest -q               # Python services
npm test                # Node.js services
```

### Environment Variables

All services read configuration from environment variables. Use `.env.local` (git-ignored) for local overrides.

| Variable | Default (local) | Description |
|---|---|---|
| `POSTGRES_URL` | `postgres://logistics:logistics_dev@localhost:5432/logistics_db` | Main PostgreSQL DSN |
| `TIMESCALEDB_URL` | `postgres://logistics:logistics_dev@localhost:5433/gps_db` | TimescaleDB DSN |
| `KAFKA_BROKERS` | `localhost:9092` | Comma-separated broker list |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch endpoint |
| `LOG_LEVEL` | `debug` | One of: debug, info, warn, error |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OpenTelemetry collector endpoint |

---

## Language Standards by Service

Each service uses the language best suited to its performance and ecosystem requirements.

| Service | Language | Runtime | Rationale |
|---|---|---|---|
| tracking-service | **Go 1.22** | Native binary | High-throughput GPS event processing; minimal GC pause; low memory footprint |
| gps-processing-service | **Go 1.22** | Native binary | CPU-bound coordinate math; goroutine-per-partition concurrency model fits Kafka |
| shipment-service | **Kotlin / Spring Boot 3** | JVM 21 | Complex domain model; DDD aggregate pattern; rich validation libraries |
| carrier-integration-service | **Node.js 20 (TypeScript)** | Node.js | Carrier API adapters are I/O-bound; async/await well-suited; easy JSON manipulation |
| notification-service | **Node.js 20 (TypeScript)** | Node.js | Email/SMS/push SDKs have excellent Node.js support |
| route-optimization-service | **Python 3.12** | CPython | OR-Tools (Google) and scikit-learn are Python-native; ML model inference |
| customs-service | **Kotlin / Spring Boot 3** | JVM 21 | Complex rule engine for HS codes and duty calculation |
| returns-service | **Kotlin / Spring Boot 3** | JVM 21 | Shares domain model with shipment-service |
| analytics-service | **Python 3.12** | CPython | Pandas/Polars for aggregation; Elasticsearch Python client |

---

## API Design Standards

All REST APIs follow these conventions regardless of language:

### URL Structure
```
GET    /v1/shipments                          # list (paginated)
POST   /v1/shipments                          # create
GET    /v1/shipments/{shipmentId}             # get by ID
PATCH  /v1/shipments/{shipmentId}             # partial update
DELETE /v1/shipments/{shipmentId}             # soft delete

GET    /v1/shipments/{shipmentId}/tracking    # tracking events for a shipment
POST   /v1/shipments/{shipmentId}/exceptions  # raise an exception
```

### Error Response Format
All error responses use RFC 7807 Problem Details:
```json
{
  "type": "https://logistics.example.com/errors/validation-failed",
  "title": "Validation Failed",
  "status": 422,
  "detail": "Consignee postal code '9999' is invalid for country AU",
  "instance": "/v1/shipments",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "errors": [
    { "field": "consignee.postalCode", "code": "INVALID_POSTAL_CODE", "message": "..." }
  ]
}
```

### Pagination
All list endpoints use cursor-based pagination (not offset):
```
GET /v1/shipments?limit=50&after=cursor_eyJpZCI6MTAwfQ==
```
Response includes `next_cursor` and `has_more` fields. Maximum `limit` is 200.

### Idempotency
All mutating POST endpoints require `Idempotency-Key` header (UUID v4). Keys are scoped to `(tenant_id, endpoint, key)` and cached for 24 hours.

---

## Database Access Patterns

### Repository Pattern
Services never issue SQL directly in business logic. All database access goes through typed repositories.

```go
// Good: repository interface (Go)
type ShipmentRepository interface {
    Save(ctx context.Context, s *Shipment) error
    FindByID(ctx context.Context, id ShipmentID) (*Shipment, error)
    FindByTrackingNumber(ctx context.Context, tn TrackingNumber) (*Shipment, error)
    FindByTenantAndStatus(ctx context.Context, tenantID TenantID, status ShipmentStatus, cursor string, limit int) ([]*Shipment, string, error)
}

// Bad: raw SQL in service layer
func (s *ShipmentService) GetShipment(id string) (*Shipment, error) {
    row := s.db.QueryRow("SELECT * FROM shipments WHERE id = $1", id) // ❌
    ...
}
```

### Migrations (Flyway)
- Migration files live in `db/migrations/` within each service.
- File naming: `V{version}__{description}.sql` (e.g., `V001__create_shipments_table.sql`).
- Migrations are **append-only**: never edit a committed migration; always add a new one.
- Breaking changes (column drops, type changes) require a three-phase migration: add new → backfill → drop old.

### No N+1 Queries
Repository implementations must batch-load related entities. Use `IN (...)` clauses for collections:
```sql
-- Good
SELECT * FROM tracking_events WHERE shipment_id = ANY($1::uuid[]);

-- Bad: called in a loop
SELECT * FROM tracking_events WHERE shipment_id = $1;
```

---

## Domain Model Conventions

- **Aggregate roots are immutable after creation** of their identity. The `Shipment` aggregate's `shipmentId` field is set once and never changed.
- **Value objects wrap primitives.** Do not use raw `String` for tracking numbers, AWB numbers, or postal codes — wrap them in value object classes that enforce format validation at construction time.
- **Domain events are first-class citizens.** Every state transition emits a domain event. Events are stored in the outbox table within the same transaction as the aggregate mutation.
- **No domain logic in controllers or repositories.** Business rules live in the aggregate or domain services only.

---

## GPS Data Processing Best Practices

### Coordinate Validation
```go
func ValidateCoordinates(lat, lon float64) error {
    if lat < -90.0 || lat > 90.0 {
        return ErrInvalidLatitude
    }
    if lon < -180.0 || lon > 180.0 {
        return ErrInvalidLongitude
    }
    return nil
}
```

### Deduplication
Skip GPS pings that are **both** within 10 metres of the last known position **and** within 5 seconds of the last recorded ping. Either condition alone is not sufficient — a stationary vehicle should still emit a ping every 30 seconds for liveness tracking.

```go
func (v *GPSValidator) IsDuplicate(vehicleID string, lat, lon float64, recordedAt time.Time) bool {
    last, ok := v.cache.GetPosition(vehicleID)
    if !ok {
        return false
    }
    distanceM := HaversineMeters(last.Lat, last.Lon, lat, lon)
    timeDelta := recordedAt.Sub(last.RecordedAt)
    return distanceM < 10.0 && timeDelta < 5*time.Second
}
```

### Batch Writes to TimescaleDB
Do not write GPS pings individually. Accumulate 100 breadcrumbs in a buffer and flush using `COPY` or a multi-row INSERT for throughput. Flush also triggers on a 500ms timeout to prevent stale data.

```go
const batchSize = 100
const flushInterval = 500 * time.Millisecond
```

### Redis Vehicle Position Cache
Store the most recent vehicle position in Redis with a 5-minute TTL. Key format: `vehicle:pos:{vehicleId}`. Serialise as JSON with `lat`, `lon`, `speed_kmh`, `heading`, `recorded_at` fields.

```
SET vehicle:pos:VH-12345 '{"lat":28.6139,"lon":77.2090,"speed_kmh":45.2,"heading":270,"recorded_at":"2024-01-15T10:30:00Z"}' EX 300
```

### Outlier / Anomaly Filtering
Reject GPS coordinates where the implied speed from the last known position exceeds 500 km/h. This filters GPS drift, spoofed coordinates, and device clock errors.

```go
func IsOutlier(prev, curr GPSPosition) bool {
    distKm := HaversineKm(prev.Lat, prev.Lon, curr.Lat, curr.Lon)
    hours := curr.RecordedAt.Sub(prev.RecordedAt).Hours()
    if hours <= 0 {
        return true
    }
    impliedSpeedKmh := distKm / hours
    return impliedSpeedKmh > 500.0
}
```

---

## Carrier API Integration Patterns

### ICarrierAdapter Interface
Every carrier implements a single interface. This enforces a uniform contract regardless of carrier API style (REST, SOAP, EDI).

```typescript
interface ICarrierAdapter {
  book(request: BookingRequest): Promise<BookingResponse>;
  cancelBooking(awb: string): Promise<void>;
  getTrackingStatus(awb: string): Promise<TrackingStatusResponse>;
  getLabel(awb: string, format: LabelFormat): Promise<LabelData>;
  getEstimatedDelivery(origin: Address, dest: Address, serviceCode: string): Promise<Date>;
}
```

### Circuit Breaker Configuration (Resilience4j)
Each carrier has its own independently configured circuit breaker:

```yaml
resilience4j:
  circuitbreaker:
    instances:
      fedex:
        slidingWindowSize: 30
        failureRateThreshold: 50         # open after 5 failures in 30s window
        waitDurationInOpenState: 60s     # half-open after 60s
        permittedNumberOfCallsInHalfOpenState: 3
      ups:
        slidingWindowSize: 30
        failureRateThreshold: 50
        waitDurationInOpenState: 60s
```

### Retry Policy
Retry transient errors (HTTP 5xx, connection timeout) with exponential backoff. Do **not** retry HTTP 4xx (permanent failures).

```typescript
const retryConfig = {
  retries: 3,
  factor: 2,
  minTimeout: 1000,   // 1s → 2s → 4s
  maxTimeout: 8000,
  retryOn: (err: Error, res: Response) => {
    if (res && res.status >= 400 && res.status < 500) return false; // no retry for 4xx
    return true;
  },
};
```

### Idempotency
Use the AWB number as the idempotency key for carrier booking requests. If the carrier returns a duplicate booking error (HTTP 409), treat it as a success and return the existing AWB.

### Webhook Signature Validation
All inbound carrier webhooks must have their HMAC-SHA256 signature validated before processing:

```typescript
function validateCarrierWebhook(
  payload: Buffer,
  signature: string,
  secret: string
): boolean {
  const expected = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');
  return crypto.timingSafeEqual(
    Buffer.from(expected, 'hex'),
    Buffer.from(signature, 'hex')
  );
}
```

---

## Testing Strategy

| Layer | What to Test | Tools | Notes |
|---|---|---|---|
| Unit | Business logic, domain rules, adapter transformations | Go test, JUnit 5, pytest, Jest | Carrier adapters tested against mock HTTP server |
| Integration | Carrier adapters against sandbox APIs | Testcontainers, WireMock | Run in CI against real sandbox endpoints weekly |
| E2E | Full shipment lifecycle in staging | Playwright, REST-assured | Staging environment = production minus real carrier calls |
| Load | GPS processing pipeline throughput | k6 | Target: 10,000 GPS events/second sustained for 10 minutes |
| Contract | Carrier API response shape validation | Pact | Provider tests run on every carrier adapter change |
| Chaos | Broker outage, DB failover, network partition | Chaos Mesh | Run weekly in staging; results reviewed in reliability sync |

### Load Test Targets
- GPS ingest: 10,000 events/second with P99 < 100ms
- Shipment API: 5,000 req/second with P99 < 200ms
- Tracking query (public): 20,000 req/second with P99 < 50ms (CDN-assisted)

---

## Observability Standards

### Structured Logging
Every log line must include these mandatory fields. Use the shared logging library (`pkg/logging`) — do not use raw `fmt.Println` or `console.log`.

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "info",
  "service": "tracking-service",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "shipment_id": "SHP-2024-001234",
  "carrier_id": "fedex",
  "tenant_id": "tenant-acme",
  "message": "GPS breadcrumb written to TimescaleDB"
}
```

### Prometheus Metrics
All services expose `/metrics` on port `9090` in Prometheus exposition format. Required metrics:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `gps_events_processed_total` | Counter | `vehicle_id`, `outcome` | Total GPS pings processed |
| `gps_kafka_consumer_lag` | Gauge | `topic`, `partition`, `group` | Current consumer lag |
| `gps_timescaledb_write_duration_seconds` | Histogram | `outcome` | TimescaleDB write latency |
| `shipment_sla_breach_total` | Counter | `carrier_id`, `sla_class` | SLA breaches detected |
| `carrier_api_request_duration_seconds` | Histogram | `carrier_id`, `operation`, `status` | Carrier API call latency |
| `delivery_attempt_outcome_total` | Counter | `carrier_id`, `outcome` | Delivery attempt results |

### Distributed Tracing (OpenTelemetry)
All services instrument using the OpenTelemetry SDK. Traces propagate via `traceparent` HTTP header. Spans are exported to Jaeger via OTLP (gRPC on port 4317).

Every HTTP handler and Kafka consumer must create a span. Use the shared `pkg/tracing` wrapper:

```go
ctx, span := tracer.Start(ctx, "gps.process_update",
    trace.WithAttributes(
        attribute.String("vehicle.id", vehicleID),
        attribute.Float64("gps.lat", lat),
        attribute.Float64("gps.lon", lon),
    ),
)
defer span.End()
```

### PagerDuty Alerts

| Severity | Condition | Team | Response Time |
|---|---|---|---|
| SEV-1 | GPS pipeline lag > 5 min OR delivery SLA breach rate > 5% | On-call SRE | 15 minutes |
| SEV-2 | GPS pipeline lag > 30s OR Kafka consumer at max replicas | Platform team | 1 hour |
| SEV-3 | Carrier webhook failure burst OR DLQ depth > 1,000 | Feature team | Next business day |

