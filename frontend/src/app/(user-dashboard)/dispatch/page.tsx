'use client';

import { useCreateAssignment, useDispatchAssignments, useDrivers, useShipments, useVehicles } from '@/hooks/use-logistics';
import { useState } from 'react';

export default function DispatchPage() {
  const { data: assignments = [] } = useDispatchAssignments();
  const { data: shipments = [] } = useShipments();
  const { data: drivers = [] } = useDrivers();
  const { data: vehicles = [] } = useVehicles();
  const createAssignment = useCreateAssignment();
  const [shipmentId, setShipmentId] = useState<number | undefined>();
  const [driverId, setDriverId] = useState<number | undefined>();
  const [vehicleId, setVehicleId] = useState<number | undefined>();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dispatch Board</h1>
      <div className="rounded border p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Create Assignment</h2>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <select className="rounded border px-2 py-2" onChange={(event) => setShipmentId(Number(event.target.value))}>
            <option value="">Select shipment</option>
            {shipments.map((shipment) => <option key={shipment.id} value={shipment.id}>{shipment.reference}</option>)}
          </select>
          <select className="rounded border px-2 py-2" onChange={(event) => setDriverId(Number(event.target.value))}>
            <option value="">Select driver</option>
            {drivers.map((driver) => <option key={driver.id} value={driver.id}>{driver.name}</option>)}
          </select>
          <select className="rounded border px-2 py-2" onChange={(event) => setVehicleId(Number(event.target.value))}>
            <option value="">Select vehicle</option>
            {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.code}</option>)}
          </select>
          <button
            className="rounded bg-blue-600 px-4 py-2 text-white"
            onClick={() => {
              if (!shipmentId || !driverId) return;
              createAssignment.mutate({ shipment_id: shipmentId, driver_id: driverId, vehicle_id: vehicleId });
            }}
          >
            Assign
          </button>
        </div>
      </div>
      <div className="rounded border p-4">
        <p className="mb-3 text-sm text-gray-600">Live assignment workload for dispatcher workflows.</p>
        <ul className="space-y-2 text-sm">
          {assignments.length === 0 ? <li>No assignments yet.</li> : assignments.map((assignment) => (
            <li key={assignment.id} className="rounded border px-3 py-2">
              Assignment #{assignment.id} · Shipment {assignment.shipment_id} · Driver {assignment.driver_id} · {assignment.status}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
