from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class ShipmentStatus(str, Enum):
    CREATED = "created"
    CONFIRMED = "confirmed"
    AT_ORIGIN_HUB = "at_origin_hub"
    IN_TRANSIT = "in_transit"
    AT_DESTINATION_HUB = "at_destination_hub"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    DELAYED = "delayed"
    FAILED = "failed"
    RETURNED = "returned"
    CANCELLED = "cancelled"


class DeliveryExceptionType(str, Enum):
    ADDRESS_ISSUE = "address_issue"
    CUSTOMER_UNAVAILABLE = "customer_unavailable"
    VEHICLE_BREAKDOWN = "vehicle_breakdown"
    WEATHER_DELAY = "weather_delay"
    HUB_DELAY = "hub_delay"
    DAMAGED = "damaged"
    LOST = "lost"
    FAILED_ATTEMPT = "failed_attempt"


class Shipment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    reference: str = Field(index=True, unique=True, max_length=64)
    customer_name: str = Field(max_length=255)
    customer_contact: str = Field(max_length=255)
    origin_address: str = Field(max_length=500)
    destination_address: str = Field(max_length=500)
    current_status: ShipmentStatus = Field(default=ShipmentStatus.CREATED)
    public_tracking_token: str = Field(index=True, unique=True, max_length=64)
    tenant_id: Optional[int] = Field(default=None, foreign_key="tenant.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ShipmentItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id", index=True)
    sku: str = Field(max_length=128)
    description: str = Field(max_length=255)
    quantity: int = Field(default=1, ge=1)
    weight_kg: float = Field(default=0.0, ge=0)


class ShipmentStop(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id", index=True)
    sequence: int = Field(ge=1)
    hub_id: Optional[int] = Field(default=None, foreign_key="hub.id", index=True)
    address: str = Field(max_length=500)
    arrived_at: Optional[datetime] = None
    departed_at: Optional[datetime] = None


class ShipmentEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id", index=True)
    status: ShipmentStatus = Field(index=True)
    message: str = Field(max_length=500)
    actor_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class TrackingCheckpoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id", index=True)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_label: Optional[str] = Field(default=None, max_length=255)
    eta_at: Optional[datetime] = None
    event_at: datetime = Field(default_factory=datetime.utcnow)


class Hub(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True, max_length=32)
    name: str = Field(max_length=255)
    address: str = Field(max_length=500)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class Route(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True, max_length=32)
    name: str = Field(max_length=255)
    is_active: bool = Field(default=True)


class RouteLeg(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    route_id: int = Field(foreign_key="route.id", index=True)
    from_hub_id: int = Field(foreign_key="hub.id", index=True)
    to_hub_id: int = Field(foreign_key="hub.id", index=True)
    sequence: int = Field(ge=1)


class Vehicle(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True, max_length=32)
    type: str = Field(max_length=64)
    capacity_kg: float = Field(default=0.0, ge=0)
    is_active: bool = Field(default=True)


class Driver(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    name: str = Field(max_length=255)
    phone: str = Field(max_length=64)
    license_number: str = Field(max_length=128)
    is_available: bool = Field(default=True)


class DriverAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id", index=True)
    driver_id: int = Field(foreign_key="driver.id", index=True)
    vehicle_id: Optional[int] = Field(default=None, foreign_key="vehicle.id", index=True)
    route_id: Optional[int] = Field(default=None, foreign_key="route.id", index=True)
    status: str = Field(default="assigned", max_length=32)
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class DeliveryAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id", index=True)
    assignment_id: Optional[int] = Field(default=None, foreign_key="driverassignment.id", index=True)
    attempted_at: datetime = Field(default_factory=datetime.utcnow)
    success: bool = Field(default=False)
    notes: Optional[str] = Field(default=None, max_length=500)


class DeliveryException(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id", index=True)
    assignment_id: Optional[int] = Field(default=None, foreign_key="driverassignment.id", index=True)
    exception_type: DeliveryExceptionType
    details: str = Field(max_length=500)
    is_resolved: bool = Field(default=False)
    raised_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class ProofOfDelivery(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id", index=True)
    assignment_id: Optional[int] = Field(default=None, foreign_key="driverassignment.id", index=True)
    recipient_name: str = Field(max_length=255)
    signature_text: Optional[str] = Field(default=None, max_length=255)
    photo_url: Optional[str] = Field(default=None, max_length=500)
    delivered_at: datetime = Field(default_factory=datetime.utcnow)
