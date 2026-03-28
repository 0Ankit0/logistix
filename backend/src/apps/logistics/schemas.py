from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from src.apps.logistics.models import DeliveryExceptionType, ShipmentStatus


class ShipmentCreate(BaseModel):
    customer_name: str
    customer_contact: str
    origin_address: str
    destination_address: str
    tenant_id: int | None = None


class ShipmentUpdate(BaseModel):
    customer_name: str | None = None
    customer_contact: str | None = None
    origin_address: str | None = None
    destination_address: str | None = None
    tenant_id: int | None = None


class ShipmentRead(BaseModel):
    id: int
    reference: str
    customer_name: str
    customer_contact: str
    origin_address: str
    destination_address: str
    current_status: ShipmentStatus
    public_tracking_token: str
    tenant_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShipmentStatusTransition(BaseModel):
    status: ShipmentStatus
    message: str = Field(default="Status updated", max_length=500)


class ShipmentEventRead(BaseModel):
    id: int
    shipment_id: int
    status: ShipmentStatus
    message: str
    actor_user_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class HubCreate(BaseModel):
    code: str
    name: str
    address: str
    latitude: float | None = None
    longitude: float | None = None


class HubUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class HubRead(HubCreate):
    id: int

    model_config = {"from_attributes": True}


class RouteCreate(BaseModel):
    code: str
    name: str
    is_active: bool = True


class RouteUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    is_active: bool | None = None


class RouteRead(RouteCreate):
    id: int

    model_config = {"from_attributes": True}


class RouteLegCreate(BaseModel):
    from_hub_id: int
    to_hub_id: int
    sequence: int


class RouteLegRead(BaseModel):
    id: int
    route_id: int
    from_hub_id: int
    to_hub_id: int
    sequence: int

    model_config = {"from_attributes": True}


class VehicleCreate(BaseModel):
    code: str
    type: str
    capacity_kg: float = 0
    is_active: bool = True


class VehicleUpdate(BaseModel):
    code: str | None = None
    type: str | None = None
    capacity_kg: float | None = None
    is_active: bool | None = None


class VehicleRead(VehicleCreate):
    id: int

    model_config = {"from_attributes": True}


class DriverCreate(BaseModel):
    user_id: int | None = None
    name: str
    phone: str
    license_number: str


class DriverUpdate(BaseModel):
    user_id: int | None = None
    name: str | None = None
    phone: str | None = None
    license_number: str | None = None


class DriverAvailabilityUpdate(BaseModel):
    is_available: bool


class DriverRead(DriverCreate):
    id: int
    is_available: bool

    model_config = {"from_attributes": True}


class AssignmentCreate(BaseModel):
    shipment_id: int
    driver_id: int
    vehicle_id: int | None = None
    route_id: int | None = None


class AssignmentStatusUpdate(BaseModel):
    status: str


class AssignmentRead(BaseModel):
    id: int
    shipment_id: int
    driver_id: int
    vehicle_id: int | None
    route_id: int | None
    status: str
    assigned_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class DeliveryAttemptCreate(BaseModel):
    shipment_id: int
    assignment_id: int | None = None
    success: bool = False
    notes: str | None = None


class DeliveryAttemptRead(BaseModel):
    id: int
    shipment_id: int
    assignment_id: int | None
    attempted_at: datetime
    success: bool
    notes: str | None

    model_config = {"from_attributes": True}


class DeliveryExceptionCreate(BaseModel):
    shipment_id: int
    assignment_id: int | None = None
    exception_type: DeliveryExceptionType
    details: str


class DeliveryExceptionResolve(BaseModel):
    resolution_notes: str = "Resolved by operator"


class DeliveryExceptionRead(BaseModel):
    id: int
    shipment_id: int
    assignment_id: int | None
    exception_type: DeliveryExceptionType
    details: str
    is_resolved: bool
    raised_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class ProofOfDeliveryCreate(BaseModel):
    shipment_id: int
    assignment_id: int | None = None
    recipient_name: str
    signature_text: str | None = None
    photo_url: str | None = None


class ProofOfDeliveryRead(BaseModel):
    id: int
    shipment_id: int
    assignment_id: int | None
    recipient_name: str
    signature_text: str | None
    photo_url: str | None
    delivered_at: datetime

    model_config = {"from_attributes": True}


class TrackingCheckpointCreate(BaseModel):
    shipment_id: int
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    eta_at: datetime | None = None


class TrackingCheckpointRead(BaseModel):
    id: int
    shipment_id: int
    latitude: float | None
    longitude: float | None
    location_label: str | None
    eta_at: datetime | None
    event_at: datetime

    model_config = {"from_attributes": True}


class PublicTrackingResponse(BaseModel):
    shipment: ShipmentRead
    timeline: list[ShipmentEventRead]
    latest_checkpoint: TrackingCheckpointRead | None
