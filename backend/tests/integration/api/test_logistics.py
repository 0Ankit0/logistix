import pytest

from src.apps.iam.api.deps import get_current_user
from src.apps.iam.models.user import User


@pytest.mark.asyncio
async def test_shipment_lifecycle_and_public_tracking(client):
    app = client._transport.app
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        username="dispatcher",
        email="dispatcher@example.com",
        hashed_password="x",
        is_active=True,
        is_confirmed=True,
    )

    created = await client.post(
        "/api/v1/shipments",
        json={
            "customer_name": "Jane Doe",
            "customer_contact": "5551234567",
            "origin_address": "Origin Hub",
            "destination_address": "Destination Address",
            "tenant_id": None,
        },
    )
    assert created.status_code == 201
    shipment = created.json()

    transition = await client.patch(
        f"/api/v1/shipments/{shipment['id']}/status",
        json={"status": "confirmed", "message": "Confirmed by dispatcher"},
    )
    assert transition.status_code == 200
    assert transition.json()["current_status"] == "confirmed"

    tracking = await client.get(f"/api/v1/tracking/{shipment['public_tracking_token']}")
    assert tracking.status_code == 200
    assert tracking.json()["shipment"]["reference"].startswith("SHP-")

    internal_tracking = await client.get(f"/api/v1/tracking/internal/{shipment['id']}")
    assert internal_tracking.status_code == 200

    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_dispatch_exception_and_resolution(client):
    app = client._transport.app
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        username="dispatcher",
        email="dispatcher@example.com",
        hashed_password="x",
        is_active=True,
        is_confirmed=True,
    )

    created = await client.post(
        "/api/v1/shipments",
        json={
            "customer_name": "John Doe",
            "customer_contact": "5551234567",
            "origin_address": "Hub A",
            "destination_address": "Hub B",
            "tenant_id": None,
        },
    )
    shipment = created.json()

    raised = await client.post(
        "/api/v1/dispatch/exceptions",
        json={
            "shipment_id": shipment["id"],
            "assignment_id": None,
            "exception_type": "failed_attempt",
            "details": "Receiver unavailable",
        },
    )
    assert raised.status_code == 201

    exception_id = raised.json()["id"]
    resolved = await client.post(f"/api/v1/dispatch/exceptions/{exception_id}/resolve", json={"resolution_notes": "Resolved and reassigned"})
    assert resolved.status_code == 200
    assert resolved.json()["is_resolved"] is True

    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_network_and_fleet_crud_surface(client):
    app = client._transport.app
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        username="ops_admin",
        email="ops@example.com",
        hashed_password="x",
        is_active=True,
        is_confirmed=True,
    )

    hub = await client.post('/api/v1/hubs', json={
        'code': 'HUB-A', 'name': 'Hub A', 'address': 'Address A', 'latitude': 10.0, 'longitude': 20.0,
    })
    assert hub.status_code == 201
    hub_id = hub.json()['id']

    route = await client.post('/api/v1/routes', json={'code': 'R-1', 'name': 'Route 1', 'is_active': True})
    assert route.status_code == 201
    route_id = route.json()['id']

    leg = await client.post(f'/api/v1/routes/{route_id}/legs', json={
        'from_hub_id': hub_id, 'to_hub_id': hub_id, 'sequence': 1,
    })
    assert leg.status_code == 201

    vehicle = await client.post('/api/v1/fleet/vehicles', json={'code': 'VAN-1', 'type': 'van', 'capacity_kg': 1000, 'is_active': True})
    assert vehicle.status_code == 201

    driver = await client.post('/api/v1/fleet/drivers', json={'name': 'Driver 1', 'phone': '+15551234567', 'license_number': 'LIC-1'})
    assert driver.status_code == 201

    app.dependency_overrides.pop(get_current_user, None)
