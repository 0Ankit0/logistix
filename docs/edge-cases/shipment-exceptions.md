# Shipment Exceptions

Edge cases covering physical and operational failures that affect a shipment after it has been accepted into the network. These scenarios span damage, loss, misrouting, address failures, and environmental disruptions.

**Severity range:** P1 (High) — P2 (Medium)

---

## Cases

1. [Package Damaged in Transit](#1-package-damaged-in-transit)
2. [Lost Shipment Detection](#2-lost-shipment-detection)
3. [Misrouted Package](#3-misrouted-package)
4. [Address Correction Failure](#4-address-correction-failure)
5. [Weather-Related Delay Cascade](#5-weather-related-delay-cascade)

---

### 1. Package Damaged in Transit

**Failure Mode:** A parcel is physically damaged during transport — crushed in a sort machine, dropped from a loading bay, or compressed by improper stacking. The outer packaging or inner contents are compromised before reaching the consignee.

**Impact:** Customer complaint and potential churn; insurance claim against the carrier or shipper's cargo insurance; contractual carrier dispute process initiated; SLA breach if the delivery window is missed during investigation; replacement cost and redelivery cost if shipper elects to reship. Photographs entered as evidence can delay settlement for weeks.

**Detection:**
- Driver or hub agent selects `DAMAGED` exception code at scan time; photo evidence attached to the scan record.
- Consignee reports damage at doorstep delivery; POD record updated with `condition: DAMAGED` flag.
- Photo analysis pipeline (if ML-enabled) flags low-quality packaging or visible damage in delivery photo.
- Alert: `exception_type=DAMAGED` event published to `shipment.exception_detected.v1` topic; ops dashboard counter increments.

**Mitigation:**
- Immediately transition shipment state to `Exception` with reason `DAMAGED`; suspend further routing until investigation scope is clear.
- Capture all available photo evidence from driver app and hub scan stations; attach to exception record.
- Notify shipper via webhook `shipment.exception_detected.v1` within 3 minutes of exception creation; include damage description, location, and carrier reference.
- If contents are visibly hazardous or biohazardous, escalate to carrier safety team and halt all movement.
- Do not attempt redelivery of a known damaged parcel without shipper approval.

**Recovery:**
- Shipper decides whether to (a) reship a replacement, (b) attempt delivery as-is with consignee consent, or (c) return to sender.
- File carrier damage claim with all photo evidence and declared value; carrier SLA for claim acknowledgement is typically 5 business days.
- If redelivery approved: create new delivery instruction; update EDD; notify consignee.
- Close exception record with `resolution: DAMAGE_CLAIM_FILED` or `RESHIPPED`; publish `shipment.exception_resolved.v1`.
- Reconcile financial settlement after carrier claim outcome is known.

**Prevention:**
- Enforce packaging guidelines at booking: weight/dimension limits per service class; minimum packaging standards documented and enforced via API validation.
- Fragile item flag on label triggers handling instructions at every sort station.
- Shock indicator stickers (impact labels) on declared fragile items provide physical evidence of mishandling.
- Carrier SLA contracts include damage rate thresholds; exceed threshold triggers performance review and potential carrier swap.

---

### 2. Lost Shipment Detection

**Failure Mode:** A parcel stops generating tracking scan events for more than 48 hours with no delivery confirmation and no exception recorded. The parcel's last known location is a hub or line-haul vehicle. The parcel cannot be physically located.

**Impact:** Direct financial loss equal to declared value plus replacement and redelivery costs; customer churn if resolution is slow; SLA breach (typically >2 days past EDD by detection time); carrier insurance claim; potential regulatory reporting if high-value or hazardous goods are involved.

**Detection:**
- Scheduled job runs every 30 minutes: `SELECT shipment_id FROM shipments WHERE status = 'InTransit' AND last_scan_at < NOW() - INTERVAL '48 hours' AND NOT EXISTS (SELECT 1 FROM delivery_attempts WHERE shipment_id = shipments.id)`.
- Alert: `shipment_no_scan_48h` fires in Prometheus when the above count exceeds 0; routes to P1 on-call.
- GPS breadcrumb gap >6 hours on a moving vehicle triggers a separate `vehicle_gps_gap` alert that can precede the 48-hour threshold.
- Carrier API polled every 4 hours; carrier-side `MISSING` or `INVESTIGATION_OPEN` status codes surfaced immediately.

**Mitigation:**
- Auto-raise `LOST` exception on the shipment record; assign to carrier investigation queue.
- Notify shipper via webhook within 5 minutes of exception creation: include last scan location, time, and assigned investigation reference number.
- Hold financial settlement until investigation concludes.
- Suppress further automated EDD recalculations; set public tracking status to `Delayed — Under Investigation`.
- If GPS tracking shows the parcel was on a specific vehicle, dispatch ops team to inspect that vehicle.

**Recovery:**
- Submit carrier tracer request via carrier portal or API; reference last scan event and AWB.
- Carrier investigation SLA: acknowledgement within 24 h, resolution within 7 business days (enforce contractually).
- If parcel located: resume normal routing; update EDD; notify consignee.
- If confirmed unrecoverable: transition state to `Lost`; file cargo insurance claim; initiate replacement shipment workflow if shipper opts for that.
- Close investigation record; publish `shipment.closed` with `reason: LOST_CONFIRMED` or `LOST_RECOVERED`.

**Prevention:**
- GPS tracking unit on all line-haul vehicles; mandatory heartbeat every 10 minutes.
- Mandatory custody scan at every hub touchpoint (inbound + outbound); scan gap > configured threshold raises automated alert.
- Carrier SLA contract includes maximum acceptable lost-shipment rate; exceed threshold triggers contractual remedy.
- High-value shipments (>$500 declared) require dual-scan handoff (both outgoing and receiving hub scan) before custody transfer is considered complete.

---

### 3. Misrouted Package

**Failure Mode:** A parcel is scanned onto the wrong sort lane at a hub and placed on a vehicle or line-haul flight heading to an incorrect destination city or region. The error may not be detected until the parcel arrives at the wrong hub and is scanned on inbound.

**Impact:** Delivery delay of 1–3 days depending on how far off-route the parcel travels; SLA breach for time-sensitive service classes (express, overnight); consignee dissatisfaction; additional carrier cost for corrective routing; EDD must be recalculated and communicated.

**Detection:**
- Hub inbound scan: system compares scan location against expected next-hub in routing plan; mismatch raises `MISROUTED` exception automatically.
- Geofence alert: if GPS on vehicle shows vehicle travelling toward a region inconsistent with shipment destination, alert fires before the vehicle departs the hub area.
- Alert: `routing_mismatch_rate` metric rises above baseline; Prometheus rule triggers P2 notification to hub ops.
- Log query: `event_type=HUB_SCAN AND hub_id != expected_hub_id` in the event stream.

**Mitigation:**
- Immediately flag shipment as `MISROUTED`; prevent further routing instructions from being issued on the incorrect path.
- If parcel has not yet departed the wrong hub, intercept physically and place in correct sort lane.
- If parcel already departed, issue corrective routing instruction to the incorrect destination hub to reroute on next available service.
- Notify shipper and consignee immediately of revised EDD; use templated `misroute_delay` notification with new expected date.
- Record the specific sort lane and hub operator in the exception audit log for investigation.

**Recovery:**
- Create corrected routing plan from current actual location to destination; insert new hub waypoints.
- Update EDD in system using recalculation engine; surface new date on public tracking page.
- Publish `shipment.exception_resolved.v1` once parcel arrives at the correct hub and is confirmed on the right routing plan.
- If SLA breach occurs: trigger automated SLA credit calculation for eligible service classes.
- Conduct hub investigation to identify whether the mis-sort was human error or scanner/sort machine fault.

**Prevention:**
- Sort lane verification scan: scanner beeps differently (audible tone + visual indicator) if the barcode does not match the assigned lane manifest.
- Automated sort lane assignment: label barcode contains embedded routing zone; sort machine reads zone and directs to correct lane without operator decision.
- Supervisor spot-check: random 5% of parcels re-verified against manifest before vehicle departure.
- Hub dashboards show real-time sort error rate; threshold alert when rate exceeds 0.1%.

---

### 4. Address Correction Failure

**Failure Mode:** A shipment is created with an address that fails geocoding validation (low confidence score, unrecognised street, incomplete postcode), but the booking proceeds because validation was not enforced as a hard block. The driver cannot locate the address on the delivery attempt, resulting in a failed delivery.

**Impact:** One failed delivery attempt wasted (driver time, fuel, vehicle capacity); customer frustration; potential return-to-sender if address cannot be corrected in time; additional cost to redeliver once address is corrected; in some cases the parcel cycles through multiple failed attempts before returning.

**Detection:**
- Address validation API (Google Maps / HERE) returns confidence score < 95% at booking time; warning flag set on shipment record.
- Driver selects `address_not_found` or `invalid_address` failure reason on delivery attempt in the driver app.
- Alert: `low_confidence_address_delivery_failure_rate` exceeds threshold — indicates booking API is not enforcing minimum confidence.
- Log: `address_confidence_score < 0.95 AND delivery_attempt.outcome = FAILED` correlation query.

**Mitigation:**
- On first failed delivery attempt with `address_not_found` reason: automatically trigger customer service outreach to consignee for address confirmation; do not wait for driver to report manually.
- Hold shipment at local depot or hub; do not schedule second delivery attempt until address is confirmed.
- Suspend EDD public display; show `Address Under Review` status on tracking page.
- If consignee unreachable within 48 hours, notify shipper to provide alternate delivery instructions.

**Recovery:**
- Consignee or shipper provides corrected address; address validation API confirms >95% confidence on new address.
- Update `delivery_address` on shipment record with audit log entry recording who changed the address and when.
- Schedule new delivery attempt with corrected address; recalculate EDD.
- Publish `shipment.exception_resolved.v1` with resolution `ADDRESS_CORRECTED`; notify consignee of new delivery window.
- If address cannot be corrected within 5 business days, initiate return-to-sender workflow.

**Prevention:**
- Hard block at booking API: address validation must return confidence ≥ 95% before shipment is confirmed; return HTTP 422 with structured error directing user to correct the address field.
- Address correction UI: when confidence is 80–94%, surface a Google Maps autocomplete suggestion and require the user to confirm the corrected address before proceeding.
- Periodic batch validation: run geocoding on all confirmed-but-not-yet-picked-up shipments nightly; flag any that have drifted to low confidence (e.g., due to geocoder model updates).
- Driver app: display full address with map pin at route start so driver can visually confirm before setting out.

---

### 5. Weather-Related Delay Cascade

**Failure Mode:** Severe weather — hurricane, blizzard, widespread flooding, or volcanic ash cloud — grounds air freight, blocks road networks, or forces carrier operational suspensions across an entire region. Hundreds or thousands of in-transit and scheduled shipments are simultaneously affected. Normal EDD calculations become invalid.

**Impact:** Mass SLA breach event affecting potentially thousands of shipments simultaneously; thousands of customer notifications required within a short window; carrier operations partially or fully suspended for the affected region; upstream shipper order fulfilment disrupted; force majeure clause may apply, relieving contractual SLA penalties but not waiving customer communication obligations.

**Detection:**
- Weather API integration (e.g., Tomorrow.io, OpenWeatherMap) publishes `weather_alert` events when storm severity ≥ threshold for regions intersecting active shipment routes.
- Carrier APIs begin returning bulk `WEATHER_DELAY` or `SERVICE_SUSPENDED` status codes for affected lanes; carrier webhook pushes delay notifications.
- GPS telemetry: large cluster of vehicles showing zero movement in affected region for >2 hours during operating hours.
- Alert: `bulk_edd_recalculation_trigger` fires when >500 shipments simultaneously require EDD update from a single cause code.

**Mitigation:**
- Activate force majeure flag on all affected shipments: `force_majeure: true`; pauses SLA clock automatically — SLA breach penalties do not accrue during force majeure.
- Run bulk EDD recalculation job using weather clearance forecast + estimated backlog recovery time; update all affected shipments.
- Send mass customer notifications using weather delay template (pre-approved, avoids manual copy for each customer); batch send via notification service with rate limiting to avoid downstream SMTP/SMS capacity exhaustion.
- Halt new booking commitments to affected lanes until carrier confirms resumption capacity.
- Alert shipper accounts with high volume in the affected region via account-level notification (not per-shipment).

**Recovery:**
- Monitor weather API and carrier status endpoint for clearance signal.
- On clearance: release force majeure flag; re-prioritise delivery queue based on EDD urgency (oldest EDD first).
- Coordinate with carriers on backlog processing plan; get written capacity commitment for the recovery window.
- Resume new bookings to affected lanes once carrier confirms operational capacity.
- Run post-event SLA reconciliation: identify which breaches qualify for force majeure exemption vs. which pre-dated the weather event and were already in breach.
- Publish incident summary to shipper accounts and customer service portal.

**Prevention:**
- Weather monitoring integration with automated route-risk scoring; proactively reroute around forecast disruptions 24–48 hours in advance where possible.
- Backup carrier contracts for critical lanes: if primary carrier suspends, secondary carrier can absorb volume (capacity pre-agreed in contract).
- Resilient hub network design: avoid single-hub dependency for entire regional distribution; traffic can divert through an adjacent hub.
- Force majeure clause explicitly defined in shipper contracts with clear activation criteria (carrier suspension notice or government advisory) to avoid disputes.

---
