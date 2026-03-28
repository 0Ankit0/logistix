import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/providers/dio_provider.dart';
import 'logistics_models.dart';

class LogisticsRepository {
  LogisticsRepository(this._read);
  final Ref _read;

  Future<List<DriverAssignment>> listAssignments() async {
    final dio = _read.read(dioClientProvider);
    final response = await dio.get(ApiEndpoints.dispatchAssignments);
    final data = response.data as List<dynamic>;
    return data
        .map((item) => DriverAssignment.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<void> updateAssignmentStatus({
    required int assignmentId,
    required String status,
  }) async {
    final dio = _read.read(dioClientProvider);
    await dio.patch('${ApiEndpoints.dispatchAssignments}/$assignmentId', data: {
      'status': status,
    });
  }

  Future<void> reportException({
    required int shipmentId,
    int? assignmentId,
    required String details,
  }) async {
    final dio = _read.read(dioClientProvider);
    await dio.post(ApiEndpoints.dispatchExceptions, data: {
      'shipment_id': shipmentId,
      'assignment_id': assignmentId,
      'exception_type': 'failed_attempt',
      'details': details,
    });
  }

  Future<void> submitCheckpoint({
    required int shipmentId,
    required String locationLabel,
  }) async {
    final dio = _read.read(dioClientProvider);
    await dio.post(ApiEndpoints.trackingCheckpoints, data: {
      'shipment_id': shipmentId,
      'location_label': locationLabel,
    });
  }

  Future<void> submitProofOfDelivery({
    required int shipmentId,
    int? assignmentId,
    required String recipientName,
  }) async {
    final dio = _read.read(dioClientProvider);
    await dio.post(ApiEndpoints.dispatchProofOfDelivery, data: {
      'shipment_id': shipmentId,
      'assignment_id': assignmentId,
      'recipient_name': recipientName,
    });
  }
}

final logisticsRepositoryProvider = Provider<LogisticsRepository>((ref) {
  return LogisticsRepository(ref);
});
