'use client';

import { useCreateHub, useCreateRoute, useHubs, useRoutes } from '@/hooks/use-logistics';
import { useState } from 'react';

export default function HubsRoutesPage() {
  const { data: hubs = [] } = useHubs();
  const { data: routes = [] } = useRoutes();
  const createHub = useCreateHub();
  const createRoute = useCreateRoute();
  const [hubForm, setHubForm] = useState({ code: '', name: '', address: '' });
  const [routeForm, setRouteForm] = useState({ code: '', name: '' });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Hubs & Routes</h1>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <section className="rounded border p-4 space-y-3">
          <h2 className="font-medium">Hubs</h2>
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              createHub.mutate(hubForm);
              setHubForm({ code: '', name: '', address: '' });
            }}
          >
            <input className="w-full rounded border px-2 py-1" placeholder="Code" value={hubForm.code} onChange={(event) => setHubForm((prev) => ({ ...prev, code: event.target.value }))} required />
            <input className="w-full rounded border px-2 py-1" placeholder="Name" value={hubForm.name} onChange={(event) => setHubForm((prev) => ({ ...prev, name: event.target.value }))} required />
            <input className="w-full rounded border px-2 py-1" placeholder="Address" value={hubForm.address} onChange={(event) => setHubForm((prev) => ({ ...prev, address: event.target.value }))} required />
            <button className="rounded bg-blue-600 px-3 py-1 text-white" type="submit">Add Hub</button>
          </form>
          <ul className="space-y-2 text-sm">
            {hubs.length === 0 ? <li>No hubs configured.</li> : hubs.map((hub) => (
              <li key={hub.id} className="rounded border px-3 py-2">{hub.code} · {hub.name}</li>
            ))}
          </ul>
        </section>
        <section className="rounded border p-4 space-y-3">
          <h2 className="font-medium">Routes</h2>
          <form
            className="space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              createRoute.mutate({ ...routeForm, is_active: true });
              setRouteForm({ code: '', name: '' });
            }}
          >
            <input className="w-full rounded border px-2 py-1" placeholder="Code" value={routeForm.code} onChange={(event) => setRouteForm((prev) => ({ ...prev, code: event.target.value }))} required />
            <input className="w-full rounded border px-2 py-1" placeholder="Name" value={routeForm.name} onChange={(event) => setRouteForm((prev) => ({ ...prev, name: event.target.value }))} required />
            <button className="rounded bg-blue-600 px-3 py-1 text-white" type="submit">Add Route</button>
          </form>
          <ul className="space-y-2 text-sm">
            {routes.length === 0 ? <li>No routes configured.</li> : routes.map((route) => (
              <li key={route.id} className="rounded border px-3 py-2">{route.code} · {route.name}</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
