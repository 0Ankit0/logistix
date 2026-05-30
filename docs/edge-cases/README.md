# Edge Cases — Logistics Tracking System

Operational runbooks covering failure scenarios, mitigation logic, recovery procedures, and preventive design patterns across all functional domains of the Logistics Tracking System.

---

## Overview

This directory contains edge-case documentation organised by functional domain. Each file covers a set of failure scenarios that engineers and operations teams will encounter in production. Every case follows a consistent six-section format so on-call responders can triage and act without reading background context.

Each runbook entry answers six questions:
1. **What breaks?** (Failure Mode)
2. **Who and what is hurt?** (Impact)
3. **How do we know it broke?** (Detection)
4. **How do we limit damage right now?** (Mitigation)
5. **How do we get back to normal?** (Recovery)
6. **How do we stop it happening again?** (Prevention)

---

## Table of Contents

| # | File | Domain | Cases |
|---|------|--------|-------|
| 1 | [shipment-exceptions.md](./shipment-exceptions.md) | Shipment Exceptions | 5 |
| 2 | [carrier-failover.md](./carrier-failover.md) | Carrier Failover | 5 |
| 3 | [last-mile-delivery.md](./last-mile-delivery.md) | Last-Mile Delivery | 5 |
| 4 | [proof-of-delivery.md](./proof-of-delivery.md) | Proof of Delivery | 5 |
| 5 | [api-and-ui.md](./api-and-ui.md) | API & UI | 5 |
| 6 | [security-and-compliance.md](./security-and-compliance.md) | Security & Compliance | 5 |
| 7 | [operations.md](./operations.md) | Platform Operations | 5 |

---

## Severity Classification Guide

Use the highest applicable severity level when classifying a case.

| Severity | Label | Criteria | Response SLA | Example |
|----------|-------|----------|--------------|---------|
| **P0** | Critical | Production data loss, complete service outage, active security breach, or mass SLA breach affecting >10% of daily volume | Immediate (< 15 min) | Kafka broker down, GPS data store unavailable, carrier credential leak |
| **P1** | High | Significant degradation of a core workflow, SLA breach for a defined customer segment, or compliance risk | < 1 hour | Carrier API circuit open, POD upload pipeline stalled, GDPR erasure overdue |
| **P2** | Medium | Isolated failures affecting a minority of shipments, manual workaround exists, no data loss | < 4 hours | Single driver GPS spoofing, one carrier capacity exceeded, webhook DLQ growing |
| **P3** | Low | Cosmetic issues, rare edge cases with negligible customer impact, or proactive improvements | Next sprint | Address confidence score borderline, API version deprecation warning |

---

## How to Use These Runbooks

### During an Incident
1. Identify the functional domain from the alert or ticket description.
2. Open the corresponding file from the table above.
3. Locate the matching case by name or keyword.
4. Follow **Mitigation** steps immediately to stop customer harm.
5. Follow **Recovery** steps to restore normal operation.
6. File a post-mortem linking the case and documenting deviations.

### Before Going On-Call
- Read through all cases in your domain files.
- Verify that all **Detection** signals (metrics, alerts, log queries) are configured in your monitoring stack.
- Confirm you have access to the tools referenced in **Recovery** steps (carrier portals, DB consoles, Kafka admin UI).

### Keeping Runbooks Current
- Any production incident that does not match an existing case → create a new case entry in the correct file.
- After a post-mortem, update the **Prevention** section of the relevant case with any new design changes agreed.
- Review all runbooks quarterly; archive cases that no longer apply after architecture changes.

---

## Edge Case Summary Table

| Category | File | Case Count | Max Severity |
|----------|------|-----------|--------------|
| Shipment Exceptions | shipment-exceptions.md | 5 | P1 (High) |
| Carrier Failover | carrier-failover.md | 5 | P1 (High) |
| Last-Mile Delivery | last-mile-delivery.md | 5 | P1 (High) |
| Proof of Delivery | proof-of-delivery.md | 5 | P1 (High) |
| API & UI | api-and-ui.md | 5 | P1 (High) |
| Security & Compliance | security-and-compliance.md | 5 | P0 (Critical) |
| Platform Operations | operations.md | 5 | P0 (Critical) |

---

## Standard Case Format

Every edge case in this directory uses the following structure:

```
### [Case Name]

**Failure Mode:** What breaks and how

**Impact:** Business and technical consequences

**Detection:** Metrics, alerts, log queries, and thresholds that surface the issue

**Mitigation:** Immediate steps to reduce harm while the issue is active

**Recovery:** Steps to fully restore normal operation

**Prevention:** Design patterns, processes, or tooling that eliminate or reduce recurrence
```

---

## Related Documentation

- `README.md` at the system root — architecture overview and technology choices
- Individual domain design docs inside each feature folder
- Monitoring dashboards: link to your observability platform per domain
- On-call escalation matrix: link to your incident management tool
