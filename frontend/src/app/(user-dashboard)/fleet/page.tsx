'use client';

import { useCreateDriver, useCreateVehicle, useDrivers, useVehicles } from '@/hooks/use-logistics';
import { useState } from 'react';

export default function FleetDriversPage() {
  const { data: drivers = [] } = useDrivers();
  const { data: vehicles = [] } = useVehicles();
  const createVehicle = useCreateVehicle();
  const createDriver = useCreateDriver();
  const [vehicleForm, setVehicleForm] = useState({ code: '', type: '', capacity_kg: 0 });
  const [driverForm, setDriverForm] = useState({ name: '', phone: '', license_number: '' });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Fleet & Drivers</h1>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <section className="rounded border p-4 space-y-3">
          <h2 className="font-medium">Vehicles</h2>
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              createVehicle.mutate({ ...vehicleForm, is_active: true });
              setVehicleForm({ code: '', type: '', capacity_kg: 0 });
            }}
          >
            <input className="w-full rounded border px-2 py-1" placeholder="Code" value={vehicleForm.code} onChange={(event) => setVehicleForm((prev) => ({ ...prev, code: event.target.value }))} required />
            <input className="w-full rounded border px-2 py-1" placeholder="Type" value={vehicleForm.type} onChange={(event) => setVehicleForm((prev) => ({ ...prev, type: event.target.value }))} required />
            <input className="w-full rounded border px-2 py-1" placeholder="Capacity kg" type="number" value={vehicleForm.capacity_kg} onChange={(event) => setVehicleForm((prev) => ({ ...prev, capacity_kg: Number(event.target.value) }))} required />
            <button className="rounded bg-blue-600 px-3 py-1 text-white" type="submit">Add Vehicle</button>
          </form>
          <ul className="space-y-2 text-sm">
            {vehicles.length === 0 ? <li>No vehicles.</li> : vehicles.map((vehicle) => (
              <li key={vehicle.id} className="rounded border px-3 py-2">{vehicle.code} · {vehicle.type} · {vehicle.capacity_kg}kg</li>
            ))}
          </ul>
        </section>
        <section className="rounded border p-4 space-y-3">
          <h2 className="font-medium">Drivers</h2>
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              createDriver.mutate(driverForm);
              setDriverForm({ name: '', phone: '', license_number: '' });
            }}
          >
            <input className="w-full rounded border px-2 py-1" placeholder="Name" value={driverForm.name} onChange={(event) => setDriverForm((prev) => ({ ...prev, name: event.target.value }))} required />
            <input className="w-full rounded border px-2 py-1" placeholder="Phone" value={driverForm.phone} onChange={(event) => setDriverForm((prev) => ({ ...prev, phone: event.target.value }))} required />
            <input className="w-full rounded border px-2 py-1" placeholder="License number" value={driverForm.license_number} onChange={(event) => setDriverForm((prev) => ({ ...prev, license_number: event.target.value }))} required />
            <button className="rounded bg-blue-600 px-3 py-1 text-white" type="submit">Add Driver</button>
          </form>
          <ul className="space-y-2 text-sm">
            {drivers.length === 0 ? <li>No drivers.</li> : drivers.map((driver) => (
              <li key={driver.id} className="rounded border px-3 py-2">{driver.name} · {driver.phone} · {driver.is_available ? 'Available' : 'Unavailable'}</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
