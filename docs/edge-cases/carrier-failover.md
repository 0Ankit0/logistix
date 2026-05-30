# Carrier Failover

Edge cases covering failures in the carrier integration layer: API outages, capacity limits, service suspensions, handoff breakdowns, and international rejection events. These scenarios require the system to route around unavailable carrier services without interrupting shipper operations.

**Severity range:** P1 (High) — P2 (Medium)

---

## Cases

1. [Carrier API Unavailability](#1-carrier-api-unavailability)
2. [Carrier Capacity Exceeded](#2-carrier-capacity-exceeded)
3. [Carrier Service Suspension](#3-carrier-service-suspension)
4. [Mid-Transit Carrier Handoff Failure](#4-mid-transit-carrier-handoff-failure)
5. [International Carrier Rejection](#5-international-carrier-rejection)

---

### 1. Carrier API Unavailability

**Failure Mode:** A major carrier's integration API (FedEx, UPS, DHL, or equivalent) returns HTTP 503 Service Unavailable, times out after the configured threshold, or drops the TCP connection for a sustained period exceeding 5 minutes. The failure may be intermittent at first, then sustained.

**Impact:** New shipment bookings on the affected carrier are blocked (label generation fails); real-time tracking updates stop flowing in; EDD recalculations dependent on carrier data become stale; operations dashboards lose live carrier status. If no failover is configured, shippers receive booking errors, eroding confidence.

**Detection:**
- Circuit breaker (Resilience4j or equivalent) opens after 5 consecutive failures within 30 seconds on the carrier HTTP client.
- Prometheus alert: `carrier_api_error_rate{carrier="fedex"} > 0.1` for 5 minutes → P1 page to on-call.
- Health check endpoint (called every 30 seconds) returns non-200 → carrier marked `DEGRADED` in the carrier availability registry.
- Log pattern: `ERROR CarrierClient - carrier=fedex status=503` or `TimeoutException` spike in carrier integration service logs.

**Mitigation:**
- Circuit breaker open state prevents further calls to the unavailable carrier, protecting against thread pool exhaustion and cascading latency.
- New booking requests on the affected carrier are queued in a persistent retry queue (Kafka topic `carrier.booking.retry`) rather than immediately rejected to shippers.
- For shipments where booking cannot be deferred, route automatically to the pre-configured backup carrier for the same service lane; apply backup carrier rates and notify shipper of carrier substitution.
- Suppress repeated EDD recalculation calls that depend on carrier API; use last-known data with a staleness warning on the tracking page.

**Recovery:**
- Circuit breaker enters half-open state after 60 seconds; sends a single test request to the carrier API.
- If test request succeeds → breaker closes; normal traffic resumes.
- If test request fails → breaker stays open; retry half-open after another 60 seconds (exponential backoff cap at 5 minutes).
- Once breaker closes, drain the retry queue: process queued bookings in order with a configurable concurrency limit to avoid overwhelming the recovered carrier API.
- Reconcile any shipments that were automatically shifted to backup carrier; update carrier assignment in shipment records.
- Alert operations team that carrier API has recovered; confirm all queued bookings processed successfully.

**Prevention:**
- Circuit breaker pattern implemented for every outbound carrier HTTP client; no carrier call is made without circuit breaker protection.
- Carrier health checks every 30 seconds (lightweight ping endpoint); carrier availability registry updated in real time.
- Backup carrier pre-configured per service lane in the carrier routing matrix; failover is automatic and requires no manual intervention.
- Carrier SLA contracts require 99.9% API uptime with defined escalation contacts; API outages beyond 30 minutes trigger contractual incident process.
- Synthetic monitoring: automated booking test every 5 minutes per carrier in a staging environment to detect degradation before production impact.

---

### 2. Carrier Capacity Exceeded

**Failure Mode:** A carrier returns a `capacity_exceeded`, `429 Too Many Requests`, or equivalent error for specific routes or service classes during peak shipping periods (Black Friday, Christmas, major sale events). The carrier cannot accept additional volume on the affected lanes.

**Impact:** New shipments cannot be booked on the primary carrier for affected routes; shippers receive booking failures or are silently downgraded to a slower service; if no secondary carrier is configured, bookings must be manually held until capacity opens; shipper fulfilment pipelines may be blocked, causing downstream order delays.

**Detection:**
- Carrier API returns `HTTP 429` or JSON body containing `error_code: CAPACITY_EXCEEDED` for specific route/service-class combinations.
- Booking success rate metric `carrier_booking_success_rate{carrier="ups", route="NY-LA"}` drops below 100% → alert fires.
- Capacity exceeded events from carrier webhook (some carriers push proactive capacity notices) parsed and stored in carrier capacity registry.
- Operations team receives peak season capacity warnings from carrier account manager (manual signal that should trigger pre-emptive action).

**Mitigation:**
- Route new booking requests for affected lanes to the secondary carrier with matching or equivalent service level; record the substitution in the shipment record.
- Notify shipper of carrier substitution via webhook `shipment.carrier_changed.v1` with original carrier, substitute carrier, and reason.
- Apply secondary carrier rates transparently; if rates differ significantly, alert billing system to adjust invoice.
- If no secondary carrier is available for the lane, place booking in a holding queue and notify shipper of delay with an estimated opening time.
- Pause automated volume commitments to the primary carrier for the affected lane; do not over-commit.

**Recovery:**
- Poll carrier capacity API (or await carrier webhook notification) for capacity restoration on the affected lane.
- Once capacity opens, resume routing to primary carrier; drain holding queue in order of shipment creation time.
- Evaluate whether accumulated delayed bookings should all go to primary carrier or be split across carriers to prevent a new capacity spike on restoration.
- Reconcile any shipments booked on secondary carrier during outage; confirm tracking integrations are active for those shipments.

**Prevention:**
- Capacity forecasting: analyse historical booking volume by lane and season; negotiate pre-booked capacity allocations with carriers before peak periods.
- Multi-carrier contracts: maintain active contracts with at least two carriers per major lane; capacity on secondary carrier is always available as true backup, not just theoretical.
- Carrier capacity monitoring: integrate with carrier capacity APIs (where available) to get advance warning of utilisation approaching limits.
- Volume smoothing: during high-load events, spread booking API traffic across time windows rather than allowing sudden volume spikes.

---

### 3. Carrier Service Suspension

**Failure Mode:** A carrier suspends service to a specific country, postal region, or product type due to regulatory changes, government embargo, operational incidents (e.g., labour strike), or safety concerns. The suspension may be announced with short notice (24–48 hours) or take effect immediately with no warning.

**Impact:** All new bookings to the affected route are unserviceable; in-transit shipments already en route to the affected destination may be stranded at origin or intermediate hub; shippers with active fulfilment pipelines targeting the affected region are blocked; consignees awaiting deliveries receive no further updates; potential customs or import compliance issues for already-in-transit goods.

**Detection:**
- Carrier sends suspension notice via email, API status endpoint, or webhook; system parses and stores in the carrier service availability registry.
- Carrier API returns `service_suspended` or `route_not_available` error codes for bookings to affected destinations.
- Alert: `carrier_service_suspended{carrier="dhl", destination="RU"}` event published → P1 notification to carrier operations team.
- Monitoring of carrier status pages (automated scraping or official status feed) detects route removal.

**Mitigation:**
- Immediately halt new booking acceptance for the affected carrier-route combination; return HTTP 422 to booking API callers with a clear message identifying the suspension.
- Identify all in-transit shipments on the affected route that have not yet been handed to the carrier for international leg; hold at origin hub pending alternative routing.
- For shipments already handed to the carrier and in international transit, open emergency investigation with carrier to determine their disposition (hold at hub, return to origin, or continue to a transit country).
- Notify all affected shippers via bulk notification with suspension details, affected route, estimated duration (if known), and instruction on what action to take.

**Recovery:**
- Identify alternative carrier capable of serving the affected route; negotiate emergency capacity if needed.
- Reroute held in-transit shipments to alternative carrier; issue new AWBs; update tracking records.
- For shipments already in the carrier's possession, coordinate with carrier for return-to-origin or transfer to alternative carrier at the nearest international hub.
- Once carrier lifts the suspension, re-enable route in the carrier service availability registry; resume normal booking flow.
- Conduct post-incident review: assess whether the suspension was foreseeable and whether earlier detection would have prevented stranded shipments.

**Prevention:**
- Carrier service bulletin monitoring: automated parsing of carrier operational notices and service advisories; alerts when bulletins affect active routes.
- Carrier diversity per route: for any route with significant volume, maintain at least two active carrier contracts so suspension of one does not leave the route unserviceable.
- Contractual SLAs with carriers include suspension notification minimum lead times (e.g., 72 hours for planned suspensions) with financial penalties for non-compliance.
- Geopolitical risk scoring on destination countries; flag high-risk routes for additional carrier backup planning.

---

### 4. Mid-Transit Carrier Handoff Failure

**Failure Mode:** A multi-modal shipment (e.g., air + ground, international + domestic final mile) is scheduled to transfer custody from one carrier to another at a designated handoff point — an airport, border crossing hub, or intermodal terminal. The receiving carrier fails to pick up the shipment at the agreed time, or the outgoing carrier fails to present it, leaving the parcel stranded at the transfer hub.

**Impact:** Shipment stranded at the transfer hub with no active custodian; SLA breach as delivery window passes; consignee misses confirmed delivery slot (particularly impactful for appointment-based deliveries or B2B just-in-time supply); both carriers may blame each other, complicating responsibility assignment; recovery requires emergency re-manifesting, which adds 6–24 hours.

**Detection:**
- Expected handoff scan missing more than 4 hours after the scheduled handoff time: `SELECT * FROM handoff_events WHERE expected_at < NOW() - INTERVAL '4 hours' AND actual_scan_at IS NULL`.
- No tracking events received from the receiving carrier's API for the AWB within 6 hours of scheduled handoff.
- Alert: `handoff_overdue{outgoing_carrier="lufthansa_cargo", receiving_carrier="dhl"}` fires → P1 notification to carrier ops team.
- Carrier API status for the receiving carrier's AWB remains `not_found` or `pre-advice_only` beyond handoff window.

**Mitigation:**
- Raise `HANDOFF_FAILURE` exception on the shipment record immediately on detection; assign to carrier operations team.
- Contact both carriers simultaneously: confirm whether the outgoing carrier presented the shipment to the transfer hub and whether the receiving carrier has located it.
- If parcel is physically at the hub and receiving carrier simply failed to collect, arrange emergency collection with a 4-hour SLA.
- If parcel cannot be located at the expected transfer hub, escalate to an all-points investigation across both carriers' hub networks.
- Notify consignee and shipper of delay with updated EDD as soon as the parcel is physically confirmed located.

**Recovery:**
- Arrange emergency re-manifest on the receiving carrier (or alternative carrier) from the transfer hub location.
- Assign priority routing for the remainder of the journey to compensate for lost time.
- Update shipment record with actual handoff timestamp and new routing plan; recalculate EDD.
- Publish `shipment.exception_resolved.v1` once the receiving carrier confirms custody with a scan.
- Initiate carrier dispute process to determine responsibility and financial liability for the SLA breach.

**Prevention:**
- Confirmed handoff scan requirement: the outgoing carrier must record a `HANDOFF_OUT` scan and the receiving carrier must record a `HANDOFF_IN` scan; both are required for the handoff record to be marked complete.
- Automated handoff monitoring: a job checks every 30 minutes for overdue handoffs and escalates progressively (alert → phone call to hub manager → emergency pickup dispatch).
- Contractual handoff SLAs with defined acceptance windows (e.g., receiving carrier must collect within 2 hours of AWB availability at transfer hub); financial penalty for breach.
- Dedicated account contacts at both carriers for emergency handoff resolution during business hours and on-call numbers outside business hours.

---

### 5. International Carrier Rejection

**Failure Mode:** An international carrier rejects a shipment at the origin facility before loading. Rejection reasons include: incorrect or missing commercial invoice, prohibited goods declaration, HS code mismatch, shipper not approved for the destination country, or weight/dimension discrepancy versus the booking declaration.

**Impact:** Shipment cannot depart on the planned flight or vehicle; SLA clock was running from booking confirmation but delivery is now impossible on the original timeline; shipper must remediate the documentation issue before rebooting the shipment; consignee receives no further movement updates; if the rejection is for prohibited goods, regulatory reporting may be required.

**Detection:**
- Carrier rejection scan recorded at origin facility: exception code `REJECTED_AT_ORIGIN` with rejection reason code from the carrier.
- Carrier API returns `booking_rejected` or `shipment_refused` status code when the system queries the AWB status.
- Alert: `carrier_rejection_rate{carrier="dhl", origin_country="IN", destination_country="US"}` exceeds baseline → P2 notification to carrier operations and compliance team.
- Carrier sends electronic rejection notice (EDI 315 / IATA CIMP) parsed by the carrier integration service.

**Mitigation:**
- Return the shipment to the shipper's collection address or hold at origin carrier facility; record physical custody location.
- Send immediate rejection notice to shipper with: rejection reason code, carrier reference, required remediation action (e.g., correct HS code, provide Form E, re-weigh), and deadline to remediate before return shipping is initiated.
- Pause SLA clock with reason `CARRIER_REJECTION_PENDING_REMEDIATION`; SLA does not accrue against the operator during shipper remediation window (configurable, default 48 hours).
- Publish `shipment.exception_detected.v1` with reason `CARRIER_REJECTION`; notify compliance team if rejection reason involves prohibited or restricted goods.

**Recovery:**
- Shipper corrects the identified documentation issue (amends commercial invoice, corrects HS code, obtains missing certificate).
- Shipper re-submits the booking; a new AWB is issued by the carrier; the original AWB is voided.
- System creates a new shipment record linked to the original via `replacement_for` field; preserves audit trail.
- New booking goes through full pre-departure validation checks before submission to carrier.
- Once new shipment departs, close original exception record with `resolution: REBOOKED_WITH_CORRECTIONS`.

**Prevention:**
- Pre-shipment document validation pipeline: at booking time, validate commercial invoice line items against declared shipment contents; check HS codes against the destination country's restricted/prohibited goods list; verify shipper is registered for the destination country.
- HS code verification: integrate with customs tariff databases (e.g., WCO HS nomenclature, country-specific tariff schedules); flag any HS codes that attract additional documentation requirements for the destination.
- Carrier-specific country restrictions database: maintain a rules engine encoding each carrier's country-specific restrictions (e.g., carrier A does not accept batteries on certain routes, carrier B requires additional documentation for pharmaceuticals to certain countries).
- Weight and dimension verification at pickup: driver app captures actual weight/dimensions on collection and compares with booking declaration; discrepancies flagged before parcel enters the carrier network.

---
