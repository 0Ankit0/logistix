from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.apps.iam.models import Permission, Role, RolePermission

LOGISTICS_RESOURCES = [
    "shipments",
    "tracking",
    "hubs",
    "routes",
    "fleet",
    "drivers",
    "dispatch",
    "exceptions",
    "proof_of_delivery",
]

LOGISTICS_ROLES = [
    ("operations_admin", "Operations administrator for logistics platform"),
    ("dispatcher", "Manages assignments, route execution, and exceptions"),
    ("driver", "Executes assignments and updates shipment checkpoints"),
    ("customer_support", "Supports customers with shipment lookups and updates"),
    ("customer_viewer", "Read-only customer shipment and tracking visibility"),
]

ROLE_ACTIONS = {
    "operations_admin": {"read", "write", "delete"},
    "dispatcher": {"read", "write"},
    "driver": {"read", "write"},
    "customer_support": {"read", "write"},
    "customer_viewer": {"read"},
}


async def seed_logistics_rbac(session: AsyncSession) -> None:
    role_lookup: dict[str, Role] = {}
    for name, description in LOGISTICS_ROLES:
        result = await session.execute(select(Role).where(Role.name == name))
        role = result.scalars().first()
        if role is None:
            role = Role(name=name, description=description)
            session.add(role)
            await session.flush()
        role_lookup[name] = role

    permission_lookup: dict[tuple[str, str], Permission] = {}
    for resource in LOGISTICS_RESOURCES:
        for action in ["read", "write", "delete"]:
            result = await session.execute(
                select(Permission).where(Permission.resource == resource, Permission.action == action)
            )
            permission = result.scalars().first()
            if permission is None:
                permission = Permission(
                    resource=resource,
                    action=action,
                    description=f"{action} access for {resource}",
                )
                session.add(permission)
                await session.flush()
            permission_lookup[(resource, action)] = permission

    for role_name, role in role_lookup.items():
        allowed = ROLE_ACTIONS.get(role_name, {"read"})
        for resource in LOGISTICS_RESOURCES:
            for action in allowed:
                permission = permission_lookup[(resource, action)]
                result = await session.execute(
                    select(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id == permission.id,
                    )
                )
                if result.scalars().first() is None:
                    session.add(RolePermission(role_id=role.id, permission_id=permission.id))

    await session.commit()
