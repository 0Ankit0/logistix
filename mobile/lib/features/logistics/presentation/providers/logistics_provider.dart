import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/logistics_models.dart';
import '../../data/logistics_repository.dart';

final driverAssignmentsProvider = FutureProvider<List<DriverAssignment>>((ref) async {
  final repo = ref.read(logisticsRepositoryProvider);
  return repo.listAssignments();
});
