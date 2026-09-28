import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useAuth } from "@/hooks/useAuth";
import Dashboard from "@/pages/dashboard";
import Landing from "@/pages/landing";
import Home from "@/pages/home";
import Login from "@/pages/login";
import Admin from "@/pages/admin";
import ControlCenter from "@/pages/control-center";
import DoctorLogin from "@/pages/doctor-login";
import DoctorDashboard from "@/pages/doctor-dashboard";
import ReceptionLogin from "@/pages/reception-login";
import Appointments from "@/pages/appointments";
import DepartmentMonitoring from "@/pages/department-monitoring";
import DepartmentStatistics from "@/pages/department-statistics";
import ReceptionDesk from "@/pages/reception-desk";
import ClinicOverview from "@/pages/clinic-overview";
import ClinicDayView from "@/pages/clinic-day-view";
import OvertimePortal from "@/pages/overtime-portal";
import CallCenterLogin from "@/pages/callcenter-login";
import ExamSchedule from "@/pages/exam-schedule";
import NotFound from "@/pages/not-found";

const LoadingScreen = () => (
  <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-blue-50 via-teal-50 to-indigo-100">
    <div className="text-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
      <p className="text-gray-600 dark:text-gray-300">Loading...</p>
    </div>
  </div>
);

function Router() {
  const { isAuthenticated, isLoading } = useAuth();

  return (
    <Switch>
      {/* Always-accessible routes — matched before any auth check */}
      <Route path="/doctor-login" component={DoctorLogin} />
      <Route path="/doctor-dashboard" component={DoctorDashboard} />
      <Route path="/overtime" component={OvertimePortal} />
      <Route path="/callcenter-login" component={CallCenterLogin} />
      <Route path="/exam-schedule" component={ExamSchedule} />

      {/* Authenticated routes — wait for auth to resolve */}
      {isLoading ? (
        <Route path="*" component={LoadingScreen} />
      ) : !isAuthenticated ? (
        <>
          <Route path="/" component={Landing} />
          <Route path="/login" component={Login} />
          <Route path="/reception-login" component={ReceptionLogin} />
        </>
      ) : (
        <>
          <Route path="/" component={Home} />
          <Route path="/dashboard" component={Dashboard} />
          <Route path="/admin" component={Admin} />
          <Route path="/control-center" component={ControlCenter} />
          <Route path="/appointments" component={Appointments} />
          <Route path="/department-monitoring" component={DepartmentMonitoring} />
          <Route path="/department-statistics" component={DepartmentStatistics} />
          <Route path="/reception-desk" component={ReceptionDesk} />
          <Route path="/clinic-overview" component={ClinicOverview} />
          <Route path="/clinic-day" component={ClinicDayView} />
          <Route path="/login" component={Login} />
        </>
      )}
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Router />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
