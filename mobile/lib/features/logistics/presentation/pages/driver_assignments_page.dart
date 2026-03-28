import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/logistics_provider.dart';
import '../../data/logistics_repository.dart';

class DriverAssignmentsPage extends ConsumerWidget {
  const DriverAssignmentsPage({super.key});

  Future<void> _reportExceptionDialog(
    BuildContext context,
    WidgetRef ref,
    int shipmentId,
    int assignmentId,
  ) async {
    final controller = TextEditingController();
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Report Exception'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(hintText: 'Describe issue'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              await ref.read(logisticsRepositoryProvider).reportException(
                    shipmentId: shipmentId,
                    assignmentId: assignmentId,
                    details: controller.text.trim().isEmpty
                        ? 'Driver-reported exception from mobile app'
                        : controller.text.trim(),
                  );
              if (context.mounted) Navigator.pop(context);
              ref.invalidate(driverAssignmentsProvider);
            },
            child: const Text('Submit'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final assignmentsAsync = ref.watch(driverAssignmentsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Driver Assignments')),
      body: assignmentsAsync.when(
        data: (assignments) => ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: assignments.length,
          itemBuilder: (context, index) {
            final assignment = assignments[index];
            return Card(
              child: ListTile(
                title: Text('Shipment #${assignment.shipmentId}'),
                subtitle: Text('Assignment ${assignment.id} · ${assignment.status}'),
                trailing: PopupMenuButton<String>(
                  onSelected: (value) async {
                    final repo = ref.read(logisticsRepositoryProvider);
                    if (value == 'checkpoint') {
                      await repo.submitCheckpoint(
                        shipmentId: assignment.shipmentId,
                        locationLabel: 'Checkpoint from driver app',
                      );
                    }
                    if (value == 'in_transit') {
                      await repo.updateAssignmentStatus(
                        assignmentId: assignment.id,
                        status: 'in_transit',
                      );
                    }
                    if (value == 'deliver') {
                      await repo.submitProofOfDelivery(
                        shipmentId: assignment.shipmentId,
                        assignmentId: assignment.id,
                        recipientName: 'Customer',
                      );
                      await repo.updateAssignmentStatus(
                        assignmentId: assignment.id,
                        status: 'completed',
                      );
                    }
                    if (value == 'exception') {
                      await _reportExceptionDialog(
                        context,
                        ref,
                        assignment.shipmentId,
                        assignment.id,
                      );
                    }
                    ref.invalidate(driverAssignmentsProvider);
                  },
                  itemBuilder: (context) => const [
                    PopupMenuItem(value: 'in_transit', child: Text('Mark in transit')),
                    PopupMenuItem(value: 'checkpoint', child: Text('Submit checkpoint')),
                    PopupMenuItem(value: 'deliver', child: Text('Mark delivered')),
                    PopupMenuItem(value: 'exception', child: Text('Report exception')),
                  ],
                ),
              ),
            );
          },
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Failed to load assignments: $error')),
      ),
    );
  }
}
