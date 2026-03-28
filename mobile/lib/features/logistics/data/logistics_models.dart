class DriverAssignment {
  final int id;
  final int shipmentId;
  final int driverId;
  final String status;

  DriverAssignment({
    required this.id,
    required this.shipmentId,
    required this.driverId,
    required this.status,
  });

  factory DriverAssignment.fromJson(Map<String, dynamic> json) => DriverAssignment(
        id: json['id'] as int,
        shipmentId: json['shipment_id'] as int,
        driverId: json['driver_id'] as int,
        status: json['status'] as String? ?? 'assigned',
      );
}
