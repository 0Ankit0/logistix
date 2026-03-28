'use client';

import { useCreateShipment, useShipments, useTransitionShipmentStatus } from '@/hooks/use-logistics';
import type { ShipmentStatus } from '@/types/logistics';
import { useState } from 'react';

const statusFlow: ShipmentStatus[] = [
  'created',
  'confirmed',
  'at_origin_hub',
  'in_transit',
  'at_destination_hub',
  'out_for_delivery',
  'delivered',
];

export default function ShipmentsPage() {
  const { data: shipments = [], isLoading } = useShipments();
  const createShipment = useCreateShipment();
  const transitionStatus = useTransitionShipmentStatus();
  const [form, setForm] = useState({ customer_name: '', customer_contact: '', origin_address: '', destination_address: '' });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Shipment Management</h1>
      <form
        className="grid grid-cols-1 gap-3 rounded border p-4 md:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          createShipment.mutate(form);
          setForm({ customer_name: '', customer_contact: '', origin_address: '', destination_address: '' });
        }}
      >
        {Object.entries(form).map(([key, value]) => (
          <input
            key={key}
            className="rounded border px-3 py-2"
            placeholder={key.replaceAll('_', ' ')}
            value={value}
            onChange={(event) => setForm((prev) => ({ ...prev, [key]: event.target.value }))}
            required
          />
        ))}
        <button className="rounded bg-blue-600 px-4 py-2 text-white" type="submit">Create shipment</button>
      </form>

      <div className="rounded border">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2">Reference</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Origin</th>
              <th className="px-3 py-2">Destination</th>
              <th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td className="px-3 py-2" colSpan={5}>Loading…</td></tr>
            ) : shipments.length === 0 ? (
              <tr><td className="px-3 py-2" colSpan={5}>No shipments yet.</td></tr>
            ) : shipments.map((shipment) => (
              <tr key={shipment.id} className="border-t align-top">
                <td className="px-3 py-2 font-medium">{shipment.reference}</td>
                <td className="px-3 py-2">{shipment.current_status}</td>
                <td className="px-3 py-2">{shipment.origin_address}</td>
                <td className="px-3 py-2">{shipment.destination_address}</td>
                <td className="px-3 py-2">
                  <select
                    className="rounded border px-2 py-1"
                    defaultValue={shipment.current_status}
                    onChange={(event) => transitionStatus.mutate({
                      shipmentId: shipment.id,
                      status: event.target.value as ShipmentStatus,
                      message: `Status moved to ${event.target.value}`,
                    })}
                  >
                    {statusFlow.map((statusValue) => (
                      <option key={statusValue} value={statusValue}>{statusValue}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
