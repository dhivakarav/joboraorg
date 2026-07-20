import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { Spinner } from "./components/UI";
import Layout from "./components/Layout";

import Login from "./pages/Login";
import Register from "./pages/Register";
import PendingApproval from "./pages/PendingApproval";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import VerifyEmail from "./pages/VerifyEmail";
import Extensions from "./pages/Extensions";

import Dashboard from "./pages/user/Dashboard";
import FindJobs from "./pages/user/FindJobs";
import MatchedJobs from "./pages/user/MatchedJobs";
import Resume from "./pages/user/Resume";
import Filters from "./pages/user/Filters";
import ActivityLog from "./pages/user/ActivityLog";
import VerificationCenter from "./pages/user/VerificationCenter";
import Settings from "./pages/user/Settings";

import AdminDashboard from "./pages/admin/AdminDashboard";
import UserManagement from "./pages/admin/UserManagement";
import AllApplications from "./pages/admin/AllApplications";
import Operations from "./pages/admin/Operations";

function RequireUser({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.is_admin) return <Navigate to="/admin/dashboard" replace />;
  if (user.status === "pending") return <Navigate to="/pending" replace />;
  if (user.status === "suspended") return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function RequireAdmin({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_admin) return <Navigate to="/app/dashboard" replace />;
  return <Layout admin>{children}</Layout>;
}

export default function App() {
  const { user, loading } = useAuth();

  return (
    <Routes>
      <Route
        path="/"
        element={
          loading ? (
            <Spinner />
          ) : user ? (
            <Navigate to={user.is_admin ? "/admin/dashboard" : "/app/dashboard"} replace />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route path="/extensions" element={<Extensions />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/pending" element={<PendingApproval />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />

      {/* User portal */}
      <Route path="/app/dashboard" element={<RequireUser><Dashboard /></RequireUser>} />
      <Route path="/app/jobs" element={<RequireUser><FindJobs /></RequireUser>} />
      <Route path="/app/matched" element={<RequireUser><MatchedJobs /></RequireUser>} />
      <Route path="/app/resume" element={<RequireUser><Resume /></RequireUser>} />
      <Route path="/app/filters" element={<RequireUser><Filters /></RequireUser>} />
      <Route path="/app/activity" element={<RequireUser><ActivityLog /></RequireUser>} />
      <Route path="/app/verification" element={<RequireUser><VerificationCenter /></RequireUser>} />
      <Route path="/app/settings" element={<RequireUser><Settings /></RequireUser>} />

      {/* Admin portal */}
      <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
      <Route path="/admin/dashboard" element={<RequireAdmin><AdminDashboard /></RequireAdmin>} />
      <Route path="/admin/users" element={<RequireAdmin><UserManagement /></RequireAdmin>} />
      <Route path="/admin/applications" element={<RequireAdmin><AllApplications /></RequireAdmin>} />
      <Route path="/admin/operations" element={<RequireAdmin><Operations /></RequireAdmin>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
