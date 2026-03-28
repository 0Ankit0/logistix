import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import type {
  DeliveryException,
  Driver,
  DriverAssignment,
  Hub,
  Route,
  Shipment,
  ShipmentStatus,
  Vehicle,
} from '@/types/logistics';

export function useShipments() {
  return useQuery({
    queryKey: ['logistics', 'shipments'],
    queryFn: async () => (await apiClient.get<Shipment[]>('/shipments')).data,
  });
}

export function useCreateShipment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      customer_name: string;
      customer_contact: string;
      origin_address: string;
      destination_address: string;
      tenant_id?: number | null;
    }) => (await apiClient.post<Shipment>('/shipments', payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['logistics', 'shipments'] }),
  });
}

export function useTransitionShipmentStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ shipmentId, status, message }: { shipmentId: number; status: ShipmentStatus; message: string }) =>
      (await apiClient.patch<Shipment>(`/shipments/${shipmentId}/status`, { status, message })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['logistics', 'shipments'] }),
  });
}

export function useDispatchAssignments() {
  return useQuery({
    queryKey: ['logistics', 'assignments'],
    queryFn: async () => (await apiClient.get<DriverAssignment[]>('/dispatch/assignments')).data,
  });
}

export function useCreateAssignment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { shipment_id: number; driver_id: number; vehicle_id?: number | null; route_id?: number | null }) =>
      (await apiClient.post<DriverAssignment>('/dispatch/assignments', payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['logistics', 'assignments'] }),
  });
}

export function useExceptions() {
  return useQuery({
    queryKey: ['logistics', 'exceptions'],
    queryFn: async () => (await apiClient.get<DeliveryException[]>('/dispatch/exceptions', { params: { only_open: true } })).data,
  });
}

export function useResolveException() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ exceptionId, resolution_notes }: { exceptionId: number; resolution_notes: string }) =>
      (await apiClient.post(`/dispatch/exceptions/${exceptionId}/resolve`, { resolution_notes })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['logistics', 'exceptions'] }),
  });
}

export function useHubs() {
  return useQuery({
    queryKey: ['logistics', 'hubs'],
    queryFn: async () => (await apiClient.get<Hub[]>('/hubs')).data,
  });
}

export function useRoutes() {
  return useQuery({
    queryKey: ['logistics', 'routes'],
    queryFn: async () => (await apiClient.get<Route[]>('/routes')).data,
  });
}

export function useVehicles() {
  return useQuery({
    queryKey: ['logistics', 'vehicles'],
    queryFn: async () => (await apiClient.get<Vehicle[]>('/fleet/vehicles')).data,
  });
}

export function useDrivers() {
  return useQuery({
    queryKey: ['logistics', 'drivers'],
    queryFn: async () => (await apiClient.get<Driver[]>('/fleet/drivers')).data,
  });
}


export function useCreateHub() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { code: string; name: string; address: string }) =>
      (await apiClient.post<Hub>('/hubs', payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['logistics', 'hubs'] }),
  });
}

export function useCreateRoute() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { code: string; name: string; is_active?: boolean }) =>
      (await apiClient.post<Route>('/routes', payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['logistics', 'routes'] }),
  });
}

export function useCreateVehicle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { code: string; type: string; capacity_kg: number; is_active?: boolean }) =>
      (await apiClient.post<Vehicle>('/fleet/vehicles', payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['logistics', 'vehicles'] }),
  });
}

export function useCreateDriver() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { name: string; phone: string; license_number: string }) =>
      (await apiClient.post<Driver>('/fleet/drivers', payload)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['logistics', 'drivers'] }),
  });
}
