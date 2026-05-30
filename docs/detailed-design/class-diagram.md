# Class Diagram

This document contains all class diagrams for the Logistics Tracking System, organised by bounded context. Each diagram covers the aggregate roots, entities, value objects, interfaces, and supporting types for its domain. Mermaid source is the canonical, version-controlled artifact; render in any Mermaid-compatible viewer (GitHub, GitLab, Notion, VS Code extension).

---

## 1. Shipment Aggregate Class Diagram

The `Shipment` aggregate is the core domain object. It owns the chain of custody from booking through final delivery, including items, parcels, addresses, and declared value.

```mermaid
classDiagram
    direction TB

    class Shipment {
        +UUID shipmentId
        +String referenceNumber
        +ShipmentStatus status
        +ServiceLevel serviceLevel
        +Address originAddress
        +Address destinationAddress
        +Money declaredValue
        +Weight totalWeight
        +List~ShipmentItem~ items
        +List~Parcel~ parcels
        +DateTime createdAt
        +DateTime updatedAt
        +String tenantId
        +String createdByUserId
        +create(CreateShipmentCommand) Shipment
        +book(BookingRequest) CarrierAllocation
        +cancel(String reason) void
        +hold(String reason) void
        +updateStatus(ShipmentStatus newStatus) void
        +addItem(ShipmentItem item) void
        +addParcel(Parcel parcel) void
        +calculateTotalWeight() Weight
        +calculateTotalValue() Money
        +isHazmat() boolean
        +requiresCustomsDeclaration() boolean
    }

    class ShipmentItem {
        +UUID itemId
        +String description
        +HSCode hsCode
        +int quantity
        +Money unitValue
        +Weight weight
        +CountryCode countryOfOrigin
        +HazmatClass hazmatClass
        +String skuCode
        +String commodityType
        +boolean isFragile
        +boolean isPerishable
        +totalValue() Money
        +totalWeight() Weight
        +validate() ValidationResult
    }

    class Parcel {
        +UUID parcelId
        +TrackingNumber trackingNumber
        +Barcode barcode
        +Dimensions dimensions
        +Weight weight
        +ParcelStatus status
        +String currentLocation
        +DateTime lastScannedAt
        +List~ScanEvent~ scanHistory
        +scan(ScanEvent event) void
        +updateLocation(GeoPoint location) void
        +markDelivered(PODRecord pod) void
        +markException(ExceptionType type) void
        +getDimWeight() Weight
        +getChargeableWeight() Weight
    }

    class Address {
        <<ValueObject>>
        +String line1
        +String line2
        +String city
        +String state
        +String postalCode
        +CountryCode country
        +String phone
        +String contactName
        +boolean isResidential
        +boolean isValidated
        +GeoPoint coordinates
        +validate() ValidationResult
        +toFormattedString() String
        +isInternational(Address other) boolean
    }

    class Money {
        <<ValueObject>>
        +BigDecimal amount
        +Currency currency
        +add(Money other) Money
        +subtract(Money other) Money
        +multiply(BigDecimal factor) Money
        +convertTo(Currency target, ExchangeRate rate) Money
        +isZero() boolean
        +isNegative() boolean
        +compareTo(Money other) int
    }

    class Weight {
        <<ValueObject>>
        +double value
        +WeightUnit unit
        +toKilograms() Weight
        +toPounds() Weight
        +add(Weight other) Weight
        +compareTo(Weight other) int
    }

    class Dimensions {
        <<ValueObject>>
        +double lengthCm
        +double widthCm
        +double heightCm
        +calculateVolume() double
        +calculateDimWeight(double divisor) Weight
        +longestSide() double
        +girth() double
    }

    class ScanEvent {
        <<ValueObject>>
        +UUID scanId
        +ScanType type
        +String location
        +GeoPoint coordinates
        +String scannedBy
        +DateTime occurredAt
        +String deviceId
        +String notes
    }

    class PODRecord {
        +UUID podId
        +UUID parcelId
        +UUID deliveryAttemptId
        +String recipientName
        +String signatureImageUrl
        +String photoUrl
        +DateTime capturedAt
        +GeoPoint captureLocation
        +boolean isContactless
        +String safeDropLocation
        +validate() ValidationResult
    }

    class TrackingNumber {
        <<ValueObject>>
        +String value
        +CarrierCode carrier
        +String format
        +validate() boolean
        +toBarcode() Barcode
    }

    class HSCode {
        <<ValueObject>>
        +String code
        +String description
        +double dutyRatePercent
        +validate() boolean
        +isRestricted(CountryCode destination) boolean
    }

    Shipment "1" *-- "1..*" ShipmentItem : contains
    Shipment "1" *-- "1..*" Parcel : contains
    Shipment "1" *-- "2" Address : origin / destination
    Shipment "1" *-- "1" Money : declaredValue
    Shipment "1" *-- "1" Weight : totalWeight
    Parcel "1" *-- "1" Dimensions : dimensions
    Parcel "1" *-- "1" Weight : weight
    Parcel "1" *-- "1" TrackingNumber : trackingNumber
    Parcel "1" *-- "0..*" ScanEvent : scanHistory
    Parcel "1" *-- "0..1" PODRecord : pod
    ShipmentItem "1" *-- "1" Money : unitValue
    ShipmentItem "1" *-- "1" Weight : weight
    ShipmentItem "1" *-- "0..1" HSCode : hsCode
```

### Shipment Aggregate — Key Design Decisions

| Decision | Rationale |
|---|---|
| `Parcel` owns `ScanEvent` history | Scan events belong to the physical parcel, not the logical shipment; enables multi-parcel shipments to track independently |
| `Address` is a value object | Addresses have no identity—equality is structural; copying is preferred over referencing |
| `Money` carries `Currency` | Prevents implicit currency arithmetic; all cross-currency operations must supply an `ExchangeRate` |
| `getDimWeight()` on `Parcel` | Dimensional weight calculation is carrier-specific; the `divisor` param allows FedEx (139), UPS (139), DHL (5000) logic |
| `requiresCustomsDeclaration()` on `Shipment` | Centralises the rule: any item with an `HSCode` and `countryOfOrigin` different from the destination country triggers customs |

---

## 2. Carrier Integration Class Diagram

The carrier integration layer uses the Adapter pattern to present a uniform interface to the rest of the system, regardless of the underlying carrier API protocol (REST, XML/SOAP, proprietary).

```mermaid
classDiagram
    direction TB

    class ICarrierAdapter {
        <<interface>>
        +book(BookingRequest) BookingResponse
        +track(String trackingNumber) TrackingResponse
        +cancel(String awbNumber) CancellationResponse
        +getRates(RateRequest) List~RateQuote~
        +validateAddress(Address address) AddressValidationResult
        +getServiceLevels(CountryCode origin, CountryCode dest) List~ServiceLevel~
    }

    class FedExAdapter {
        -FedExClient httpClient
        -FedExCredentials credentials
        -CircuitBreaker circuitBreaker
        +book(BookingRequest) BookingResponse
        +track(String trackingNumber) TrackingResponse
        +cancel(String awbNumber) CancellationResponse
        +getRates(RateRequest) List~RateQuote~
        +validateAddress(Address address) AddressValidationResult
        +getServiceLevels(CountryCode origin, CountryCode dest) List~ServiceLevel~
        -mapToFedExRequest(BookingRequest) FedExShipRequest
        -mapFromFedExResponse(FedExShipResponse) BookingResponse
        -refreshToken() void
    }

    class UPSAdapter {
        -UPSRestClient httpClient
        -UPSCredentials credentials
        -CircuitBreaker circuitBreaker
        +book(BookingRequest) BookingResponse
        +track(String trackingNumber) TrackingResponse
        +cancel(String awbNumber) CancellationResponse
        +getRates(RateRequest) List~RateQuote~
        +validateAddress(Address address) AddressValidationResult
        +getServiceLevels(CountryCode origin, CountryCode dest) List~ServiceLevel~
        -mapToUPSShipmentRequest(BookingRequest) UPSShipRequest
        -parseUPSTrackingXml(String xml) TrackingResponse
    }

    class DHLAdapter {
        -DHLExpressClient httpClient
        -DHLCredentials credentials
        -CircuitBreaker circuitBreaker
        +book(BookingRequest) BookingResponse
        +track(String trackingNumber) TrackingResponse
        +cancel(String awbNumber) CancellationResponse
        +getRates(RateRequest) List~RateQuote~
        +validateAddress(Address address) AddressValidationResult
        +getServiceLevels(CountryCode origin, CountryCode dest) List~ServiceLevel~
        -mapToDHLShipmentRequest(BookingRequest) DHLShipmentRequest
        -parseDHLWebhookPayload(String json) TrackingEvent
    }

    class USPSAdapter {
        -USPSWebToolsClient httpClient
        -USPSCredentials credentials
        -CircuitBreaker circuitBreaker
        +book(BookingRequest) BookingResponse
        +track(String trackingNumber) TrackingResponse
        +cancel(String awbNumber) CancellationResponse
        +getRates(RateRequest) List~RateQuote~
        +validateAddress(Address address) AddressValidationResult
        +getServiceLevels(CountryCode origin, CountryCode dest) List~ServiceLevel~
        -buildUSPSXmlRequest(BookingRequest) String
        -parseUSPSXmlResponse(String xml) BookingResponse
    }

    class CarrierAdapterFactory {
        -Map~String, ICarrierAdapter~ adapterRegistry
        +getAdapter(String carrierId) ICarrierAdapter
        +registerAdapter(String carrierId, ICarrierAdapter adapter) void
        +getSupportedCarriers() List~String~
    }

    class CarrierAllocation {
        +UUID allocationId
        +UUID shipmentId
        +UUID carrierId
        +String awbNumber
        +String labelUrl
        +String labelFormat
        +AllocationStatus status
        +Money allocatedRate
        +ServiceLevel allocatedService
        +DateTime confirmedAt
        +DateTime expiresAt
        +String cancellationReason
        +allocate(BookingResponse response) void
        +cancel(String reason) void
        +isExpired() boolean
        +regenerateLabel() String
    }

    class BookingRequest {
        <<ValueObject>>
        +UUID shipmentId
        +Address origin
        +Address destination
        +Weight weight
        +Dimensions dimensions
        +ServiceLevel service
        +List~ShipmentItem~ items
        +Money declaredValue
        +boolean isResidentialDelivery
        +boolean requiresSignature
        +String specialInstructions
        +DateTime requestedPickupDate
    }

    class BookingResponse {
        <<ValueObject>>
        +String awbNumber
        +String labelUrl
        +String labelFormat
        +Date estimatedDelivery
        +BigDecimal cost
        +Currency currency
        +String carrierReference
        +List~String~ warnings
        +boolean isSuccess
        +String errorCode
        +String errorMessage
    }

    class RateRequest {
        <<ValueObject>>
        +Address origin
        +Address destination
        +Weight weight
        +Dimensions dimensions
        +DateTime shipDate
        +List~ServiceLevel~ requestedServices
    }

    class RateQuote {
        <<ValueObject>>
        +String carrierId
        +ServiceLevel service
        +Money rate
        +DateTime estimatedDelivery
        +String transitDays
        +List~Surcharge~ surcharges
        +Money totalRate()
    }

    ICarrierAdapter <|.. FedExAdapter : implements
    ICarrierAdapter <|.. UPSAdapter : implements
    ICarrierAdapter <|.. DHLAdapter : implements
    ICarrierAdapter <|.. USPSAdapter : implements
    CarrierAdapterFactory --> ICarrierAdapter : creates
    CarrierAllocation --> BookingResponse : populated from
    FedExAdapter ..> BookingRequest : uses
    FedExAdapter ..> BookingResponse : returns
    UPSAdapter ..> RateRequest : uses
    UPSAdapter ..> RateQuote : returns
```

### Carrier Integration — Key Design Decisions

| Decision | Rationale |
|---|---|
| `ICarrierAdapter` interface with `validateAddress` | Address validation is carrier-specific; FedEx has better US coverage, DHL better for international |
| `CircuitBreaker` per adapter | Carrier API outages should not cascade; each carrier isolates its own failure domain |
| `CarrierAdapterFactory` with registry | Allows dynamic registration of new regional carriers without code changes to the selection service |
| `labelUrl` on `BookingResponse` | Labels are stored in S3; the adapter uploads during booking so the URL is immediately available |
| `RateQuote` includes `surcharges` | Fuel surcharge, residential surcharge, and remote area fees must be itemised for cost transparency |

---

## 3. Route Optimization Class Diagram

The route optimizer manages last-mile delivery routing, taking driver availability, vehicle capacity, time windows, and real-time traffic into account.

```mermaid
classDiagram
    direction TB

    class Route {
        +UUID routeId
        +UUID driverId
        +UUID vehicleId
        +Date plannedDate
        +List~Waypoint~ waypoints
        +RouteStatus status
        +double totalDistanceKm
        +int estimatedDurationMinutes
        +DateTime startedAt
        +DateTime completedAt
        +addWaypoint(Waypoint waypoint) void
        +removeWaypoint(UUID waypointId) void
        +optimize() void
        +reoptimize(Waypoint newStop) void
        +complete() void
        +getTotalStops() int
        +getCompletedStops() int
        +getProgressPercent() double
        +getNextWaypoint() Waypoint
    }

    class Waypoint {
        +UUID waypointId
        +int sequence
        +Address address
        +UUID shipmentId
        +UUID parcelId
        +WaypointType type
        +DateTime arrivalEta
        +DateTime departureEta
        +DateTime actualArrival
        +DateTime actualDeparture
        +TimeWindow deliveryWindow
        +WaypointStatus status
        +boolean requiresSignature
        +String accessInstructions
        +arrive(DateTime actualTime) void
        +depart(DateTime actualTime) void
        +fail(String reason) void
        +reschedule(DateTime newEta) void
        +isLate() boolean
        +getSlaBreachRisk() RiskLevel
    }

    class RouteOptimizer {
        -DistanceMatrixClient distanceClient
        -TrafficDataService trafficService
        -OptimizationAlgorithm algorithm
        +optimize(UUID driverId, List~Shipment~ shipments, OptimizationConstraints constraints) Route
        +reoptimize(Route existing, Waypoint newStop) Route
        +estimateRouteMetrics(List~Waypoint~ waypoints) RouteMetrics
        -buildDistanceMatrix(List~Address~ addresses) double[][]
        -applyVehicleCapacityConstraint(List~Waypoint~ stops, Vehicle vehicle) List~Waypoint~
        -applyTimeWindowConstraints(List~Waypoint~ stops) List~Waypoint~
        -runTspSolver(double[][] distMatrix, List~Waypoint~ stops) List~Waypoint~
    }

    class OptimizationConstraints {
        <<ValueObject>>
        +DateTime startTime
        +DateTime endTime
        +int maxStops
        +double maxDistanceKm
        +Weight maxLoadWeight
        +double maxLoadVolumeCbm
        +boolean requireSignatureByDefault
        +boolean avoidTolls
        +boolean avoidHighways
        +int serviceDurationMinutes
    }

    class RouteMetrics {
        <<ValueObject>>
        +double totalDistanceKm
        +int estimatedDurationMinutes
        +int stopCount
        +double fuelCostEstimate
        +int slaAtRiskCount
    }

    class TimeWindow {
        <<ValueObject>>
        +DateTime from
        +DateTime to
        +boolean isFlexible
        +boolean contains(DateTime dt) boolean
        +overlapsWith(TimeWindow other) boolean
    }

    class Vehicle {
        +UUID vehicleId
        +String licensePlate
        +VehicleType type
        +Weight maxPayloadWeight
        +double maxPayloadVolumeCbm
        +boolean isRefrigerated
        +boolean canCarryHazmat
        +FuelType fuelType
        +isAvailable(DateTime from, DateTime to) boolean
    }

    class ShipmentException {
        +UUID exceptionId
        +UUID shipmentId
        +ExceptionType type
        +Severity severity
        +ExceptionStatus status
        +String description
        +String assignedTo
        +DateTime detectedAt
        +DateTime slaBreachAt
        +DateTime resolvedAt
        +List~ExceptionResolution~ resolutions
        +resolve(ExceptionResolution resolution) void
        +escalate(String escalateTo) void
        +addResolution(ExceptionResolution res) void
        +isBreached() boolean
        +getRemainingSlaDuration() Duration
    }

    class ExceptionResolution {
        +UUID resolutionId
        +UUID exceptionId
        +ResolutionType type
        +String notes
        +String resolvedBy
        +DateTime resolvedAt
        +boolean isAutoResolved
        +Map~String, String~ metadata
    }

    Route "1" *-- "1..*" Waypoint : ordered stops
    Route --> Vehicle : assigned to
    RouteOptimizer --> Route : produces
    RouteOptimizer ..> OptimizationConstraints : uses
    RouteOptimizer ..> RouteMetrics : returns
    Waypoint *-- TimeWindow : delivery window
    ShipmentException "1" *-- "0..*" ExceptionResolution : resolution history
```

### Route Optimization — Key Design Decisions

| Decision | Rationale |
|---|---|
| `reoptimize` on `RouteOptimizer` | During active delivery runs, new urgent stops must be inserted without discarding all prior optimisation |
| `TimeWindow` as value object on `Waypoint` | Customer-promised delivery windows are immutable once confirmed; violations trigger SLA breach logic |
| `getSlaBreachRisk()` on `Waypoint` | Gives dispatchers a real-time risk signal before a breach actually occurs |
| `ExceptionResolution` history | Full audit trail of who attempted what resolution, when, and whether it was automated or manual |
| `Severity` on `ShipmentException` | Drives escalation routing: LOW auto-notifies, MEDIUM alerts supervisor, HIGH/CRITICAL pages on-call |

---

## 4. Enumerations and Supporting Types

```mermaid
classDiagram
    direction LR

    class ShipmentStatus {
        <<enumeration>>
        DRAFT
        CONFIRMED
        PICKUP_SCHEDULED
        PICKED_UP
        IN_TRANSIT
        OUT_FOR_DELIVERY
        DELIVERED
        EXCEPTION
        RETURNED_TO_SENDER
        CANCELLED
        LOST
    }

    class ServiceLevel {
        <<enumeration>>
        ECONOMY
        STANDARD
        EXPRESS
        OVERNIGHT
        SAME_DAY
        FREIGHT
    }

    class ParcelStatus {
        <<enumeration>>
        CREATED
        LABELLED
        PICKED_UP
        IN_TRANSIT
        AT_FACILITY
        OUT_FOR_DELIVERY
        DELIVERED
        EXCEPTION
        RETURNED
    }

    class ExceptionType {
        <<enumeration>>
        DELAY
        DAMAGE
        LOST
        ADDRESS_ISSUE
        CUSTOMS_HOLD
        REFUSED_BY_RECIPIENT
        WEATHER_DELAY
        CARRIER_DELAY
        VEHICLE_BREAKDOWN
    }

    class Severity {
        <<enumeration>>
        LOW
        MEDIUM
        HIGH
        CRITICAL
    }

    class WaypointType {
        <<enumeration>>
        PICKUP
        DELIVERY
        HUB_TRANSFER
        RETURN
    }

    class ResolutionType {
        <<enumeration>>
        REROUTED
        REDELIVERY_SCHEDULED
        RETURNED_TO_SENDER
        ADDRESS_CORRECTED
        CLAIM_FILED
        CARRIER_CONTACTED
        CUSTOMS_CLEARED
        CANCELLED
    }

    class HazmatClass {
        <<enumeration>>
        CLASS_1_EXPLOSIVES
        CLASS_2_GASES
        CLASS_3_FLAMMABLE_LIQUIDS
        CLASS_4_FLAMMABLE_SOLIDS
        CLASS_5_OXIDISING
        CLASS_6_TOXIC
        CLASS_7_RADIOACTIVE
        CLASS_8_CORROSIVE
        CLASS_9_MISC
        NONE
    }
```

---

## Design Principles Applied

1. **Aggregate boundaries enforce invariants** — `Shipment` is the only entry point for modifying items and parcels; direct `ShipmentItem` or `Parcel` mutations are prohibited outside the aggregate root.
2. **Value objects are immutable** — `Address`, `Money`, `Weight`, `Dimensions`, `TimeWindow` have no setters; operations return new instances.
3. **Interfaces decouple carrier implementations** — `ICarrierAdapter` allows swapping, mocking, or adding carriers without changes to the booking service.
4. **Rich domain model** — Business logic (`isHazmat()`, `requiresCustomsDeclaration()`, `getSlaBreachRisk()`) lives in the domain, not in application services.
5. **Explicit exception hierarchy** — `ShipmentException` → `ExceptionResolution` models the full investigation lifecycle with audit trail.

