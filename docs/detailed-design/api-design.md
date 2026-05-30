# API Design — Logistics Tracking System

## Table of Contents
1. [Design Principles](#1-design-principles)
2. [Base URL & Versioning](#2-base-url--versioning)
3. [Request / Response Envelope](#3-request--response-envelope)
4. [Pagination](#4-pagination)
5. [Idempotency](#5-idempotency)
6. [Rate Limiting](#6-rate-limiting)
7. [Endpoint Reference](#7-endpoint-reference)
   - 7.1 Shipments API
   - 7.2 Public Tracking API
   - 7.3 Carriers API
   - 7.4 Drivers API
   - 7.5 Vehicles API
   - 7.6 Routes API
   - 7.7 Proofs of Delivery API
   - 7.8 Exceptions API
   - 7.9 Customs API
   - 7.10 Returns API
   - 7.11 Webhooks API
   - 7.12 Reports API
8. [Request / Response Examples](#8-request--response-examples)
9. [Error Code Catalogue](#9-error-code-catalogue)
10. [Authorization Matrix](#10-authorization-matrix)
11. [Webhook Payload Contract](#11-webhook-payload-contract)

---

## 1. Design Principles

| Principle | Implementation |
|-----------|----------------|
| **REST semantics** | Resources are nouns; HTTP verbs carry intent (`GET`, `POST`, `PUT`, `DELETE`). Collections use plural nouns (e.g., `/shipments`, `/drivers`). |
| **Versioning** | URL path prefix `/v1/`; `Accept: application/vnd.logistics.v1+json` header also accepted. Breaking changes bump the major version; non-breaking additions ship within the same version. |
| **Idempotency** | All mutating requests accept `Idempotency-Key: <uuid-v4>` header. Replays return the cached response for 24 hours without re-executing the operation. Keys are scoped to `(shipper_id, route, key)`. |
| **Error envelope** | All errors use `{ "error": { "code": "...", "message": "...", "details": [...] } }`. Error codes follow `LOG-NNNN` format. |
| **Pagination** | Cursor-based via `next_cursor` / `prev_cursor`. Supports `page` + `per_page` for small collections. Stable sort on `created_at:desc` by default. |
| **Rate limiting** | Token-bucket per endpoint group + per API key. Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`. Exceeding limits returns `429 Too Many Requests`. |
| **HATEOAS (light)** | Resources include `_links` object with common transitions (self, cancel, book, track). |
| **Content negotiation** | `Content-Type: application/json` for all JSON endpoints; `multipart/form-data` for POD uploads. |
| **Tracing** | All responses carry `X-Request-Id` (UUID) and `X-Trace-Id` (W3C `traceparent` format) for distributed tracing. |
| **Deprecation** | `Sunset` header + `Deprecation` header on deprecated endpoints with migration guide URL. |

---

## 2. Base URL & Versioning

```
https://api.logistics.io/v1/{resource}
```

**Authentication methods accepted on every protected endpoint:**

| Method | Header | Notes |
|--------|--------|-------|
| Bearer JWT | `Authorization: Bearer <token>` | Short-lived (1 hour); issued by `/v1/auth/token` |
| API Key | `X-API-Key: <key>` | Long-lived; scoped to a single shipper account |

The public tracking endpoint (`GET /v1/track/{tracking_number}`) requires no authentication.

---

## 3. Request / Response Envelope

### Success (single resource)
```json
{
  "data": { "...": "..." },
  "_links": {
    "self":   { "href": "/v1/shipments/shp_01HXZ3K" },
    "track":  { "href": "/v1/track/1Z999AA10123456784" },
    "cancel": { "href": "/v1/shipments/shp_01HXZ3K/cancel", "method": "POST" }
  },
  "meta": {
    "request_id": "req_01HXZ3K",
    "timestamp":  "2025-01-15T10:30:00Z"
  }
}
```

### Success (list)
```json
{
  "data": [ { "...": "..." }, { "...": "..." } ],
  "pagination": {
    "total":       843,
    "per_page":    20,
    "next_cursor": "eyJpZCI6InNocF8wNTAifQ==",
    "prev_cursor": null
  },
  "meta": { "request_id": "req_01HXZ3K", "timestamp": "2025-01-15T10:30:00Z" }
}
```

### Error
```json
{
  "error": {
    "code":    "LOG-1001",
    "message": "Shipment not found.",
    "details": [
      { "field": "shipment_id", "issue": "no_record", "value": "shp_UNKNOWN" }
    ],
    "doc_url": "https://docs.logistics.io/errors/LOG-1001"
  },
  "meta": { "request_id": "req_01HXZ3K", "timestamp": "2025-01-15T10:30:00Z" }
}
```

---

## 4. Pagination

| Parameter  | Type   | Default          | Description |
|------------|--------|------------------|-------------|
| `cursor`   | string | —                | Opaque base64 cursor from previous response |
| `page`     | int    | 1                | 1-based page number (collections < 10 000 only) |
| `per_page` | int    | 20               | Items per page; max 100 |
| `sort`     | string | `created_at:desc`| `field:asc\|desc`; allowed fields vary per resource |
| `status`   | string | —                | Filter by shipment/resource status |
| `date_from`| string | —                | ISO 8601 lower bound on `created_at` |
| `date_to`  | string | —                | ISO 8601 upper bound on `created_at` |

Cursor tokens are opaque base64-encoded JSON and should never be constructed client-side. They encode the last-seen primary key and sort column value to guarantee stable pagination even when records are inserted between pages.

---

## 5. Idempotency

Clients **MUST** send `Idempotency-Key: <uuid-v4>` for all `POST`, `PUT`, and `DELETE` requests. Keys are stored for **24 hours** and scoped to `(shipper_id, endpoint_path, key)`. A replayed request with the same key returns the original HTTP status code and response body without re-executing the operation.

If the key exists but the request body differs, the API returns `409 Conflict` with error code `LOG-1002` (or equivalent) and a description of the mismatch. This prevents accidental double-submission with different payloads.

**Header example:**
```http
POST /v1/shipments
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

---

## 6. Rate Limiting

| Endpoint Group | Limit (per minute) | Burst | Scope |
|----------------|--------------------|-------|-------|
| Shipments (read) | 600 req/min | 100 | Per API key |
| Shipments (write) | 120 req/min | 30 | Per API key |
| Public Tracking | 300 req/min | 60 | Per IP |
| Carrier Allocation | 60 req/min | 10 | Per API key |
| Driver & Vehicle | 300 req/min | 60 | Per API key |
| GPS / Telemetry | 3 600 req/min | 600 | Per vehicle/device |
| POD Upload | 120 req/min | 20 | Per driver |
| Exceptions | 120 req/min | 20 | Per API key |
| Customs | 60 req/min | 10 | Per API key |
| Returns | 120 req/min | 20 | Per API key |
| Webhooks (mgmt) | 60 req/min | 10 | Per API key |
| Reports | 30 req/min | 5 | Per API key |

---

## 7. Endpoint Reference

### 7.1 Shipments API

Base: `/v1/shipments`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `POST`   | `/v1/shipments` | Create a new shipment in Draft status | Bearer / API Key |
| `GET`    | `/v1/shipments` | List shipments with filters (status, carrier_id, date_from, date_to, shipper_id) | Bearer / API Key |
| `GET`    | `/v1/shipments/{id}` | Get full shipment detail with embedded tracking events summary | Bearer / API Key |
| `PUT`    | `/v1/shipments/{id}` | Update shipment metadata before booking (Draft/Confirmed only) | Bearer / API Key |
| `DELETE` | `/v1/shipments/{id}` | Cancel/delete a Draft shipment permanently | Bearer / API Key |
| `GET`    | `/v1/shipments/{id}/tracking-events` | List all tracking events for a shipment (paginated, chronological) | Bearer / API Key |
| `POST`   | `/v1/shipments/{id}/book` | Book shipment with carrier; triggers carrier API call; returns AWB and label URL | Bearer / API Key |
| `POST`   | `/v1/shipments/{id}/cancel` | Cancel a booked or confirmed shipment; notifies carrier | Bearer / API Key |
| `POST`   | `/v1/shipments/{id}/hold` | Place a booked shipment on administrative hold | Bearer / API Key |

---

### 7.2 Public Tracking API

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET` | `/v1/track/{tracking_number}` | Public endpoint — returns sanitized tracking info and events timeline. No authentication required. Returns HTTP 404 with LOG-1011 if tracking number is unknown. | **None** |

---

### 7.3 Carriers API

Base: `/v1/carriers`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET`  | `/v1/carriers` | List active carriers; filter by `capabilities` (e.g., `hazmat`, `international`) | Bearer / API Key |
| `GET`  | `/v1/carriers/{id}` | Carrier detail including supported service types and integration status | Bearer / API Key |
| `GET`  | `/v1/carriers/{id}/services` | List carrier service offerings with transit days, weight limits, and rate basis | Bearer / API Key |
| `POST` | `/v1/carriers/{id}/allocate` | Force-allocate a specific shipment to this carrier (admin only) | Bearer (admin) |

---

### 7.4 Drivers API

Base: `/v1/drivers`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET`  | `/v1/drivers` | List drivers; filter by `status` (`active`, `off_duty`, `on_leave`), `carrier_id` | Bearer / API Key |
| `POST` | `/v1/drivers` | Create a new driver profile linked to a carrier | Bearer (admin) |
| `GET`  | `/v1/drivers/{id}` | Driver detail including current GPS coordinates and assigned vehicle | Bearer / API Key |
| `PUT`  | `/v1/drivers/{id}` | Update driver profile fields (license, certifications, contact info) | Bearer (admin) |

---

### 7.5 Vehicles API

Base: `/v1/vehicles`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET`  | `/v1/vehicles` | List fleet vehicles; filter by `status`, `carrier_id`, `vehicle_type` | Bearer / API Key |
| `POST` | `/v1/vehicles` | Register a new vehicle in the fleet | Bearer (admin) |
| `GET`  | `/v1/vehicles/{id}` | Vehicle detail with GPS breadcrumb history (last 24 hours by default) | Bearer / API Key |

---

### 7.6 Routes API

Base: `/v1/routes`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET`  | `/v1/routes` | List routes; filter by `planned_date`, `driver_id`, `status` | Bearer / API Key |
| `POST` | `/v1/routes/optimize` | Request route optimization. Input: `driver_id`, `shipment_ids[]`. Response: optimized waypoint sequence with ETAs. | Bearer (admin) |

---

### 7.7 Proofs of Delivery API

Base: `/v1/proofs-of-delivery`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET`  | `/v1/proofs-of-delivery` | List PODs; filter by `shipper_id`, `date_from`, `date_to`, `delivery_type` | Bearer / API Key |
| `POST` | `/v1/proofs-of-delivery` | Submit POD from driver app (`multipart/form-data`; fields: `shipment_id`, `recipient_name`, `signature` file, `photo` file) | Bearer (driver) |
| `GET`  | `/v1/proofs-of-delivery/{id}` | POD detail including pre-signed signature and photo download URLs | Bearer / API Key |

---

### 7.8 Exceptions API

Base: `/v1/exceptions`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET`  | `/v1/exceptions` | List exceptions; filter by `severity` (`critical`, `high`, `medium`, `low`), `status`, `shipment_id` | Bearer / API Key |
| `POST` | `/v1/exceptions` | Manually raise an exception against a shipment | Bearer / API Key |
| `GET`  | `/v1/exceptions/{id}` | Exception detail with full resolution history and escalation timeline | Bearer / API Key |
| `PUT`  | `/v1/exceptions/{id}/resolve` | Resolve an open exception; requires `resolution_type` and `notes` in body | Bearer / API Key |

---

### 7.9 Customs API

Base: `/v1/customs`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET`  | `/v1/customs` | List customs declarations; filter by `shipment_id`, `customs_status`, `destination_country` | Bearer / API Key |
| `POST` | `/v1/customs` | Submit a new customs declaration with line items, HS codes, and declared values | Bearer / API Key |
| `GET`  | `/v1/customs/{id}` | Declaration detail with full line items, duties/taxes, and clearance status | Bearer / API Key |

---

### 7.10 Returns API

Base: `/v1/returns`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `POST` | `/v1/returns` | Initiate a return shipment; generates RMA code and return label | Bearer / API Key |
| `GET`  | `/v1/returns` | List return shipments; filter by `return_status`, `shipper_id`, `date_from` | Bearer / API Key |
| `GET`  | `/v1/returns/{id}` | Return detail including RMA code, QC status, and refund trigger timestamp | Bearer / API Key |

---

### 7.11 Webhooks API

Base: `/v1/webhooks`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `POST`   | `/v1/webhooks` | Register a new webhook subscription with endpoint URL and event type filter | Bearer / API Key |
| `GET`    | `/v1/webhooks` | List webhook subscriptions for the authenticated shipper | Bearer / API Key |
| `DELETE` | `/v1/webhooks/{id}` | Delete a webhook subscription | Bearer / API Key |

---

### 7.12 Reports API

Base: `/v1/reports`

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET` | `/v1/reports/delivery-performance` | Delivery rate, on-time percentage, and average delivery days; filter by `date_from`, `date_to`, `carrier_id` | Bearer / API Key |
| `GET` | `/v1/reports/carrier-performance` | Per-carrier metrics: transit time, exception rate, POD compliance | Bearer / API Key |
| `GET` | `/v1/reports/exceptions` | Exception counts by type, severity distribution, and average resolution time | Bearer / API Key |

---

## 8. Request / Response Examples

### 8.1 Create Shipment

**Request**
```http
POST /v1/shipments
Content-Type: application/json
Authorization: Bearer <token>
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000

{
  "shipper_id": "shpr_01J3KMAB",
  "consignee": {
    "name": "Jane Doe",
    "company": "Acme Corp",
    "email": "jane@acme.com",
    "phone": "+1-555-0100",
    "address_line1": "742 Evergreen Terrace",
    "address_line2": "Suite 4B",
    "city": "Springfield",
    "state": "IL",
    "postal_code": "62704",
    "country_iso2": "US",
    "delivery_instructions": "Leave at front desk",
    "is_residential": false
  },
  "service_level": "EXPRESS_48H",
  "items": [
    {
      "description": "Laptop Computer",
      "hs_code": "8471300000",
      "quantity": 2,
      "unit_value": 1200.00,
      "weight_kg": 2.1,
      "country_of_origin": "CN",
      "hazmat_class": null,
      "is_restricted": false
    }
  ],
  "declared_value": 2400.00,
  "currency": "USD",
  "special_instructions": "Fragile — handle with care",
  "requires_signature": true,
  "requires_photo": false,
  "insurance_value": 2400.00,
  "is_international": false,
  "idempotency_key": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response** `201 Created`
```json
{
  "data": {
    "shipment_id": "shp_01J3KM99",
    "reference_number": "LOG-2025-000842",
    "status": "draft",
    "service_level": "EXPRESS_48H",
    "shipper_id": "shpr_01J3KMAB",
    "consignee_id": "cns_09ZAQ1",
    "piece_count": 2,
    "total_weight_kg": 4.2,
    "declared_value": 2400.00,
    "currency": "USD",
    "sla_delivery_date": null,
    "estimated_delivery_date": null,
    "created_at": "2025-01-15T10:30:00Z",
    "updated_at": "2025-01-15T10:30:00Z"
  },
  "_links": {
    "self":   { "href": "/v1/shipments/shp_01J3KM99" },
    "book":   { "href": "/v1/shipments/shp_01J3KM99/book", "method": "POST" },
    "cancel": { "href": "/v1/shipments/shp_01J3KM99/cancel", "method": "POST" }
  },
  "meta": { "request_id": "req_01HXZ3K", "timestamp": "2025-01-15T10:30:00Z" }
}
```

---

### 8.2 Book Shipment

**Request**
```http
POST /v1/shipments/shp_01J3KM99/book
Content-Type: application/json
Authorization: Bearer <token>
Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7

{
  "carrier_id": "car_FEDEX01",
  "service_id": "svc_FX_PRIORITY",
  "preferred_pickup_date": "2025-01-16",
  "notes": "Call shipper 30 minutes before pickup"
}
```

**Response** `200 OK`
```json
{
  "data": {
    "shipment_id": "shp_01J3KM99",
    "status": "confirmed",
    "allocation": {
      "allocation_id": "alloc_ZZ1001",
      "carrier_id": "car_FEDEX01",
      "carrier_name": "FedEx",
      "service_code": "PRIORITY_OVERNIGHT",
      "awb_number": "7489 2345 6789",
      "booking_reference": "FX-20250116-843221",
      "label_url": "https://labels.logistics.io/v1/labels/alloc_ZZ1001.pdf",
      "label_format": "PDF",
      "estimated_delivery_date": "2025-01-17T18:00:00Z",
      "sla_delivery_date": "2025-01-17T23:59:59Z",
      "confirmed_at": "2025-01-15T10:31:00Z"
    }
  },
  "_links": {
    "self":            { "href": "/v1/shipments/shp_01J3KM99" },
    "tracking-events": { "href": "/v1/shipments/shp_01J3KM99/tracking-events" },
    "track":           { "href": "/v1/track/7489234567890" }
  },
  "meta": { "request_id": "req_02ABY4L", "timestamp": "2025-01-15T10:31:00Z" }
}
```

---

### 8.3 Public Tracking (No Auth)

**Request**
```http
GET /v1/track/7489234567890
```

**Response** `200 OK`
```json
{
  "data": {
    "tracking_number": "7489234567890",
    "carrier": "FedEx",
    "service": "Priority Overnight",
    "status": "in_transit",
    "origin": {
      "city": "Chicago",
      "state": "IL",
      "country": "US"
    },
    "destination": {
      "city": "Springfield",
      "state": "IL",
      "country": "US"
    },
    "estimated_delivery_date": "2025-01-17T18:00:00Z",
    "sla_delivery_date": "2025-01-17T23:59:59Z",
    "events": [
      {
        "event_type": "DEPARTED_FACILITY",
        "event_code": "DF",
        "description": "Package departed FedEx facility",
        "location": "Chicago, IL, US",
        "occurred_at": "2025-01-16T08:45:00Z",
        "is_milestone": true
      },
      {
        "event_type": "ARRIVED_AT_FACILITY",
        "event_code": "AF",
        "description": "Package arrived at FedEx facility",
        "location": "Chicago, IL, US",
        "occurred_at": "2025-01-16T06:30:00Z",
        "is_milestone": true
      },
      {
        "event_type": "PICKED_UP",
        "event_code": "PU",
        "description": "Package picked up by FedEx courier",
        "location": "Chicago, IL, US",
        "occurred_at": "2025-01-16T04:15:00Z",
        "is_milestone": true
      }
    ]
  },
  "meta": { "request_id": "req_03CDE5M", "timestamp": "2025-01-16T09:00:00Z" }
}
```

---

### 8.4 Submit Proof of Delivery (Multipart)

**Request**
```http
POST /v1/proofs-of-delivery
Content-Type: multipart/form-data; boundary=---FormBoundary7MA4YWxkTrZu0gW
Authorization: Bearer <driver_token>
Idempotency-Key: a1b2c3d4-e5f6-7890-abcd-ef1234567890

-----FormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="shipment_id"

shp_01J3KM99
-----FormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="recipient_name"

Jane Doe
-----FormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="recipient_relationship"

self
-----FormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="delivery_type"

signature_and_photo
-----FormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="geo_lat"

39.7817
-----FormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="geo_lon"

-89.6501
-----FormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="signature"; filename="sig.png"
Content-Type: image/png

<binary data>
-----FormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="photo"; filename="photo.jpg"
Content-Type: image/jpeg

<binary data>
-----FormBoundary7MA4YWxkTrZu0gW--
```

**Response** `201 Created`
```json
{
  "data": {
    "pod_id": "pod_99XYZ1",
    "shipment_id": "shp_01J3KM99",
    "delivery_type": "signature_and_photo",
    "delivered_at": "2025-01-17T14:22:00Z",
    "recipient_name": "Jane Doe",
    "recipient_relationship": "self",
    "signature_url": "https://storage.logistics.io/pods/pod_99XYZ1/signature.png?sig=eyJ...",
    "photo_url": "https://storage.logistics.io/pods/pod_99XYZ1/photo.jpg?sig=eyJ...",
    "geo_lat": 39.7817,
    "geo_lon": -89.6501,
    "is_offline_capture": false,
    "created_at": "2025-01-17T14:22:05Z"
  },
  "_links": {
    "self":     { "href": "/v1/proofs-of-delivery/pod_99XYZ1" },
    "shipment": { "href": "/v1/shipments/shp_01J3KM99" }
  },
  "meta": { "request_id": "req_04DEF6N", "timestamp": "2025-01-17T14:22:05Z" }
}
```

---

### 8.5 Request Route Optimization

**Request**
```http
POST /v1/routes/optimize
Content-Type: application/json
Authorization: Bearer <token>
Idempotency-Key: b2c3d4e5-f6a7-8901-bcde-f01234567890

{
  "driver_id": "drv_AAB001",
  "vehicle_id": "veh_TRK009",
  "hub_id": "hub_CHI01",
  "planned_date": "2025-01-17",
  "shipment_ids": [
    "shp_01J3KM99",
    "shp_01J3KM88",
    "shp_01J3KM77",
    "shp_01J3KM66"
  ],
  "optimization_objective": "minimize_time",
  "start_location": {
    "lat": 41.8781,
    "lon": -87.6298
  }
}
```

**Response** `200 OK`
```json
{
  "data": {
    "route_id": "rte_20250117_001",
    "driver_id": "drv_AAB001",
    "vehicle_id": "veh_TRK009",
    "planned_date": "2025-01-17",
    "optimization_score": 94.7,
    "total_stops": 4,
    "estimated_total_distance_km": 38.4,
    "estimated_completion_time": "2025-01-17T17:30:00Z",
    "waypoints": [
      {
        "sequence": 1,
        "shipment_id": "shp_01J3KM77",
        "address": "123 Oak St, Chicago, IL 60601",
        "arrival_eta": "2025-01-17T09:15:00Z",
        "departure_eta": "2025-01-17T09:25:00Z"
      },
      {
        "sequence": 2,
        "shipment_id": "shp_01J3KM88",
        "address": "456 Elm Ave, Chicago, IL 60602",
        "arrival_eta": "2025-01-17T10:05:00Z",
        "departure_eta": "2025-01-17T10:20:00Z"
      },
      {
        "sequence": 3,
        "shipment_id": "shp_01J3KM66",
        "address": "789 Pine Rd, Chicago, IL 60603",
        "arrival_eta": "2025-01-17T11:30:00Z",
        "departure_eta": "2025-01-17T11:45:00Z"
      },
      {
        "sequence": 4,
        "shipment_id": "shp_01J3KM99",
        "address": "742 Evergreen Terrace, Springfield, IL 62704",
        "arrival_eta": "2025-01-17T14:00:00Z",
        "departure_eta": "2025-01-17T14:15:00Z"
      }
    ]
  },
  "meta": { "request_id": "req_05EFG7O", "timestamp": "2025-01-17T08:00:00Z" }
}
```

---

### 8.6 Submit Customs Declaration

**Request**
```http
POST /v1/customs
Content-Type: application/json
Authorization: Bearer <token>
Idempotency-Key: c3d4e5f6-a7b8-9012-cdef-012345678901

{
  "shipment_id": "shp_INTL001",
  "declaration_type": "CN22",
  "origin_country": "CN",
  "destination_country": "US",
  "declared_value": 2400.00,
  "currency": "USD",
  "incoterms": "DDP",
  "lines": [
    {
      "hs_code": "8471300000",
      "description": "Laptop Computer",
      "quantity": 2,
      "unit_value": 1200.00,
      "total_value": 2400.00,
      "country_of_origin": "CN",
      "weight_kg": 4.2
    }
  ]
}
```

**Response** `201 Created`
```json
{
  "data": {
    "declaration_id": "cus_ZZ9901",
    "shipment_id": "shp_INTL001",
    "declaration_type": "CN22",
    "customs_status": "submitted",
    "declared_value": 2400.00,
    "currency": "USD",
    "incoterms": "DDP",
    "submitted_at": "2025-01-15T11:00:00Z",
    "cleared_at": null,
    "duties_amount": null,
    "taxes_amount": null
  },
  "_links": {
    "self":     { "href": "/v1/customs/cus_ZZ9901" },
    "shipment": { "href": "/v1/shipments/shp_INTL001" }
  },
  "meta": { "request_id": "req_06FGH8P", "timestamp": "2025-01-15T11:00:00Z" }
}
```

---

### 8.7 Raise Exception

**Request**
```http
POST /v1/exceptions
Content-Type: application/json
Authorization: Bearer <token>
Idempotency-Key: d4e5f6a7-b8c9-0123-def0-123456789012

{
  "shipment_id": "shp_01J3KM99",
  "exception_type": "DELIVERY_FAILED",
  "severity": "high",
  "description": "Customer not at address. No safe location for parcel. Buzzer code refused.",
  "detected_by": "driver_app"
}
```

**Response** `201 Created`
```json
{
  "data": {
    "exception_id": "exc_AAB001",
    "shipment_id": "shp_01J3KM99",
    "exception_type": "DELIVERY_FAILED",
    "severity": "high",
    "status": "open",
    "description": "Customer not at address. No safe location for parcel. Buzzer code refused.",
    "detected_at": "2025-01-17T14:30:00Z",
    "detected_by": "driver_app",
    "sla_breach": false,
    "auto_escalated": false
  },
  "_links": {
    "self":    { "href": "/v1/exceptions/exc_AAB001" },
    "resolve": { "href": "/v1/exceptions/exc_AAB001/resolve", "method": "PUT" }
  },
  "meta": { "request_id": "req_07GHI9Q", "timestamp": "2025-01-17T14:30:00Z" }
}
```

---

### 8.8 Initiate Return

**Request**
```http
POST /v1/returns
Content-Type: application/json
Authorization: Bearer <token>
Idempotency-Key: e5f6a7b8-c9d0-1234-ef01-234567890123

{
  "original_shipment_id": "shp_01J3KM99",
  "return_reason": "CUSTOMER_CHANGED_MIND",
  "return_reason_notes": "Customer no longer needs the item.",
  "carrier_id": "car_FEDEX01"
}
```

**Response** `201 Created`
```json
{
  "data": {
    "return_id": "ret_BB2002",
    "original_shipment_id": "shp_01J3KM99",
    "rma_code": "RMA-2025-000099",
    "return_status": "pending_pickup",
    "return_reason": "CUSTOMER_CHANGED_MIND",
    "initiated_by": "shipper",
    "initiated_at": "2025-01-18T09:00:00Z",
    "return_label_url": "https://labels.logistics.io/v1/labels/ret_BB2002.pdf",
    "carrier_allocation_id": "alloc_RET001"
  },
  "_links": {
    "self":             { "href": "/v1/returns/ret_BB2002" },
    "original_shipment":{ "href": "/v1/shipments/shp_01J3KM99" }
  },
  "meta": { "request_id": "req_08HIJ0R", "timestamp": "2025-01-18T09:00:00Z" }
}
```

---

### 8.9 Register Webhook

**Request**
```http
POST /v1/webhooks
Content-Type: application/json
Authorization: Bearer <token>
Idempotency-Key: f6a7b8c9-d0e1-2345-f012-345678901234

{
  "endpoint_url": "https://hooks.acme.com/logistics",
  "event_types": [
    "shipment.status_changed",
    "shipment.delivered",
    "shipment.exception_raised",
    "pod.submitted"
  ],
  "description": "Acme order management integration"
}
```

**Response** `201 Created`
```json
{
  "data": {
    "webhook_id": "wh_CC3003",
    "endpoint_url": "https://hooks.acme.com/logistics",
    "event_types": [
      "shipment.status_changed",
      "shipment.delivered",
      "shipment.exception_raised",
      "pod.submitted"
    ],
    "status": "active",
    "secret": "whsec_Tz9x8mK3pL2nQ7rV0yA4bC1dE6fG5hI",
    "failure_count": 0,
    "created_at": "2025-01-15T10:00:00Z"
  },
  "meta": { "request_id": "req_09IJK1S", "timestamp": "2025-01-15T10:00:00Z" }
}
```

---

### 8.10 Delivery Performance Report

**Request**
```http
GET /v1/reports/delivery-performance?date_from=2025-01-01&date_to=2025-01-31&carrier_id=car_FEDEX01
Authorization: Bearer <token>
```

**Response** `200 OK`
```json
{
  "data": {
    "period_from": "2025-01-01",
    "period_to": "2025-01-31",
    "carrier_id": "car_FEDEX01",
    "carrier_name": "FedEx",
    "total_shipments": 1243,
    "delivered": 1195,
    "failed_delivery": 38,
    "returned_to_sender": 10,
    "delivery_rate_pct": 96.14,
    "on_time_pct": 93.72,
    "avg_delivery_days": 1.8,
    "first_attempt_success_rate_pct": 89.45,
    "exception_rate_pct": 3.06,
    "sla_breach_count": 31,
    "avg_exception_resolution_hours": 6.4
  },
  "meta": { "request_id": "req_10JKL2T", "timestamp": "2025-02-01T00:00:00Z" }
}
```

---

## 9. Error Code Catalogue

| Code | HTTP Status | Constant | Description | Retry? |
|------|-------------|----------|-------------|--------|
| `LOG-1001` | 404 | `SHIPMENT_NOT_FOUND` | The requested shipment ID does not exist or is not accessible to this caller | No |
| `LOG-1002` | 409 | `SHIPMENT_ALREADY_BOOKED` | Shipment has already been booked with a carrier and cannot be modified in this way | No |
| `LOG-1003` | 503 | `CARRIER_UNAVAILABLE` | The selected carrier's API is currently unreachable or returning errors | Yes (exponential) |
| `LOG-1004` | 429 | `CARRIER_CAPACITY_EXCEEDED` | Carrier has reached capacity for this service lane; try again or select alternate carrier | After delay |
| `LOG-1005` | 422 | `INVALID_HS_CODE` | The provided HS/commodity code does not exist in the harmonized tariff schedule | No |
| `LOG-1006` | 422 | `HAZMAT_CARRIER_REQUIRED` | Shipment contains hazardous materials but no hazmat-certified carrier was selected | No |
| `LOG-1007` | 422 | `WEIGHT_LIMIT_EXCEEDED` | Total shipment weight exceeds the selected carrier service's maximum allowed weight | No |
| `LOG-1008` | 422 | `CUSTOMS_DECLARATION_INCOMPLETE` | International shipment is missing required customs declaration fields (HS code, declared value, or country of origin) | No |
| `LOG-1009` | 409 | `MAX_ATTEMPTS_REACHED` | Maximum delivery attempts have been reached for this shipment | No |
| `LOG-1010` | 409 | `POD_ALREADY_EXISTS` | A proof of delivery has already been submitted for this shipment | No |
| `LOG-1011` | 404 | `INVALID_TRACKING_NUMBER` | The tracking number does not match any shipment in the system | No |
| `LOG-1012` | 404 | `EXCEPTION_NOT_FOUND` | The requested exception ID does not exist | No |
| `LOG-1013` | 403 | `RETURN_AUTH_REQUIRED` | Initiating a return requires explicit authorization from the original shipper | No |
| `LOG-1014` | 429 | `GPS_UPDATE_RATE_EXCEEDED` | GPS breadcrumb updates are being sent faster than the allowed rate for this device | After delay |
| `LOG-1015` | 422 | `GEOFENCE_INVALID_POLYGON` | The submitted geofence polygon is not a valid closed polygon (insufficient vertices or self-intersecting) | No |
| `LOG-1016` | 502 | `CARRIER_API_ERROR` | The carrier API returned an unexpected error response; request may be retried | Yes (exponential) |
| `LOG-1017` | 500 | `LABEL_GENERATION_FAILED` | Shipping label could not be generated; carrier booking may have succeeded — check allocation status before retrying | Yes (idempotent) |
| `LOG-1018` | 500 | `POD_UPLOAD_FAILED` | Proof of delivery file upload to object storage failed; retry with the same idempotency key | Yes |
| `LOG-1019` | 422 | `WEBHOOK_ENDPOINT_UNREACHABLE` | The provided webhook endpoint URL returned an error during validation ping | No |
| `LOG-1020` | 422 | `SLA_CLASS_INVALID` | The specified SLA service level class does not exist or is not available for this origin–destination pair | No |

---

## 10. Authorization Matrix

Roles: `platform:admin`, `shipper:admin`, `shipper:user`, `carrier:admin`, `carrier:dispatcher`, `driver`, `auditor`, `public`

| Endpoint Group | platform:admin | shipper:admin | shipper:user | carrier:dispatcher | driver | public |
|----------------|:-:|:-:|:-:|:-:|:-:|:-:|
| Shipments (read) | ✅ | own | own | allocated | own route | — |
| Shipments (write/book) | ✅ | ✅ | ✅ | — | — | — |
| Shipments (cancel) | ✅ | ✅ | — | — | — | — |
| Public Tracking | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Carriers (read) | ✅ | ✅ | ✅ | ✅ | — | — |
| Carriers (allocate) | ✅ | — | — | — | — | — |
| Drivers (read) | ✅ | — | — | ✅ | own | — |
| Drivers (write) | ✅ | — | — | ✅ | — | — |
| Vehicles (read) | ✅ | — | — | ✅ | own | — |
| Vehicles (write) | ✅ | — | — | ✅ | — | — |
| Routes (read) | ✅ | — | — | ✅ | own | — |
| Routes (optimize) | ✅ | — | — | ✅ | — | — |
| POD (submit) | ✅ | — | — | — | ✅ | — |
| POD (read) | ✅ | own | own | allocated | own | — |
| Exceptions (read) | ✅ | own | own | allocated | — | — |
| Exceptions (write/resolve) | ✅ | ✅ | — | ✅ | — | — |
| Customs (read/write) | ✅ | own | own | — | — | — |
| Returns (read/write) | ✅ | own | own | — | — | — |
| Webhooks (manage) | ✅ | ✅ | — | — | — | — |
| Reports | ✅ | own | — | own | — | — |

---

## 11. Webhook Payload Contract

All outbound webhooks share this envelope:

```json
{
  "webhook_id":   "wh_CC3003",
  "delivery_id":  "dlv_AB1234",
  "event_type":   "shipment.status_changed",
  "shipper_id":   "shpr_01J3KMAB",
  "occurred_at":  "2025-01-16T08:45:00Z",
  "payload": {
    "shipment_id":      "shp_01J3KM99",
    "reference_number": "LOG-2025-000842",
    "old_status":       "confirmed",
    "new_status":       "in_transit",
    "tracking_number":  "7489234567890",
    "carrier":          "FedEx",
    "location": {
      "city":    "Chicago",
      "state":   "IL",
      "country": "US"
    },
    "occurred_at": "2025-01-16T08:45:00Z"
  },
  "signature":   "sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "retry_count": 0
}
```

**Signature verification:** `HMAC-SHA256` over `delivery_id + "." + occurred_at + "." + raw_body` using the webhook secret returned at registration. Verify before processing every delivery.

**Delivery guarantee:** At-least-once. Idempotent handlers are required on the consumer side. Retries use exponential back-off: 5 s → 30 s → 5 min → 30 min → 2 h (5 attempts total). After exhaustion the subscription `failure_count` is incremented and status transitions to `failing`.

| Event Type | Trigger |
|------------|---------|
| `shipment.created` | New shipment written to Draft status |
| `shipment.status_changed` | Any shipment status transition |
| `shipment.booked` | Carrier booking confirmed with AWB issued |
| `shipment.out_for_delivery` | Shipment loaded on last-mile run |
| `shipment.delivered` | Proof of delivery accepted |
| `shipment.exception_raised` | Exception detected on shipment |
| `shipment.exception_resolved` | Exception marked resolved |
| `shipment.cancelled` | Shipment cancelled by shipper or carrier |
| `pod.submitted` | Proof of delivery uploaded by driver |
| `return.initiated` | Return shipment created with RMA |
| `return.received` | Return parcel received at warehouse |
| `customs.cleared` | Customs declaration cleared |
| `customs.held` | Customs declaration placed on hold |
| `exception.escalated` | Exception auto-escalated due to SLA breach |
| `carrier.capacity_warning` | Carrier capacity nearing threshold for a lane |
