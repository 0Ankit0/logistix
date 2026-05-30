import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import { Providers } from '@/components/providers';
import AuthLayout from '@/app/(auth)/layout';
import UserDashboardLayout from '@/app/(user-dashboard)/layout';
import AdminDashboardLayout from '@/app/(admin-dashboard)/layout';
import HomePage from '@/app/page';
import LoginPage from '@/app/(auth)/login/page';
import SignupPage from '@/app/(auth)/signup/page';
import ForgotPasswordPage from '@/app/(auth)/forgot-password/page';
import ResetPasswordPage from '@/app/(auth)/reset-password/page';
import OtpVerifyPage from '@/app/(auth)/otp-verify/page';
import VerifyEmailPage from '@/app/(auth)/verify-email/page';
import AcceptInvitationPage from '@/app/(auth)/accept-invitation/page';
import AuthCallbackPage from '@/app/(auth)/auth-callback/page';
import PaymentCallbackPage from '@/app/(auth)/payment-callback/page';
import DashboardPage from '@/app/(user-dashboard)/dashboard/page';
import ShipmentsPage from '@/app/(user-dashboard)/shipments/page';
import TrackingPage from '@/app/(user-dashboard)/tracking/page';
import DispatchPage from '@/app/(user-dashboard)/dispatch/page';
import ProfilePage from '@/app/(user-dashboard)/profile/page';
import SettingsPage from '@/app/(user-dashboard)/settings/page';
import RbacPage from '@/app/(user-dashboard)/rbac/page';
import UserRoleManagePage from '@/app/(user-dashboard)/rbac/[roleId]/page';
import NotificationsPage from '@/app/(user-dashboard)/notifications/page';
import FinancesPage from '@/app/(user-dashboard)/finances/page';
import ExceptionsPage from '@/app/(user-dashboard)/exceptions/page';
import FleetPage from '@/app/(user-dashboard)/fleet/page';
import HubsRoutesPage from '@/app/(user-dashboard)/hubs-routes/page';
import MapsPage from '@/app/(user-dashboard)/maps/page';
import TokensPage from '@/app/(user-dashboard)/tokens/page';
import TenantsPage from '@/app/(user-dashboard)/tenants/page';
import AdminLandingPage from '@/app/(admin-dashboard)/admin/dashboard/page';
import AdminUsersPage from '@/app/(admin-dashboard)/admin/users/page';
import AdminSecurityReviewPage from '@/app/(admin-dashboard)/admin/security-review/page';
import AdminRbacPage from '@/app/(admin-dashboard)/admin/rbac/page';
import AdminRoleManagePage from '@/app/(admin-dashboard)/admin/rbac/[roleId]/page';
import PublicTrackingPage from '@/app/track/[token]/page';

function RootProviders() {
  return (
    <Providers>
      <Outlet />
    </Providers>
  );
}

function AuthShell() {
  return (
    <AuthLayout>
      <Outlet />
    </AuthLayout>
  );
}

function UserDashboardShell() {
  return (
    <UserDashboardLayout>
      <Outlet />
    </UserDashboardLayout>
  );
}

function AdminDashboardShell() {
  return (
    <AdminDashboardLayout>
      <Outlet />
    </AdminDashboardLayout>
  );
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootProviders />,
    children: [
      { index: true, element: <HomePage /> },
      {
        element: <AuthShell />,
        children: [
          { path: 'login', element: <LoginPage /> },
          { path: 'signup', element: <SignupPage /> },
          { path: 'forgot-password', element: <ForgotPasswordPage /> },
          { path: 'reset-password', element: <ResetPasswordPage /> },
          { path: 'otp-verify', element: <OtpVerifyPage /> },
          { path: 'verify-email', element: <VerifyEmailPage /> },
          { path: 'accept-invitation', element: <AcceptInvitationPage /> },
          { path: 'auth-callback', element: <AuthCallbackPage /> },
          { path: 'payment-callback', element: <PaymentCallbackPage /> },
        ],
      },
      {
        element: <UserDashboardShell />,
        children: [
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'shipments', element: <ShipmentsPage /> },
          { path: 'tracking', element: <TrackingPage /> },
          { path: 'dispatch', element: <DispatchPage /> },
          { path: 'profile', element: <ProfilePage /> },
          { path: 'settings', element: <SettingsPage /> },
          { path: 'rbac', element: <RbacPage /> },
          {
            path: 'rbac/:roleId',
            element: <UserRoleManagePage />,
          },
          { path: 'notifications', element: <NotificationsPage /> },
          { path: 'finances', element: <FinancesPage /> },
          { path: 'exceptions', element: <ExceptionsPage /> },
          { path: 'fleet', element: <FleetPage /> },
          { path: 'hubs-routes', element: <HubsRoutesPage /> },
          { path: 'maps', element: <MapsPage /> },
          { path: 'tokens', element: <TokensPage /> },
          { path: 'tenants', element: <TenantsPage /> },
        ],
      },
      {
        element: <AdminDashboardShell />,
        children: [
          { path: 'admin/dashboard', element: <AdminLandingPage /> },
          { path: 'admin/users', element: <AdminUsersPage /> },
          { path: 'admin/security-review', element: <AdminSecurityReviewPage /> },
          { path: 'admin/rbac', element: <AdminRbacPage /> },
          {
            path: 'admin/rbac/:roleId',
            element: <AdminRoleManagePage />,
          },
        ],
      },
      { path: 'track/:token', element: <PublicTrackingPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
