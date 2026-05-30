from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import select

from src.apps.core.security import get_password_hash
from src.apps.finance.models.payment import PaymentProvider, PaymentStatus, PaymentTransaction
from src.apps.iam.models.role import Permission, Role, RolePermission, UserRole
from src.apps.iam.models.user import User, UserProfile
from src.apps.logistics.models import (
    DeliveryAttempt,
    DeliveryException,
    DeliveryExceptionType,
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
from src.apps.multitenancy.models.tenant import (
    InvitationStatus,
    Tenant,
    TenantInvitation,
    TenantMember,
    TenantRole,
)
from src.apps.notification.models.notification import Notification, NotificationType
from src.apps.observability.models import ObservabilityLogEntry, SecurityIncident
from src.db.session import async_session_factory, init_db


async def _get_user(session, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalars().first()


async def _get_by_field(session, model, field, value):
    result = await session.execute(select(model).where(field == value))
    return result.scalars().first()


async def _ensure_user(
    session,
    *,
    username: str,
    email: str,
    password: str,
    is_superuser: bool,
    first_name: str,
    last_name: str,
    phone: str,
) -> User:
    user = await _get_user(session, username)
    hashed = get_password_hash(password)

    if user is None:
        user = User(
            username=username,
            email=email,
            hashed_password=hashed,
            is_active=True,
            is_superuser=is_superuser,
            is_confirmed=True,
            otp_enabled=False,
            otp_verified=False,
        )
        session.add(user)
        await session.flush()

        profile = UserProfile(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            bio=f"QA seeded profile for {username}",
        )
        session.add(profile)
        await session.flush()
        return user

    user.email = email
    user.hashed_password = hashed
    user.is_active = True
    user.is_superuser = is_superuser
    user.is_confirmed = True

    profile_result = await session.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = profile_result.scalars().first()
    if profile is None:
        profile = UserProfile(user_id=user.id)
        session.add(profile)
    profile.first_name = first_name
    profile.last_name = last_name
    profile.phone = phone
    profile.bio = f"QA seeded profile for {username}"
    await session.flush()
    return user


async def _ensure_role(session, name: str, description: str) -> Role:
    role = await _get_by_field(session, Role, Role.name, name)
    if role is None:
        role = Role(name=name, description=description)
        session.add(role)
        await session.flush()
    else:
        role.description = description
    return role


async def _ensure_permission(session, resource: str, action: str, description: str) -> Permission:
    result = await session.execute(
        select(Permission).where(Permission.resource == resource, Permission.action == action)
    )
    permission = result.scalars().first()
    if permission is None:
        permission = Permission(resource=resource, action=action, description=description)
        session.add(permission)
        await session.flush()
    else:
        permission.description = description
    return permission


async def _ensure_user_role(session, user_id: int, role_id: int) -> None:
    result = await session.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )
    if result.scalars().first() is None:
        session.add(UserRole(user_id=user_id, role_id=role_id))
        await session.flush()


async def _ensure_role_permission(session, role_id: int, permission_id: int) -> None:
    result = await session.execute(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    )
    if result.scalars().first() is None:
        session.add(RolePermission(role_id=role_id, permission_id=permission_id))
        await session.flush()


async def _ensure_tenant(session, owner_id: int) -> Tenant:
    tenant = await _get_by_field(session, Tenant, Tenant.slug, "qa-logistics")
    if tenant is None:
        tenant = Tenant(
            name="QA Logistics Org",
            slug="qa-logistics",
            description="Seeded tenant for deterministic manual QA",
            is_active=True,
            owner_id=owner_id,
        )
        session.add(tenant)
        await session.flush()
    else:
        tenant.name = "QA Logistics Org"
        tenant.description = "Seeded tenant for deterministic manual QA"
        tenant.owner_id = owner_id
    return tenant


async def _ensure_tenant_member(session, tenant_id: int, user_id: int, role: TenantRole) -> None:
    result = await session.execute(
        select(TenantMember).where(TenantMember.tenant_id == tenant_id, TenantMember.user_id == user_id)
    )
    member = result.scalars().first()
    if member is None:
        member = TenantMember(tenant_id=tenant_id, user_id=user_id, role=role, is_active=True)
        session.add(member)
    else:
        member.role = role
        member.is_active = True
    await session.flush()


async def _ensure_invitation(session, tenant_id: int, invited_by: int) -> TenantInvitation:
    invitation = await _get_by_field(session, TenantInvitation, TenantInvitation.token, "qa-invite-token-001")
    expiry = datetime.now() + timedelta(days=7)
    if invitation is None:
        invitation = TenantInvitation(
            tenant_id=tenant_id,
            invited_by=invited_by,
            email="invitee.qa@example.com",
            role=TenantRole.MEMBER,
            status=InvitationStatus.PENDING,
            token="qa-invite-token-001",
            expires_at=expiry,
        )
        session.add(invitation)
        await session.flush()
    else:
        invitation.tenant_id = tenant_id
        invitation.invited_by = invited_by
        invitation.email = "invitee.qa@example.com"
        invitation.role = TenantRole.MEMBER
        invitation.status = InvitationStatus.PENDING
        invitation.expires_at = expiry
    return invitation


async def _ensure_hub(session, code: str, name: str, address: str, lat: float, lon: float) -> Hub:
    hub = await _get_by_field(session, Hub, Hub.code, code)
    if hub is None:
        hub = Hub(code=code, name=name, address=address, latitude=lat, longitude=lon)
        session.add(hub)
        await session.flush()
    else:
        hub.name = name
        hub.address = address
        hub.latitude = lat
        hub.longitude = lon
    return hub


async def _ensure_route(session, code: str, name: str) -> Route:
    route = await _get_by_field(session, Route, Route.code, code)
    if route is None:
        route = Route(code=code, name=name, is_active=True)
        session.add(route)
        await session.flush()
    else:
        route.name = name
        route.is_active = True
    return route


async def _ensure_route_leg(session, route_id: int, from_hub_id: int, to_hub_id: int, sequence: int) -> None:
    result = await session.execute(
        select(RouteLeg).where(RouteLeg.route_id == route_id, RouteLeg.sequence == sequence)
    )
    leg = result.scalars().first()
    if leg is None:
        leg = RouteLeg(route_id=route_id, from_hub_id=from_hub_id, to_hub_id=to_hub_id, sequence=sequence)
        session.add(leg)
    else:
        leg.from_hub_id = from_hub_id
        leg.to_hub_id = to_hub_id
    await session.flush()


async def _ensure_vehicle(session, code: str, type_: str, capacity_kg: float) -> Vehicle:
    vehicle = await _get_by_field(session, Vehicle, Vehicle.code, code)
    if vehicle is None:
        vehicle = Vehicle(code=code, type=type_, capacity_kg=capacity_kg, is_active=True)
        session.add(vehicle)
        await session.flush()
    else:
        vehicle.type = type_
        vehicle.capacity_kg = capacity_kg
        vehicle.is_active = True
    return vehicle


async def _ensure_driver(session, name: str, phone: str, license_number: str, user_id: int | None = None) -> Driver:
    driver = await _get_by_field(session, Driver, Driver.license_number, license_number)
    if driver is None:
        driver = Driver(name=name, phone=phone, license_number=license_number, user_id=user_id, is_available=True)
        session.add(driver)
        await session.flush()
    else:
        driver.name = name
        driver.phone = phone
        driver.user_id = user_id
        driver.is_available = True
    return driver


async def _ensure_shipment(
    session,
    *,
    reference: str,
    token: str,
    customer_name: str,
    customer_contact: str,
    origin: str,
    destination: str,
    status: ShipmentStatus,
    tenant_id: int,
) -> Shipment:
    shipment = await _get_by_field(session, Shipment, Shipment.reference, reference)
    if shipment is None:
        shipment = Shipment(
            reference=reference,
            public_tracking_token=token,
            customer_name=customer_name,
            customer_contact=customer_contact,
            origin_address=origin,
            destination_address=destination,
            current_status=status,
            tenant_id=tenant_id,
        )
        session.add(shipment)
        await session.flush()
    else:
        shipment.public_tracking_token = token
        shipment.customer_name = customer_name
        shipment.customer_contact = customer_contact
        shipment.origin_address = origin
        shipment.destination_address = destination
        shipment.current_status = status
        shipment.tenant_id = tenant_id
        shipment.updated_at = datetime.utcnow()
    return shipment


async def _reset_shipment_events(session, shipment_id: int) -> None:
    result = await session.execute(select(ShipmentEvent).where(ShipmentEvent.shipment_id == shipment_id))
    for row in result.scalars().all():
        await session.delete(row)
    await session.flush()


async def _create_shipment_timeline(session, shipment: Shipment, actor_user_id: int, statuses: list[ShipmentStatus]) -> None:
    await _reset_shipment_events(session, shipment.id)
    for idx, item in enumerate(statuses, start=1):
        session.add(
            ShipmentEvent(
                shipment_id=shipment.id,
                status=item,
                message=f"QA seeded transition {idx}: {item.value}",
                actor_user_id=actor_user_id,
                created_at=datetime.utcnow() - timedelta(hours=(len(statuses) - idx)),
            )
        )
    await session.flush()


async def _upsert_assignment(
    session,
    shipment_id: int,
    driver_id: int,
    vehicle_id: int,
    route_id: int,
    status: str,
) -> DriverAssignment:
    result = await session.execute(select(DriverAssignment).where(DriverAssignment.shipment_id == shipment_id))
    assignment = result.scalars().first()
    if assignment is None:
        assignment = DriverAssignment(
            shipment_id=shipment_id,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            route_id=route_id,
            status=status,
        )
        session.add(assignment)
        await session.flush()
    else:
        assignment.driver_id = driver_id
        assignment.vehicle_id = vehicle_id
        assignment.route_id = route_id
        assignment.status = status
    return assignment


async def _reset_checkpoints(session, shipment_id: int) -> None:
    result = await session.execute(select(TrackingCheckpoint).where(TrackingCheckpoint.shipment_id == shipment_id))
    for row in result.scalars().all():
        await session.delete(row)
    await session.flush()


async def _seed_checkpoints(session, shipment_id: int) -> None:
    await _reset_checkpoints(session, shipment_id)
    now = datetime.utcnow()
    points = [
        (27.7172, 85.3240, "Kathmandu Origin Hub", now - timedelta(hours=7)),
        (27.6700, 85.4200, "On Linehaul", now - timedelta(hours=4)),
        (27.6380, 85.5150, "Destination Hub", now - timedelta(hours=1)),
    ]
    for lat, lon, label, event_at in points:
        session.add(
            TrackingCheckpoint(
                shipment_id=shipment_id,
                latitude=lat,
                longitude=lon,
                location_label=label,
                eta_at=now + timedelta(hours=2),
                event_at=event_at,
            )
        )
    await session.flush()


async def _ensure_exception(session, shipment_id: int, assignment_id: int) -> DeliveryException:
    result = await session.execute(
        select(DeliveryException).where(DeliveryException.shipment_id == shipment_id)
    )
    item = result.scalars().first()
    if item is None:
        item = DeliveryException(
            shipment_id=shipment_id,
            assignment_id=assignment_id,
            exception_type=DeliveryExceptionType.WEATHER_DELAY,
            details="QA seeded weather delay for exception workflow verification",
            is_resolved=False,
        )
        session.add(item)
    else:
        item.assignment_id = assignment_id
        item.exception_type = DeliveryExceptionType.WEATHER_DELAY
        item.details = "QA seeded weather delay for exception workflow verification"
        item.is_resolved = False
        item.resolved_at = None
    await session.flush()
    return item


async def _ensure_delivery_artifacts(session, shipment_id: int, assignment_id: int) -> None:
    attempts = await session.execute(select(DeliveryAttempt).where(DeliveryAttempt.shipment_id == shipment_id))
    for row in attempts.scalars().all():
        await session.delete(row)

    pods = await session.execute(select(ProofOfDelivery).where(ProofOfDelivery.shipment_id == shipment_id))
    for row in pods.scalars().all():
        await session.delete(row)

    session.add(
        DeliveryAttempt(
            shipment_id=shipment_id,
            assignment_id=assignment_id,
            attempted_at=datetime.utcnow() - timedelta(minutes=20),
            success=True,
            notes="Delivered to front desk",
        )
    )
    session.add(
        ProofOfDelivery(
            shipment_id=shipment_id,
            assignment_id=assignment_id,
            recipient_name="QA Receiver",
            signature_text="QA SIGNATURE",
            photo_url="https://example.test/pod/qa-delivered.jpg",
            delivered_at=datetime.utcnow() - timedelta(minutes=18),
        )
    )
    await session.flush()


async def _ensure_notifications(session, admin_id: int, operator_id: int) -> None:
    for user_id in (admin_id, operator_id):
        rows = await session.execute(select(Notification).where(Notification.user_id == user_id))
        for row in rows.scalars().all():
            await session.delete(row)

    notifications = [
        Notification(
            user_id=admin_id,
            title="Security incident requires review",
            body="A high severity login anomaly was detected for qa_operator.",
            type=NotificationType.WARNING,
            is_read=False,
            extra_data={"module": "observability", "severity": "high"},
        ),
        Notification(
            user_id=admin_id,
            title="Shipment SHP-QA-001 is out for delivery",
            body="Driver has started the final delivery run.",
            type=NotificationType.INFO,
            is_read=False,
            extra_data={"shipment_reference": "SHP-QA-001"},
        ),
        Notification(
            user_id=operator_id,
            title="Welcome to QA tenant",
            body="You have been added to QA Logistics Org.",
            type=NotificationType.SUCCESS,
            is_read=True,
            extra_data={"tenant_slug": "qa-logistics"},
        ),
    ]
    for item in notifications:
        session.add(item)
    await session.flush()


async def _ensure_payments(session, user_id: int) -> None:
    for po in ("PO-QA-001", "PO-QA-002", "PO-QA-003"):
        result = await session.execute(
            select(PaymentTransaction).where(PaymentTransaction.purchase_order_id == po)
        )
        existing = result.scalars().first()
        if existing:
            await session.delete(existing)
    await session.flush()

    rows = [
        PaymentTransaction(
            provider=PaymentProvider.KHALTI,
            amount=120000,
            currency="NPR",
            status=PaymentStatus.COMPLETED,
            purchase_order_id="PO-QA-001",
            purchase_order_name="Linehaul invoice batch A",
            provider_transaction_id="TXN-QA-KHALTI-001",
            provider_pidx="PIDX-QA-001",
            return_url="http://localhost:3000/payment-callback",
            website_url="http://localhost:3000",
            user_id=user_id,
            extra_data='{"seed":"qa"}',
        ),
        PaymentTransaction(
            provider=PaymentProvider.ESEWA,
            amount=83000,
            currency="NPR",
            status=PaymentStatus.INITIATED,
            purchase_order_id="PO-QA-002",
            purchase_order_name="Warehouse handling",
            provider_transaction_id="TXN-QA-ESEWA-001",
            provider_pidx="REF-QA-001",
            return_url="http://localhost:3000/payment-callback",
            website_url="http://localhost:3000",
            user_id=user_id,
            extra_data='{"seed":"qa"}',
        ),
        PaymentTransaction(
            provider=PaymentProvider.KHALTI,
            amount=50000,
            currency="NPR",
            status=PaymentStatus.FAILED,
            purchase_order_id="PO-QA-003",
            purchase_order_name="Exception recovery charge",
            provider_transaction_id="TXN-QA-KHALTI-002",
            provider_pidx="PIDX-QA-003",
            return_url="http://localhost:3000/payment-callback",
            website_url="http://localhost:3000",
            user_id=user_id,
            failure_reason="Card declined in sandbox",
            extra_data='{"seed":"qa"}',
        ),
    ]
    for item in rows:
        session.add(item)
    await session.flush()


async def _ensure_observability(session, actor_user_id: int, subject_user_id: int) -> None:
    logs = await session.execute(
        select(ObservabilityLogEntry).where(ObservabilityLogEntry.event_code.like("qa.seed.%"))
    )
    for row in logs.scalars().all():
        await session.delete(row)

    incidents = await session.execute(
        select(SecurityIncident).where(SecurityIncident.fingerprint.like("qa-seed-%"))
    )
    for row in incidents.scalars().all():
        await session.delete(row)
    await session.flush()

    entry_high = ObservabilityLogEntry(
        level="WARNING",
        logger_name="qa.seed",
        source="auth",
        message="Multiple failed login attempts detected for qa_operator",
        event_code="qa.seed.login_spike",
        request_id="qa-seed-req-001",
        method="POST",
        path="/api/v1/auth/login/",
        status_code=400,
        duration_ms=128,
        user_id=subject_user_id,
        ip_address="127.0.0.1",
        user_agent="QA Runner",
        metadata_json={"seed": "qa", "attempts": 6},
    )
    session.add(entry_high)
    await session.flush()

    entry_medium = ObservabilityLogEntry(
        level="INFO",
        logger_name="qa.seed",
        source="rbac",
        message="Role assignment updated by qa_admin",
        event_code="qa.seed.role_change",
        request_id="qa-seed-req-002",
        method="POST",
        path="/api/v1/users/assign-role",
        status_code=200,
        duration_ms=74,
        user_id=actor_user_id,
        ip_address="127.0.0.1",
        user_agent="QA Runner",
        metadata_json={"seed": "qa", "role": "Dispatcher"},
    )
    session.add(entry_medium)
    await session.flush()

    session.add(
        SecurityIncident(
            signal_type="failed_login_burst",
            severity="high",
            status="open",
            title="Repeated failed logins for qa_operator",
            summary="Detected six failed login attempts within 10 minutes from local QA IP.",
            fingerprint="qa-seed-login-burst",
            occurrence_count=6,
            first_seen_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            last_seen_at=datetime.now(timezone.utc) - timedelta(minutes=3),
            actor_user_id=None,
            subject_user_id=subject_user_id,
            ip_address="127.0.0.1",
            related_log_id=entry_high.id,
            metadata_json={"seed": "qa", "threshold": 5},
            review_notes="Seeded incident for manual admin security review page.",
        )
    )
    session.add(
        SecurityIncident(
            signal_type="privilege_change",
            severity="medium",
            status="acknowledged",
            title="Administrative role assignment activity",
            summary="qa_admin assigned dispatcher role to qa_dispatcher for workload balancing.",
            fingerprint="qa-seed-role-change",
            occurrence_count=1,
            first_seen_at=datetime.now(timezone.utc) - timedelta(hours=2),
            last_seen_at=datetime.now(timezone.utc) - timedelta(hours=2),
            actor_user_id=actor_user_id,
            subject_user_id=subject_user_id,
            ip_address="127.0.0.1",
            related_log_id=entry_medium.id,
            metadata_json={"seed": "qa", "action": "assign_role"},
            review_notes="Seeded acknowledged incident for status workflow checks.",
        )
    )
    await session.flush()


async def seed_qa_data() -> None:
    await init_db()
    async with async_session_factory() as session:
        admin = await _ensure_user(
            session,
            username="qa_admin",
            email="qa_admin@example.com",
            password="Admin1234",
            is_superuser=True,
            first_name="QA",
            last_name="Admin",
            phone="+9779800000001",
        )
        operator = await _ensure_user(
            session,
            username="qa_operator",
            email="qa_operator@example.com",
            password="User12345",
            is_superuser=False,
            first_name="QA",
            last_name="Operator",
            phone="+9779800000002",
        )
        dispatcher = await _ensure_user(
            session,
            username="qa_dispatcher",
            email="qa_dispatcher@example.com",
            password="User12345",
            is_superuser=False,
            first_name="QA",
            last_name="Dispatcher",
            phone="+9779800000003",
        )

        role_admin = await _ensure_role(session, "Logistics Admin", "Full control over logistics operations")
        role_dispatcher = await _ensure_role(session, "Dispatcher", "Manage assignments and route execution")
        role_viewer = await _ensure_role(session, "Viewer", "Read-only access to shipment operations")

        perm_shipments_read = await _ensure_permission(session, "shipments", "read", "Read shipment records")
        perm_shipments_write = await _ensure_permission(session, "shipments", "write", "Create or update shipment records")
        perm_dispatch_manage = await _ensure_permission(session, "dispatch", "manage", "Manage dispatch assignments and exceptions")

        await _ensure_role_permission(session, role_admin.id, perm_shipments_read.id)
        await _ensure_role_permission(session, role_admin.id, perm_shipments_write.id)
        await _ensure_role_permission(session, role_admin.id, perm_dispatch_manage.id)
        await _ensure_role_permission(session, role_dispatcher.id, perm_shipments_read.id)
        await _ensure_role_permission(session, role_dispatcher.id, perm_dispatch_manage.id)
        await _ensure_role_permission(session, role_viewer.id, perm_shipments_read.id)

        await _ensure_user_role(session, admin.id, role_admin.id)
        await _ensure_user_role(session, dispatcher.id, role_dispatcher.id)
        await _ensure_user_role(session, operator.id, role_viewer.id)

        tenant = await _ensure_tenant(session, owner_id=admin.id)
        await _ensure_tenant_member(session, tenant.id, admin.id, TenantRole.OWNER)
        await _ensure_tenant_member(session, tenant.id, dispatcher.id, TenantRole.ADMIN)
        await _ensure_tenant_member(session, tenant.id, operator.id, TenantRole.MEMBER)
        await _ensure_invitation(session, tenant.id, invited_by=admin.id)

        hub_origin = await _ensure_hub(
            session,
            code="KTM-HUB",
            name="Kathmandu Origin Hub",
            address="Koteshwor, Kathmandu",
            lat=27.678,
            lon=85.349,
        )
        hub_mid = await _ensure_hub(
            session,
            code="BRT-HUB",
            name="Biratnagar Transit Hub",
            address="Biratnagar Industrial Area",
            lat=26.452,
            lon=87.271,
        )
        hub_dest = await _ensure_hub(
            session,
            code="PKR-HUB",
            name="Pokhara Destination Hub",
            address="Lakeside, Pokhara",
            lat=28.209,
            lon=83.985,
        )

        route = await _ensure_route(session, "QA-NEPAL-1", "Kathmandu to Pokhara Priority Corridor")
        await _ensure_route_leg(session, route.id, hub_origin.id, hub_mid.id, 1)
        await _ensure_route_leg(session, route.id, hub_mid.id, hub_dest.id, 2)

        vehicle_van = await _ensure_vehicle(session, "QA-VAN-01", "van", 1200)
        vehicle_truck = await _ensure_vehicle(session, "QA-TRUCK-01", "truck", 5000)

        driver_dispatch = await _ensure_driver(
            session,
            name="Suman Gurung",
            phone="+9779811111111",
            license_number="NP-QA-DL-001",
            user_id=dispatcher.id,
        )
        driver_general = await _ensure_driver(
            session,
            name="Rita Karki",
            phone="+9779822222222",
            license_number="NP-QA-DL-002",
        )

        shipment_one = await _ensure_shipment(
            session,
            reference="SHP-QA-001",
            token="qa-track-001",
            customer_name="Apex Retail",
            customer_contact="+9779801231001",
            origin="Kathmandu Warehouse 1",
            destination="Pokhara Lakeside Store",
            status=ShipmentStatus.OUT_FOR_DELIVERY,
            tenant_id=tenant.id,
        )
        shipment_two = await _ensure_shipment(
            session,
            reference="SHP-QA-002",
            token="qa-track-002",
            customer_name="Himalaya Pharma",
            customer_contact="+9779801231002",
            origin="Kathmandu Cold Storage",
            destination="Dharan Distribution Point",
            status=ShipmentStatus.DELAYED,
            tenant_id=tenant.id,
        )
        shipment_three = await _ensure_shipment(
            session,
            reference="SHP-QA-003",
            token="qa-track-003",
            customer_name="Everest Electronics",
            customer_contact="+9779801231003",
            origin="Biratnagar DC",
            destination="Pokhara Service Center",
            status=ShipmentStatus.DELIVERED,
            tenant_id=tenant.id,
        )

        await _create_shipment_timeline(
            session,
            shipment_one,
            actor_user_id=admin.id,
            statuses=[
                ShipmentStatus.CREATED,
                ShipmentStatus.CONFIRMED,
                ShipmentStatus.AT_ORIGIN_HUB,
                ShipmentStatus.IN_TRANSIT,
                ShipmentStatus.AT_DESTINATION_HUB,
                ShipmentStatus.OUT_FOR_DELIVERY,
            ],
        )
        await _create_shipment_timeline(
            session,
            shipment_two,
            actor_user_id=dispatcher.id,
            statuses=[
                ShipmentStatus.CREATED,
                ShipmentStatus.CONFIRMED,
                ShipmentStatus.AT_ORIGIN_HUB,
                ShipmentStatus.IN_TRANSIT,
                ShipmentStatus.DELAYED,
            ],
        )
        await _create_shipment_timeline(
            session,
            shipment_three,
            actor_user_id=dispatcher.id,
            statuses=[
                ShipmentStatus.CREATED,
                ShipmentStatus.CONFIRMED,
                ShipmentStatus.AT_ORIGIN_HUB,
                ShipmentStatus.IN_TRANSIT,
                ShipmentStatus.AT_DESTINATION_HUB,
                ShipmentStatus.OUT_FOR_DELIVERY,
                ShipmentStatus.DELIVERED,
            ],
        )

        assignment_one = await _upsert_assignment(
            session,
            shipment_id=shipment_one.id,
            driver_id=driver_dispatch.id,
            vehicle_id=vehicle_van.id,
            route_id=route.id,
            status="in_progress",
        )
        assignment_two = await _upsert_assignment(
            session,
            shipment_id=shipment_two.id,
            driver_id=driver_general.id,
            vehicle_id=vehicle_truck.id,
            route_id=route.id,
            status="blocked",
        )
        assignment_three = await _upsert_assignment(
            session,
            shipment_id=shipment_three.id,
            driver_id=driver_dispatch.id,
            vehicle_id=vehicle_van.id,
            route_id=route.id,
            status="completed",
        )

        await _seed_checkpoints(session, shipment_one.id)
        await _ensure_exception(session, shipment_two.id, assignment_two.id)
        await _ensure_delivery_artifacts(session, shipment_three.id, assignment_three.id)

        await _ensure_notifications(session, admin.id, operator.id)
        await _ensure_payments(session, admin.id)
        await _ensure_observability(session, actor_user_id=admin.id, subject_user_id=operator.id)

        await session.commit()

    print("QA seed completed successfully.")
    print("Users: qa_admin / Admin1234, qa_operator / User12345, qa_dispatcher / User12345")
    print("Public tracking tokens: qa-track-001, qa-track-002, qa-track-003")


if __name__ == "__main__":
    import asyncio

    asyncio.run(seed_qa_data())
