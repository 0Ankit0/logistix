export type ShipmentStatus =
  | 'created'
  | 'confirmed'
  | 'at_origin_hub'
  | 'in_transit'
  | 'at_destination_hub'
  | 'out_for_delivery'
  | 'delivered'
  | 'delayed'
  | 'failed'
  | 'returned'
  | 'cancelled';

export interface Shipment {
  id: number;
  reference: string;
  customer_name: string;
  customer_contact: string;
  origin_address: string;
  destination_address: string;
  current_status: ShipmentStatus;
  public_tracking_token: string;
  created_at: string;
  updated_at: string;
}

export interface DriverAssignment {
  id: number;
  shipment_id: number;
  driver_id: number;
  vehicle_id: number | null;
  route_id: number | null;
  status: string;
  assigned_at: string;
  completed_at: string | null;
}

export interface DeliveryException {
  id: number;
  shipment_id: number;
  assignment_id: number | null;
  exception_type: string;
  details: string;
  is_resolved: boolean;
  raised_at: string;
  resolved_at: string | null;
}

export interface Hub {
  id: number;
  code: string;
  name: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
}

export interface Route {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
}

export interface Vehicle {
  id: number;
  code: string;
  type: string;
  capacity_kg: number;
  is_active: boolean;
}

export interface Driver {
  id: number;
  user_id: number | null;
  name: string;
  phone: string;
  license_number: string;
  is_available: boolean;
}
