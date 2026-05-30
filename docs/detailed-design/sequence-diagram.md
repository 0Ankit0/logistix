# Sequence Diagram

This document contains detailed interaction sequence diagrams for the Logistics Tracking System's four most critical flows. Each diagram models the exact message exchanges, error paths, and asynchronous events between services and external systems.

---

## Sequence 1: Carrier Allocation Process

Triggered when a confirmed shipment needs to be booked with a carrier. The `ShipmentService` delegates carrier selection and booking, with automatic fallback to the next carrier on failure.

```mermaid
sequenceDiagram
    autonumber
    participant SS as ShipmentService
    participant CSS as CarrierSelectionService
    participant CAF as CarrierAdapterFactory
    participant FedEx as FedExAdapter
    participant FedExAPI as FedEx REST API
    participant LS as LabelService
    participant S3 as Amazon S3
    participant Kafka as Kafka
    participant NS as NotificationService

    SS->>CSS: selectCarrier(shipmentId, weight, origin, destination, serviceLevel)
    CSS->>CSS: loadCarrierPriorityList(origin, destination)
    CSS->>CSS: evaluateContracts() — filter by lane, weight, service
    CSS-->>SS: carrierId = "FEDEX", priority=1

    SS->>CAF: getAdapter("FEDEX")
    CAF-->>SS: FedExAdapter instance

    SS->>FedEx: getRates(RateRequest{origin, dest, weight, dims, serviceLevel})
    FedEx->>FedExAPI: POST /rate/v1/rates/quotes
    FedExAPI-->>FedEx: 200 OK {rates: [{service, cost, eta}]}
    FedEx-->>SS: List[RateQuote] — FEDEX_PRIORITY_OVERNIGHT $42.50

    SS->>SS: validateRateAgainstBudget(quote) — PASS

    SS->>FedEx: book(BookingRequest{shipmentId, origin, dest, items, declaredValue})
    FedEx->>FedExAPI: POST /ship/v1/shipments
    alt FedEx API success
        FedExAPI-->>FedEx: 201 Created {masterTrackingNumber, label_url}
        FedEx-->>SS: BookingResponse{awb="794...", labelUrl="https://fedex.com/label/..."}
        SS->>LS: generateLabel(awb, shipmentDetails, labelFormat=PDF)
        LS->>S3: putObject(bucket="labels", key="shipment/{id}/label.pdf", content)
        S3-->>LS: ETag, versionId
        LS-->>SS: labelS3Url = "s3://labels/shipment/{id}/label.pdf"
        SS->>SS: createCarrierAllocation(shipmentId, awb, labelS3Url)
        SS->>SS: updateShipmentStatus(CONFIRMED → PICKUP_SCHEDULED)
        SS->>Kafka: publish("shipment.booked.v1", {shipmentId, carrierId, awb, eta, labelUrl})
        Kafka-->>SS: ack (offset committed)
        Kafka--)NS: consume("shipment.booked.v1")
        NS->>NS: loadShipperPreferences(shipperId)
        NS->>NS: renderTemplate("shipment_booked", {awb, eta, trackingUrl})
        NS-->>NS: sendEmail(shipper@example.com) + sendWebhook(shipper callback URL)
    else FedEx API failure (5xx or timeout)
        FedExAPI-->>FedEx: 503 Service Unavailable
        FedEx-->>SS: throw CarrierApiException{carrier="FEDEX", code=503}
        Note over SS: Circuit breaker records failure #1
        SS->>CSS: getNextCarrier(shipmentId, excludeCarriers=["FEDEX"])
        CSS-->>SS: carrierId = "UPS", priority=2
        SS->>CAF: getAdapter("UPS")
        CAF-->>SS: UPSAdapter instance
        SS->>SS: retry full booking flow with UPS adapter
        Note over SS: If all carriers fail → raise ExceptionCase(CARRIER_UNAVAILABLE)
    end
```

### Carrier Allocation — Notes

| Step | Detail |
|---|---|
| Carrier priority list | Loaded from `carrier_lane_contracts` table; ordered by cost ASC, SLA compliance DESC |
| Rate validation | Budget policy checked: `allocatedRate ≤ declaredValue × 0.15` (configurable per tenant) |
| Label storage | Labels stored in S3 with server-side encryption; URL signed on demand with 1-hour expiry for driver app |
| Circuit breaker | Per-carrier Resilience4j circuit; opens after 5 failures in 60s; half-open probe every 30s |
| Fallback chain | FedEx → UPS → DHL → USPS → manual exception queue |

---

## Sequence 2: GPS Update Processing

High-throughput path for raw GPS pings from driver devices. Designed for 10,000+ pings/second with deduplication, geofence evaluation, and EDD recalculation.

```mermaid
sequenceDiagram
    autonumber
    participant Device as GPS Device
    participant API as GPS Ingest API
    participant GPSP as GPSProcessor
    participant TSDB as TimescaleDB
    participant Redis as Redis Cache
    participant Kafka as Kafka
    participant GFS as GeofenceService
    participant EDDS as EDDService
    participant NS as NotificationService

    Device->>API: POST /gps/ping {deviceId, lat, lon, speed, heading, accuracy, timestamp}
    API->>API: authenticate(deviceId, bearerToken)
    API->>API: validateCoordinates(lat, lon) — bounds check: lat ∈ [-90,90], lon ∈ [-180,180]
    API->>API: validateAccuracy(accuracy) — reject if accuracy > 50m

    API->>Redis: GET dedup:{deviceId}:{timestamp_bucket}
    alt Duplicate ping (same device, same 5-second bucket)
        Redis-->>API: HIT — already processed
        API-->>Device: 200 OK {status: "deduplicated"}
    else New ping
        Redis-->>API: MISS
        API->>Redis: SETEX dedup:{deviceId}:{timestamp_bucket} 30s "1"

        API->>GPSP: process(GPSPing{deviceId, lat, lon, speed, heading, timestamp})
        GPSP->>GPSP: resolveShipment(deviceId) — lookup active route assignment
        GPSP->>GPSP: normalizeCoordinates(lat, lon) — snap to road network

        GPSP->>TSDB: INSERT INTO gps_breadcrumbs (device_id, shipment_id, lat, lon, speed, heading, accuracy, recorded_at)
        TSDB-->>GPSP: OK (hypertable chunk auto-created by time)

        GPSP->>Redis: SETEX gps:current:{shipmentId} 120s {lat, lon, speed, heading, updatedAt}
        Redis-->>GPSP: OK

        GPSP->>Kafka: publish("gps.location.updated.v1", {shipmentId, lat, lon, speed, timestamp})
        Kafka-->>GPSP: ack

        Kafka--)GFS: consume("gps.location.updated.v1")
        GFS->>GFS: loadActiveGeofences(shipmentId) — delivery zone, hub zones, restricted zones
        GFS->>GFS: evalPointInPolygon(lat, lon, geofences) — PostGIS ST_Contains
        alt Inside delivery geofence
            GFS->>Kafka: publish("geofence.entered.v1", {shipmentId, geofenceId, geofenceType="DELIVERY_ZONE"})
            Kafka--)NS: consume("geofence.entered.v1")
            NS-->>NS: sendPushNotification("Driver is nearby — prepare for delivery")
        else Left hub geofence
            GFS->>Kafka: publish("geofence.exited.v1", {shipmentId, geofenceId, geofenceType="HUB"})
        end

        Kafka--)EDDS: consume("gps.location.updated.v1")
        EDDS->>EDDS: loadRoute(shipmentId)
        EDDS->>EDDS: recalculateEDD(currentPos, remainingWaypoints, trafficModel)
        alt EDD shifted by > 15 minutes
            EDDS->>Kafka: publish("edd.updated.v1", {shipmentId, previousEdd, newEdd, confidenceScore})
            Kafka--)NS: consume("edd.updated.v1")
            NS-->>NS: notifyConsignee(sms/email, "Delivery time updated to {newEdd}")
        end

        GPSP-->>API: OK
        API-->>Device: 200 OK {status: "accepted", processedAt: "..."}
    end
```

### GPS Processing — Notes

| Concern | Implementation |
|---|---|
| Deduplication | Redis key: `dedup:{deviceId}:{floor(timestamp/5)}` — 5-second buckets, 30s TTL |
| TimescaleDB hypertable | Partitioned by `recorded_at` (1-day chunks); compression after 7 days; continuous aggregate for hourly summaries |
| Redis TTL on current position | 120s — if no ping for 2 min, current position is stale; UI shows "last known" label |
| EDD recalculation threshold | 15-minute shift to avoid notification fatigue; configurable per service level |
| Coordinate validation | `lat ∈ [-90, 90]` and `lon ∈ [-180, 180]`; accuracy > 50m rejected; speed > 200 km/h flagged |
| Kafka topic throughput | `gps.location.updated.v1` — 64 partitions, keyed by `shipmentId` for ordered processing |

---

## Sequence 3: Delivery Attempt with POD Capture

The last-mile delivery flow, covering both the happy path (successful delivery with signature/photo) and the failure path (recipient absent, multiple attempts, return initiation).

```mermaid
sequenceDiagram
    autonumber
    participant Driver as Driver Mobile App
    participant DS as DeliveryService
    participant PODS as PODService
    participant S3 as Amazon S3
    participant Kafka as Kafka
    participant NS as NotificationService
    participant AS as AnalyticsService

    Driver->>DS: POST /delivery/arrive {shipmentId, waypointId, driverLocation}
    DS->>DS: validateDriverAssignment(driverId, shipmentId)
    DS->>DS: updateWaypointStatus(waypointId, ARRIVED, actualArrival=now())
    DS-->>Driver: 200 OK {deliveryWindowOpen: true, parcelList: [...]}

    Driver->>DS: POST /delivery/scan {parcelId, barcodeValue}
    DS->>DS: verifyParcelBarcode(parcelId, barcodeValue)
    DS->>DS: checkDeliveryInstructions(shipmentId) — safe drop? signature required?
    DS-->>Driver: 200 OK {requiresSignature: true, recipientName: "Jane Doe"}

    alt Happy Path — Recipient Present
        Driver->>DS: POST /delivery/verify-recipient {shipmentId, recipientName, idVerified}
        DS->>DS: validateRecipient(recipientName) — fuzzy match against booking name
        DS-->>Driver: 200 OK {verified: true}

        Driver->>DS: POST /delivery/capture-signature {shipmentId, signatureData: base64PNG}
        DS->>PODS: createPOD(shipmentId, parcelId, signatureData, driverLocation)
        PODS->>S3: putObject(bucket="pod-artifacts", key="pod/{shipmentId}/signature.png", signatureData)
        S3-->>PODS: ETag, objectUrl

        Driver->>DS: POST /delivery/capture-photo {shipmentId, photoData: base64JPEG}
        PODS->>S3: putObject(bucket="pod-artifacts", key="pod/{shipmentId}/photo.jpg", photoData)
        S3-->>PODS: ETag, objectUrl

        PODS->>PODS: createPODRecord{shipmentId, signatureUrl, photoUrl, capturedAt, geoPoint}
        PODS-->>DS: PODRecord{podId, signatureUrl, photoUrl}

        DS->>DS: markParcelDelivered(parcelId, podId)
        DS->>DS: updateShipmentStatus(OUT_FOR_DELIVERY → DELIVERED)
        DS->>DS: updateWaypointStatus(waypointId, COMPLETED, actualDeparture=now())

        DS->>Kafka: publish("delivery.succeeded.v1", {shipmentId, parcelId, podId, deliveredAt, recipientName})
        Kafka-->>DS: ack

        Kafka--)NS: consume("delivery.succeeded.v1")
        NS->>NS: loadConsigneePreferences(consigneeId)
        NS-->>NS: sendSMS("Your parcel {trackingNo} has been delivered. View POD: {podUrl}")
        NS-->>NS: sendEmail(consignee, templateId="delivery_success", {trackingNo, podUrl, deliveredAt})
        NS-->>NS: triggerShipperWebhook(shipper callbackUrl, payload={shipmentId, status="DELIVERED"})

        Kafka--)AS: consume("delivery.succeeded.v1")
        AS->>AS: updateDeliveryMetrics(shipmentId, driverId, routeId, deliveryDurationMinutes)
        AS->>AS: incrementDriverKPI(driverId, SUCCESSFUL_DELIVERIES)

        DS-->>Driver: 200 OK {status: "DELIVERED", nextWaypoint: {...}}

    else Failure Path — Recipient Absent
        Driver->>DS: POST /delivery/attempt-failed {shipmentId, reason: "RECIPIENT_ABSENT", notes: "Left card"}
        DS->>DS: recordDeliveryAttempt(shipmentId, attemptNumber, FAILED, reason="RECIPIENT_ABSENT")
        DS->>DS: checkMaxAttempts(shipmentId) — attempt 1 of 3

        alt Attempts remaining
            DS->>DS: scheduleRedelivery(shipmentId, preferredDate=tomorrow)
            DS->>DS: updateShipmentStatus(OUT_FOR_DELIVERY → EXCEPTION)
            DS->>Kafka: publish("delivery.failed.v1", {shipmentId, attempt:1, reason, redeliveryDate})
            Kafka-->>DS: ack
            Kafka--)NS: consume("delivery.failed.v1")
            NS-->>NS: sendSMS(consignee, "Delivery attempted. Reschedule at: {rescheduleUrl}")
            NS-->>NS: sendEmail(consignee, templateId="delivery_failed", {attempt:1, redeliveryDate})
            DS-->>Driver: 200 OK {nextWaypoint: {...}}
        else Max attempts reached (attempt 3)
            DS->>DS: initiateReturn(shipmentId, reason="MAX_ATTEMPTS_EXCEEDED")
            DS->>DS: updateShipmentStatus(OUT_FOR_DELIVERY → RETURNED_TO_SENDER)
            DS->>Kafka: publish("return.initiated.v1", {shipmentId, reason:"MAX_ATTEMPTS_EXCEEDED"})
            Kafka--)NS: consume("return.initiated.v1")
            NS-->>NS: sendEmail(consignee, templateId="return_initiated")
            NS-->>NS: sendEmail(shipper, templateId="return_to_sender_notification")
        end
    end
```

### POD Capture — Notes

| Step | Detail |
|---|---|
| Signature storage | PNG encoded as base64 in app; decoded server-side; stored in S3 `pod-artifacts` bucket with AES-256 |
| Photo storage | JPEG, max 5 MB; resized to 1024×768 on upload; original retained for 90 days then purged |
| Recipient verification | Fuzzy match using Levenshtein distance ≤ 2; override allowed by dispatcher with audit log |
| Max delivery attempts | Default 3; configurable per service level (OVERNIGHT = 1 attempt, ECONOMY = 3) |
| POD URL access | Pre-signed S3 URL, 7-day expiry; shipper portal generates fresh URL on demand |
| Safe-drop rules | If `safeDropAllowed=true` and no signature required → contactless delivery; photo mandatory |

---

## Sequence 4: Exception Detection and Auto-Resolution

The monitoring loop that detects SLA breaches, damage reports, and stale scan events, then attempts automated resolution before escalating to the operations team.

```mermaid
sequenceDiagram
    autonumber
    participant TM as TrackingMonitor
    participant ES as ExceptionService
    participant RE as RuleEngine
    participant NS as NotificationService
    participant OPS as OpsManagerPortal
    participant CAPI as CarrierAPI

    Note over TM: Scheduled job — runs every 5 minutes

    TM->>TM: loadShipmentsRequiringCheck() — query IN_TRANSIT, OUT_FOR_DELIVERY > threshold
    TM->>TM: detectAnomalies(shipments) — no scan in 4h, EDD breach imminent, GPS stale

    loop For each anomaly detected
        TM->>ES: createException(shipmentId, anomalyType, detectedAt, evidence)
        ES->>RE: evaluate(ExceptionCandidate{shipmentId, type, severity})

        RE->>RE: loadRules(exceptionType) — rules from config: BR-EX-01 .. BR-EX-12
        RE->>RE: applyRules(candidate) — check SLA tier, carrier history, value threshold

        alt Rule: SLA breach imminent (BR-EX-01)
            RE-->>ES: severity=HIGH, autoResolutionStrategy=NOTIFY_CARRIER
            ES->>ES: createExceptionRecord(type=SLA_BREACH, severity=HIGH, slaBreachAt=T+2h)
            ES->>NS: notifyStakeholders(shipmentId, SHIPPER + CONSIGNEE, template="sla_at_risk")
            NS-->>NS: sendEmail + sendSMS

            ES->>CAPI: requestCarrierUpdate(awbNumber) — probe FedEx tracking API
            CAPI-->>ES: latestEvent{status="AT_FACILITY", timestamp="..."}

            alt Carrier confirms shipment progressing
                ES->>ES: updateException(status=AUTO_RESOLVED, resolution="Carrier confirmed in-transit")
                ES->>NS: notifyStakeholders(shipmentId, "Shipment progressing — EDD updated")
            else Carrier has no update or confirms delay
                ES->>ES: updateException(status=ESCALATED)
                ES->>NS: alertOpsManager(opsManagerId, template="exception_escalated", {shipmentId, type, eta})
                NS->>OPS: POST /ops/alerts {shipmentId, exceptionId, severity=HIGH}
                OPS-->>NS: 200 OK

                Note over OPS: Ops manager investigates via portal

                OPS->>ES: POST /exceptions/{id}/investigate {notes: "Contacted carrier — delay confirmed 24h"}
                ES->>ES: updateException(status=INVESTIGATING, assignedTo=opsManagerId)
                OPS->>ES: POST /exceptions/{id}/resolve {resolutionType=CARRIER_CONTACTED, notes, newEdd}
                ES->>ES: createExceptionResolution(resolutionType, notes, resolvedBy, resolvedAt=now())
                ES->>ES: updateException(status=RESOLVED, resolvedAt=now())
                ES->>NS: notifyStakeholders(shipmentId, SHIPPER+CONSIGNEE, template="exception_resolved", {newEdd})
                ES->>Kafka: publish("exception.resolved.v1", {shipmentId, exceptionId, resolutionType, newEdd})
            end

        else Rule: Damage suspected (BR-EX-03)
            RE-->>ES: severity=CRITICAL, autoResolutionStrategy=NONE
            ES->>ES: createExceptionRecord(type=DAMAGE, severity=CRITICAL)
            ES->>NS: alertOpsManager(CRITICAL, "Damage suspected — immediate action required")
            ES->>NS: notifyShipper("We detected a potential damage incident. Claim ref: {claimId}")
            Note over ES: No auto-resolution for CRITICAL damage — always escalates to ops

        else Rule: Stale GPS (BR-EX-07)
            RE-->>ES: severity=MEDIUM, autoResolutionStrategy=CONTACT_DRIVER
            ES->>NS: sendDriverPushNotification(driverId, "GPS signal lost — please enable location")
            Note over ES: If GPS resumes within 15 min → auto-resolve; else escalate
        end
    end
```

### Exception Handling — Business Rules Reference

| Rule ID | Trigger Condition | Severity | Auto-Resolution |
|---|---|---|---|
| BR-EX-01 | No carrier scan for > 4h while IN_TRANSIT | HIGH | Probe carrier API, notify if progressing |
| BR-EX-02 | Delivery EDD breached with no OUT_FOR_DELIVERY scan | HIGH | Escalate to ops, notify shipper |
| BR-EX-03 | Carrier reports damage event | CRITICAL | None — immediate ops escalation |
| BR-EX-04 | Address validation failed at delivery | MEDIUM | Request shipper address correction |
| BR-EX-05 | Customs hold flag from carrier | HIGH | Notify customs broker, hold shipment |
| BR-EX-06 | 3rd delivery attempt failed | HIGH | Initiate return, notify both parties |
| BR-EX-07 | GPS stale > 30 min during active route | MEDIUM | Push notification to driver |
| BR-EX-08 | Shipment weight exceeds booked weight by > 10% | LOW | Flag for billing correction |
| BR-EX-09 | Carrier AWB cancelled externally | CRITICAL | Rebook with alternate carrier |
| BR-EX-10 | Temperature excursion on refrigerated shipment | CRITICAL | Immediate ops + shipper alert |
| BR-EX-11 | Vehicle breakdown event from driver app | HIGH | Reassign parcels to alternate driver |
| BR-EX-12 | Auto-escalation timeout — exception open > 4h | HIGH | Auto-escalate to ops manager |

---

## Integration Retry and Idempotency

- **Event publishing:** Outbox pattern — mutations and outbox records committed atomically; relay publishes with exponential backoff (`base=500ms`, `factor=2`, `max=5m`, jitter=±20%).
- **Deduplication:** `event_id` is a UUID; consumers persist `(event_id, consumer_group, processed_at)` before executing side-effects.
- **API idempotency:** All mutating endpoints require `Idempotency-Key` header; scoped by `(tenantId, route, key)`; 24-hour retention.
- **Webhook retries:** 3 fast retries (5s, 15s, 30s) + 8 slow retries (5m, 15m, 30m…); HMAC-signed payloads; exhausted → DLQ with replay tooling.
- **GPS ingest:** Fire-and-forget with 200 OK acknowledgement; no back-pressure to device; TimescaleDB and Redis writes are async.

