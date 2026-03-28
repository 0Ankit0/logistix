from __future__ import annotations

from datetime import datetime
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from src.apps.analytics.dependencies import get_analytics
from src.apps.analytics.service import AnalyticsService
from src.apps.iam.api.deps import get_current_user, get_db
from src.apps.iam.models.user import User
from src.apps.logistics.models import (
    DeliveryAttempt,
    DeliveryException,
    Driver,
    DriverAssignment,
    Hub,
    ProofOfDelivery,
    Route,
    RouteLeg,
    Shipment,
    ShipmentEvent,
    ShipmentStatus,
    TrackingCheckpoint,
    Vehicle,
)
from src.apps.logistics.schemas import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentStatusUpdate,
    DeliveryAttemptCreate,
    DeliveryAttemptRead,
    DeliveryExceptionCreate,
    DeliveryExceptionRead,
    DeliveryExceptionResolve,
    DriverAvailabilityUpdate,
    DriverCreate,
    DriverRead,
    DriverUpdate,
    HubCreate,
    HubRead,
    HubUpdate,
    ProofOfDeliveryCreate,
    ProofOfDeliveryRead,
    PublicTrackingResponse,
    RouteCreate,
    RouteLegCreate,
    RouteLegRead,
    RouteRead,
    RouteUpdate,
    ShipmentCreate,
    ShipmentEventRead,
    ShipmentRead,
    ShipmentStatusTransition,
    ShipmentUpdate,
    TrackingCheckpointCreate,
    TrackingCheckpointRead,
    VehicleCreate,
    VehicleRead,
    VehicleUpdate,
)
from src.apps.notification.models.notification import NotificationType
from src.apps.notification.schemas.notification import NotificationCreate
from src.apps.notification.services.notification import create_notification
from src.apps.websocket.manager import manager as ws_manager

router = APIRouter()
log = logging.getLogger(__name__)

ALLOWED_TRANSITIONS: dict[ShipmentStatus, set[ShipmentStatus]] = {
    ShipmentStatus.CREATED: {ShipmentStatus.CONFIRMED, ShipmentStatus.CANCELLED},
    ShipmentStatus.CONFIRMED: {ShipmentStatus.AT_ORIGIN_HUB, ShipmentStatus.CANCELLED},
    ShipmentStatus.AT_ORIGIN_HUB: {ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELAYED},
    ShipmentStatus.IN_TRANSIT: {ShipmentStatus.AT_DESTINATION_HUB, ShipmentStatus.DELAYED, ShipmentStatus.FAILED},
    ShipmentStatus.AT_DESTINATION_HUB: {ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.DELAYED},
    ShipmentStatus.OUT_FOR_DELIVERY: {ShipmentStatus.DELIVERED, ShipmentStatus.FAILED, ShipmentStatus.RETURNED},
    ShipmentStatus.DELAYED: {ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.FAILED},
    ShipmentStatus.FAILED: {ShipmentStatus.RETURNED, ShipmentStatus.OUT_FOR_DELIVERY},
    ShipmentStatus.RETURNED: set(),
    ShipmentStatus.CANCELLED: set(),
    ShipmentStatus.DELIVERED: set(),
}



CUSTOMER_MILESTONE_STATUSES = {
    ShipmentStatus.CREATED,
    ShipmentStatus.IN_TRANSIT,
    ShipmentStatus.OUT_FOR_DELIVERY,
    ShipmentStatus.DELIVERED,
    ShipmentStatus.DELAYED,
    ShipmentStatus.FAILED,
}


async def _notify_shipment_update(
    db: AsyncSession,
    shipment: Shipment,
    status_value: ShipmentStatus,
    actor_user_id: int,
) -> None:
    if status_value not in CUSTOMER_MILESTONE_STATUSES:
        return

    payload = NotificationCreate(
        user_id=actor_user_id,
        title=f"Shipment {shipment.reference} update",
        body=f"Shipment status changed to {status_value.value}",
        type=NotificationType.INFO,
        extra_data={
            "shipment_id": shipment.id,
            "shipment_reference": shipment.reference,
            "status": status_value.value,
        },
    )
    await create_notification(db, payload, push_ws=True)

    assignment_result = await db.execute(
        select(DriverAssignment)
        .where(DriverAssignment.shipment_id == shipment.id)
        .order_by(col(DriverAssignment.assigned_at).desc())
        .limit(1)
    )
    assignment = assignment_result.scalars().first()
    if assignment:
        driver = await db.get(Driver, assignment.driver_id)
        if driver and driver.user_id and driver.user_id != actor_user_id:
            await create_notification(
                db,
                NotificationCreate(
                    user_id=driver.user_id,
                    title=f"Assignment update for {shipment.reference}",
                    body=f"Shipment status is now {status_value.value}",
                    type=NotificationType.INFO,
                    extra_data={
                        "shipment_id": shipment.id,
                        "shipment_reference": shipment.reference,
                        "status": status_value.value,
                    },
                ),
                push_ws=True,
            )

class LogisticsEvent:
    SHIPMENT_CREATED = "logistics.shipment.created"
    SHIPMENT_UPDATED = "logistics.shipment.updated"
    SHIPMENT_STATUS_CHANGED = "logistics.shipment.status_changed"
    ASSIGNMENT_CREATED = "logistics.assignment.created"
    ASSIGNMENT_UPDATED = "logistics.assignment.updated"
    EXCEPTION_RAISED = "logistics.exception.raised"
    EXCEPTION_RESOLVED = "logistics.exception.resolved"
    DELIVERY_COMPLETED = "logistics.delivery.completed"
    TRACKING_CHECKPOINT = "logistics.tracking.checkpoint"


def _shipment_reference() -> str:
    return f"SHP-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"


async def _append_event(
    db: AsyncSession,
    shipment: Shipment,
    status_value: ShipmentStatus,
    message: str,
    actor_user_id: int | None,
) -> ShipmentEvent:
    event = ShipmentEvent(
        shipment_id=shipment.id,
        status=status_value,
        message=message,
        actor_user_id=actor_user_id,
    )
    db.add(event)
    await db.flush()
    return event


async def _emit_domain_event(analytics: AnalyticsService, user_id: int | None, event: str, payload: dict) -> None:
    try:
        await analytics.capture(str(user_id or "system"), event, payload)
    except Exception:
        log.exception("analytics_capture_failed event=%s", event)


async def _push_internal_ws(event: str, payload: dict) -> None:
    try:
        await ws_manager.broadcast({"event": event, "data": payload})
    except Exception:
        log.debug("ws_broadcast_skipped event=%s", event)


def _log_lifecycle(event: str, **context: object) -> None:
    log.info("logistics_lifecycle event=%s context=%s", event, context)


def _apply_shipment_updates(shipment: Shipment, payload: ShipmentUpdate) -> Shipment:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(shipment, field, value)
    shipment.updated_at = datetime.utcnow()
    return shipment


@router.post("/shipments", response_model=ShipmentRead, status_code=status.HTTP_201_CREATED)
async def create_shipment(
    payload: ShipmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics),
) -> ShipmentRead:
    shipment = Shipment(
        reference=_shipment_reference(),
        customer_name=payload.customer_name,
        customer_contact=payload.customer_contact,
        origin_address=payload.origin_address,
        destination_address=payload.destination_address,
        tenant_id=payload.tenant_id,
        public_tracking_token=uuid4().hex,
    )
    db.add(shipment)
    await db.flush()
    await _append_event(db, shipment, ShipmentStatus.CREATED, "Shipment created", current_user.id)
    await db.commit()
    await db.refresh(shipment)
    await _notify_shipment_update(db, shipment, shipment.current_status, current_user.id)

    await _emit_domain_event(
        analytics,
        current_user.id,
        LogisticsEvent.SHIPMENT_CREATED,
        {"shipment_id": shipment.id, "reference": shipment.reference, "tenant_id": shipment.tenant_id},
    )
    await _push_internal_ws(
        LogisticsEvent.SHIPMENT_CREATED,
        {"shipment_id": shipment.id, "reference": shipment.reference, "status": shipment.current_status.value},
    )
    _log_lifecycle(LogisticsEvent.SHIPMENT_CREATED, shipment_id=shipment.id, status=shipment.current_status.value)
    return shipment


@router.get("/shipments", response_model=list[ShipmentRead])
async def list_shipments(
    tenant_id: int | None = Query(default=None),
    status_filter: ShipmentStatus | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ShipmentRead]:
    query = select(Shipment).order_by(col(Shipment.id).desc())
    if tenant_id is not None:
        query = query.where(Shipment.tenant_id == tenant_id)
    if status_filter is not None:
        query = query.where(Shipment.current_status == status_filter)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/shipments/{shipment_id}", response_model=ShipmentRead)
async def get_shipment(shipment_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> ShipmentRead:
    shipment = await db.get(Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment


@router.delete("/shipments/{shipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_shipment(
    shipment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    shipment = await db.get(Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    shipment.current_status = ShipmentStatus.CANCELLED
    shipment.updated_at = datetime.utcnow()
    db.add(shipment)
    await _append_event(db, shipment, ShipmentStatus.CANCELLED, "Shipment cancelled", current_user.id)
    await db.commit()


@router.patch("/shipments/{shipment_id}", response_model=ShipmentRead)
async def update_shipment_metadata(
    shipment_id: int,
    payload: ShipmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics),
) -> ShipmentRead:
    shipment = await db.get(Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")

    shipment = _apply_shipment_updates(shipment, payload)
    db.add(shipment)
    await _append_event(db, shipment, shipment.current_status, "Shipment metadata updated", current_user.id)
    await db.commit()
    await db.refresh(shipment)
    await _notify_shipment_update(db, shipment, shipment.current_status, current_user.id)

    await _emit_domain_event(
        analytics,
        current_user.id,
        LogisticsEvent.SHIPMENT_UPDATED,
        {"shipment_id": shipment.id, "reference": shipment.reference},
    )
    return shipment


@router.get("/shipments/{shipment_id}/timeline", response_model=list[ShipmentEventRead])
async def get_shipment_timeline(
    shipment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ShipmentEventRead]:
    result = await db.execute(
        select(ShipmentEvent)
        .where(ShipmentEvent.shipment_id == shipment_id)
        .order_by(col(ShipmentEvent.created_at).asc())
    )
    return list(result.scalars().all())


@router.patch("/shipments/{shipment_id}/status", response_model=ShipmentRead)
async def transition_status(
    shipment_id: int,
    payload: ShipmentStatusTransition,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics),
) -> ShipmentRead:
    shipment = await db.get(Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")

    allowed = ALLOWED_TRANSITIONS.get(shipment.current_status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {shipment.current_status} to {payload.status}",
        )

    shipment.current_status = payload.status
    shipment.updated_at = datetime.utcnow()
    db.add(shipment)
    await _append_event(db, shipment, payload.status, payload.message, current_user.id)
    await db.commit()
    await db.refresh(shipment)
    await _notify_shipment_update(db, shipment, shipment.current_status, current_user.id)

    await _emit_domain_event(
        analytics,
        current_user.id,
        LogisticsEvent.SHIPMENT_STATUS_CHANGED,
        {"shipment_id": shipment.id, "reference": shipment.reference, "status": shipment.current_status.value},
    )
    _log_lifecycle(LogisticsEvent.SHIPMENT_STATUS_CHANGED, shipment_id=shipment.id, status=shipment.current_status.value)
    return shipment


@router.get("/tracking/{tracking_token}", response_model=PublicTrackingResponse)
async def public_tracking_lookup(tracking_token: str, db: AsyncSession = Depends(get_db)) -> PublicTrackingResponse:
    result = await db.execute(select(Shipment).where(Shipment.public_tracking_token == tracking_token))
    shipment = result.scalars().first()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Tracking reference not found")

    timeline_result = await db.execute(
        select(ShipmentEvent)
        .where(ShipmentEvent.shipment_id == shipment.id)
        .order_by(col(ShipmentEvent.created_at).asc())
    )
    checkpoint_result = await db.execute(
        select(TrackingCheckpoint)
        .where(TrackingCheckpoint.shipment_id == shipment.id)
        .order_by(col(TrackingCheckpoint.event_at).desc())
        .limit(1)
    )
    latest_checkpoint = checkpoint_result.scalars().first()
    return PublicTrackingResponse(
        shipment=ShipmentRead.model_validate(shipment),
        timeline=[ShipmentEventRead.model_validate(item) for item in timeline_result.scalars().all()],
        latest_checkpoint=TrackingCheckpointRead.model_validate(latest_checkpoint) if latest_checkpoint else None,
    )


@router.get("/tracking/internal/{shipment_id}", response_model=PublicTrackingResponse)
async def internal_tracking_detail(
    shipment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PublicTrackingResponse:
    shipment = await db.get(Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return await public_tracking_lookup(shipment.public_tracking_token, db)


@router.get("/tracking/internal/{shipment_id}/latest", response_model=TrackingCheckpointRead | None)
async def internal_tracking_latest(
    shipment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TrackingCheckpointRead | None:
    checkpoint_result = await db.execute(
        select(TrackingCheckpoint)
        .where(TrackingCheckpoint.shipment_id == shipment_id)
        .order_by(col(TrackingCheckpoint.event_at).desc())
        .limit(1)
    )
    latest = checkpoint_result.scalars().first()
    return TrackingCheckpointRead.model_validate(latest) if latest else None


@router.post("/tracking/checkpoints", response_model=TrackingCheckpointRead, status_code=status.HTTP_201_CREATED)
async def add_checkpoint(
    payload: TrackingCheckpointCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics),
) -> TrackingCheckpointRead:
    shipment = await db.get(Shipment, payload.shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")

    checkpoint = TrackingCheckpoint(**payload.model_dump())
    db.add(checkpoint)
    await _append_event(
        db,
        shipment,
        shipment.current_status,
        f"Checkpoint updated: {payload.location_label or 'checkpoint'}",
        current_user.id,
    )
    await db.commit()
    await db.refresh(checkpoint)

    await _emit_domain_event(
        analytics,
        current_user.id,
        LogisticsEvent.TRACKING_CHECKPOINT,
        {"shipment_id": payload.shipment_id, "checkpoint_id": checkpoint.id},
    )
    return checkpoint


@router.get("/hubs", response_model=list[HubRead])
async def list_hubs(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[HubRead]:
    result = await db.execute(select(Hub).order_by(col(Hub.name).asc()))
    return list(result.scalars().all())


@router.get("/hubs/{hub_id}", response_model=HubRead)
async def get_hub(hub_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> HubRead:
    hub = await db.get(Hub, hub_id)
    if hub is None:
        raise HTTPException(status_code=404, detail="Hub not found")
    return hub


@router.delete("/hubs/{hub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hub(hub_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> None:
    hub = await db.get(Hub, hub_id)
    if hub is None:
        raise HTTPException(status_code=404, detail="Hub not found")
    await db.delete(hub)
    await db.commit()


@router.post("/hubs", response_model=HubRead, status_code=status.HTTP_201_CREATED)
async def create_hub(payload: HubCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> HubRead:
    hub = Hub(**payload.model_dump())
    db.add(hub)
    await db.commit()
    await db.refresh(hub)
    return hub


@router.patch("/hubs/{hub_id}", response_model=HubRead)
async def update_hub(
    hub_id: int,
    payload: HubUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> HubRead:
    hub = await db.get(Hub, hub_id)
    if hub is None:
        raise HTTPException(status_code=404, detail="Hub not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(hub, key, value)
    db.add(hub)
    await db.commit()
    await db.refresh(hub)
    return hub


@router.get("/routes", response_model=list[RouteRead])
async def list_routes(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[RouteRead]:
    result = await db.execute(select(Route).order_by(col(Route.name).asc()))
    return list(result.scalars().all())


@router.post("/routes", response_model=RouteRead, status_code=status.HTTP_201_CREATED)
async def create_route(payload: RouteCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> RouteRead:
    route = Route(**payload.model_dump())
    db.add(route)
    await db.commit()
    await db.refresh(route)
    return route


@router.get("/routes/{route_id}", response_model=RouteRead)
async def get_route(route_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> RouteRead:
    route = await db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.patch("/routes/{route_id}", response_model=RouteRead)
async def update_route(
    route_id: int,
    payload: RouteUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RouteRead:
    route = await db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(route, key, value)
    db.add(route)
    await db.commit()
    await db.refresh(route)
    return route


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(route_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> None:
    route = await db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    await db.delete(route)
    await db.commit()


@router.get("/routes/{route_id}/legs", response_model=list[RouteLegRead])
async def list_route_legs(route_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[RouteLegRead]:
    result = await db.execute(select(RouteLeg).where(RouteLeg.route_id == route_id).order_by(col(RouteLeg.sequence).asc()))
    return list(result.scalars().all())


@router.delete("/routes/{route_id}/legs/{leg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route_leg(
    route_id: int,
    leg_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> None:
    leg = await db.get(RouteLeg, leg_id)
    if leg is None or leg.route_id != route_id:
        raise HTTPException(status_code=404, detail="Route leg not found")
    await db.delete(leg)
    await db.commit()


@router.post("/routes/{route_id}/legs", response_model=RouteLegRead, status_code=status.HTTP_201_CREATED)
async def add_route_leg(
    route_id: int,
    payload: RouteLegCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RouteLegRead:
    route = await db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    leg = RouteLeg(route_id=route_id, **payload.model_dump())
    db.add(leg)
    await db.commit()
    await db.refresh(leg)
    return leg


@router.get("/fleet/vehicles", response_model=list[VehicleRead])
async def list_vehicles(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[VehicleRead]:
    result = await db.execute(select(Vehicle).order_by(col(Vehicle.id).desc()))
    return list(result.scalars().all())


@router.get("/fleet/vehicles/{vehicle_id}", response_model=VehicleRead)
async def get_vehicle(vehicle_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> VehicleRead:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.post("/fleet/vehicles", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VehicleRead:
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


@router.patch("/fleet/vehicles/{vehicle_id}", response_model=VehicleRead)
async def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VehicleRead:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle, key, value)
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


@router.delete("/fleet/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(vehicle_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> None:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    await db.delete(vehicle)
    await db.commit()


@router.get("/fleet/drivers", response_model=list[DriverRead])
async def list_drivers(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[DriverRead]:
    result = await db.execute(select(Driver).order_by(col(Driver.id).desc()))
    return list(result.scalars().all())


@router.get("/fleet/drivers/{driver_id}", response_model=DriverRead)
async def get_driver(driver_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> DriverRead:
    driver = await db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@router.post("/fleet/drivers", response_model=DriverRead, status_code=status.HTTP_201_CREATED)
async def create_driver(payload: DriverCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> DriverRead:
    driver = Driver(**payload.model_dump())
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return driver


@router.patch("/fleet/drivers/{driver_id}", response_model=DriverRead)
async def update_driver(
    driver_id: int,
    payload: DriverUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DriverRead:
    driver = await db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(driver, key, value)
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return driver


@router.patch("/fleet/drivers/{driver_id}/availability", response_model=DriverRead)
async def update_driver_availability(
    driver_id: int,
    payload: DriverAvailabilityUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DriverRead:
    driver = await db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    driver.is_available = payload.is_available
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return driver


@router.delete("/fleet/drivers/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_driver(driver_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> None:
    driver = await db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    await db.delete(driver)
    await db.commit()


@router.get("/dispatch/assignments", response_model=list[AssignmentRead])
async def list_assignments(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> list[AssignmentRead]:
    result = await db.execute(select(DriverAssignment).order_by(col(DriverAssignment.id).desc()))
    return list(result.scalars().all())


@router.get("/dispatch/assignments/{assignment_id}", response_model=AssignmentRead)
async def get_assignment(assignment_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> AssignmentRead:
    assignment = await db.get(DriverAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


@router.post("/dispatch/assignments", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    payload: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics),
) -> AssignmentRead:
    shipment = await db.get(Shipment, payload.shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")

    assignment = DriverAssignment(**payload.model_dump())
    db.add(assignment)
    await db.flush()
    await _append_event(db, shipment, shipment.current_status, f"Driver assignment {assignment.id} created", current_user.id)
    await db.commit()
    await db.refresh(assignment)

    await _emit_domain_event(
        analytics,
        current_user.id,
        LogisticsEvent.ASSIGNMENT_CREATED,
        {"assignment_id": assignment.id, "shipment_id": assignment.shipment_id},
    )
    return assignment


@router.patch("/dispatch/assignments/{assignment_id}", response_model=AssignmentRead)
async def update_assignment_status(
    assignment_id: int,
    payload: AssignmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics),
) -> AssignmentRead:
    assignment = await db.get(DriverAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    assignment.status = payload.status
    if payload.status in {"completed", "delivered"}:
        assignment.completed_at = datetime.utcnow()
    db.add(assignment)

    shipment = await db.get(Shipment, assignment.shipment_id)
    if shipment:
        await _append_event(db, shipment, shipment.current_status, f"Assignment status set to {payload.status}", current_user.id)

    await db.commit()
    await db.refresh(assignment)

    await _emit_domain_event(
        analytics,
        current_user.id,
        LogisticsEvent.ASSIGNMENT_UPDATED,
        {"assignment_id": assignment.id, "status": assignment.status},
    )
    return assignment


@router.delete("/dispatch/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(assignment_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> None:
    assignment = await db.get(DriverAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await db.delete(assignment)
    await db.commit()


@router.post("/dispatch/delivery-attempts", response_model=DeliveryAttemptRead, status_code=status.HTTP_201_CREATED)
async def create_delivery_attempt(
    payload: DeliveryAttemptCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DeliveryAttemptRead:
    attempt = DeliveryAttempt(**payload.model_dump())
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt


@router.get("/dispatch/delivery-attempts/{attempt_id}", response_model=DeliveryAttemptRead)
async def get_delivery_attempt(attempt_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> DeliveryAttemptRead:
    attempt = await db.get(DeliveryAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Delivery attempt not found")
    return attempt


@router.get("/dispatch/exceptions", response_model=list[DeliveryExceptionRead])
async def list_exceptions(
    db: AsyncSession = Depends(get_db),
    only_open: bool = Query(default=False),
    _: User = Depends(get_current_user),
) -> list[DeliveryExceptionRead]:
    query = select(DeliveryException).order_by(col(DeliveryException.raised_at).desc())
    if only_open:
        query = query.where(DeliveryException.is_resolved == False)  # noqa: E712
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/dispatch/exceptions/{exception_id}", response_model=DeliveryExceptionRead)
async def get_exception(exception_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)) -> DeliveryExceptionRead:
    exception = await db.get(DeliveryException, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception not found")
    return exception


@router.post("/dispatch/exceptions", response_model=DeliveryExceptionRead, status_code=status.HTTP_201_CREATED)
async def create_exception(
    payload: DeliveryExceptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics),
) -> DeliveryExceptionRead:
    shipment = await db.get(Shipment, payload.shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")

    exception = DeliveryException(**payload.model_dump())
    db.add(exception)
    await _append_event(db, shipment, ShipmentStatus.DELAYED, f"Exception raised: {payload.exception_type.value}", current_user.id)
    await db.commit()
    await db.refresh(exception)

    await create_notification(
        db,
        NotificationCreate(
            user_id=current_user.id,
            title=f"Exception on shipment {shipment.reference}",
            body=payload.details,
            type=NotificationType.WARNING,
            extra_data={
                "shipment_id": shipment.id,
                "shipment_reference": shipment.reference,
                "exception_type": payload.exception_type.value,
            },
        ),
        push_ws=True,
    )

    await _emit_domain_event(
        analytics,
        current_user.id,
        LogisticsEvent.EXCEPTION_RAISED,
        {"exception_id": exception.id, "shipment_id": exception.shipment_id},
    )
    _log_lifecycle(LogisticsEvent.EXCEPTION_RAISED, exception_id=exception.id, shipment_id=exception.shipment_id)
    return exception


@router.post("/dispatch/exceptions/{exception_id}/resolve", response_model=DeliveryExceptionRead)
async def resolve_exception(
    exception_id: int,
    payload: DeliveryExceptionResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics),
) -> DeliveryExceptionRead:
    exception = await db.get(DeliveryException, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception not found")

    exception.is_resolved = True
    exception.resolved_at = datetime.utcnow()
    db.add(exception)

    shipment = await db.get(Shipment, exception.shipment_id)
    if shipment:
        next_status = ShipmentStatus.IN_TRANSIT if shipment.current_status == ShipmentStatus.DELAYED else shipment.current_status
        shipment.current_status = next_status
        shipment.updated_at = datetime.utcnow()
        db.add(shipment)
        await _append_event(db, shipment, next_status, f"Exception resolved: {payload.resolution_notes}", current_user.id)

    await db.commit()
    await db.refresh(exception)

    await _emit_domain_event(
        analytics,
        current_user.id,
        LogisticsEvent.EXCEPTION_RESOLVED,
        {"exception_id": exception.id, "shipment_id": exception.shipment_id},
    )
    _log_lifecycle(LogisticsEvent.EXCEPTION_RESOLVED, exception_id=exception.id, shipment_id=exception.shipment_id)
    return exception


@router.get("/dispatch/delivery-attempts", response_model=list[DeliveryAttemptRead])
async def list_delivery_attempts(
    shipment_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DeliveryAttemptRead]:
    query = select(DeliveryAttempt).order_by(col(DeliveryAttempt.attempted_at).desc())
    if shipment_id is not None:
        query = query.where(DeliveryAttempt.shipment_id == shipment_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/dispatch/proof-of-delivery/{shipment_id}", response_model=ProofOfDeliveryRead | None)
async def get_proof_of_delivery(
    shipment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ProofOfDeliveryRead | None:
    result = await db.execute(
        select(ProofOfDelivery)
        .where(ProofOfDelivery.shipment_id == shipment_id)
        .order_by(col(ProofOfDelivery.delivered_at).desc())
        .limit(1)
    )
    pod = result.scalars().first()
    return ProofOfDeliveryRead.model_validate(pod) if pod else None


@router.post("/dispatch/proof-of-delivery", response_model=ProofOfDeliveryRead, status_code=status.HTTP_201_CREATED)
async def create_proof_of_delivery(
    payload: ProofOfDeliveryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics),
) -> ProofOfDeliveryRead:
    shipment = await db.get(Shipment, payload.shipment_id)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")

    pod = ProofOfDelivery(**payload.model_dump())
    shipment.current_status = ShipmentStatus.DELIVERED
    shipment.updated_at = datetime.utcnow()
    db.add(pod)
    db.add(shipment)
    await _append_event(db, shipment, ShipmentStatus.DELIVERED, "Proof of delivery captured", current_user.id)
    await db.commit()
    await db.refresh(pod)
    await _notify_shipment_update(db, shipment, ShipmentStatus.DELIVERED, current_user.id)

    await _emit_domain_event(
        analytics,
        current_user.id,
        LogisticsEvent.DELIVERY_COMPLETED,
        {"shipment_id": shipment.id, "proof_of_delivery_id": pod.id},
    )
    _log_lifecycle(LogisticsEvent.DELIVERY_COMPLETED, shipment_id=shipment.id, proof_of_delivery_id=pod.id)
    return pod
