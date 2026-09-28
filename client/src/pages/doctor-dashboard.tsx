import { useState, useEffect, useMemo } from "react";
import { useLocation } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Calendar, Clock, Users, FileText, LogOut, CalendarDays, AlertCircle, User, Plus, ChevronLeft, ChevronRight, CalendarCheck, BarChart3, CheckCircle2, Building2, RefreshCw, TrendingUp, Stethoscope, Pencil } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { format, parseISO, startOfWeek, endOfWeek, addWeeks, subWeeks, addDays, subDays, isToday, startOfMonth, endOfMonth, subMonths } from "date-fns";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiRequest } from "@/lib/queryClient";
import { ProcedureQuestionnaire } from "@/components/procedure/procedure-questionnaire";
import { useWebSocket } from "@/hooks/useWebSocket";
import { PatientArrivalNotification } from "@/components/PatientArrivalNotification";

interface DoctorUser {
  id: number;
  name: string;
  title: string;
  departmentId: number;
  email: string;
  phone: string;
}

interface Appointment {
  id: number;
  appointmentDate: string;
  startTime: string;
  endTime: string;
  status: string;
  type: string;
  reasonForVisit?: string;
  notes?: string;
  patient: {
    id: number;
    firstName: string;
    lastName: string;
    phone: string;
    email?: string;
  };
  clinic?: {
    id: number;
    name: string;
  };
}

interface ClinicAssignment {
  id: number;
  weekday: number;
  clinic: {
    id: number;
    name: string;
    startTime: string;
    endTime: string;
  };
}

interface Leave {
  id: number;
  startDate: string;
  endDate: string;
  type: string;
  reason?: string;
}

interface Permission {
  id: number;
  date: string;
  type: string;
  startTime: string;
  endTime: string;
  reason?: string;
}

// ── Clinic-day timeline helpers ────────────────────────────────────────────
const parseTimeDr = (t: string) => {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
};
const minsToHHMMDr = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const formatTime12Dr = (t: string) => {
  const [h, m] = t.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  return `${((h % 12) || 12)}:${String(m).padStart(2, "0")} ${ampm}`;
};
const durationLabelDr = (mins: number) => {
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60), rem = mins % 60;
  return rem ? `${h}h ${rem}m` : `${h}h`;
};
const buildTimelineDr = (startStr: string, endStr: string, appointments: any[]) => {
  const startMin = parseTimeDr(startStr);
  const endMin = parseTimeDr(endStr);
  const sorted = [...appointments]
    .filter(a => a.status !== "cancelled")
    .sort((a, b) => parseTimeDr(a.startTime) - parseTimeDr(b.startTime));
  const blocks: any[] = [];
  let cursor = startMin;
  for (const appt of sorted) {
    const s = parseTimeDr(appt.startTime);
    const e = parseTimeDr(appt.endTime || appt.startTime);
    if (s > cursor) blocks.push({ kind: "free", startMin: cursor, endMin: s });
    blocks.push({ kind: "booked", startMin: s, endMin: e, appointment: appt });
    cursor = e;
  }
  if (cursor < endMin) blocks.push({ kind: "free", startMin: cursor, endMin: endMin });
  return blocks;
};

const procedureLabelsDr: Record<string, string> = {
  alginatePreparation: "Alginate Preparation",
  crownPreparation: "Crown Preparation",
  bridgePreparation: "Bridge Preparation",
  finalImpression: "Final Impression",
  tempCementation: "Temp. Cementation",
  cementAccBb: "Cement ACC & BB",
  cementPorcelainCb: "Cement Porcelain C&B",
  metalCrownCb: "Metal Crown C&B",
  porcelainCb: "Porcelain C&B",
  postPreparation: "Post Preparation",
  postCanal: "Post Canal",
  compositeFilling: "Composite Filling",
  amalgamFilling: "Amalgam Filling",
  removableProstho: "Removable Prostho.",
  removableProsthoRepair: "Removable Prostho. Repair",
  cbRemovalPostCore: "C&B Removal / Post & Core",
  orthoAppliances: "Ortho Appliances",
  buckleAppointment: "Buckle Appointment",
  implantUnits: "Implant Units",
  tryIn: "Try-In",
  miscellaneous: "Miscellaneous",
  examination: "Examination",
};

export default function DoctorDashboard() {
  const [doctor, setDoctor] = useState<DoctorUser | null>(null);
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  
  // Patient scheduling form state
  const [isSchedulingOpen, setIsSchedulingOpen] = useState(false);
  const [patientName, setPatientName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [procedure, setProcedure] = useState("");
  const [appointmentDate, setAppointmentDate] = useState(new Date().toISOString().split('T')[0]);
  const [appointmentStartTime, setAppointmentStartTime] = useState("");
  const [appointmentEndTime, setAppointmentEndTime] = useState("");
  const [notes, setNotes] = useState("");
  
  // Appointment edit/delete state
  const [selectedAppointment, setSelectedAppointment] = useState<any>(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [editFormData, setEditFormData] = useState({
    patientName: "",
    patientPhone: "",
    procedure: "",
    appointmentDate: "",
    startTime: "",
    endTime: "",
    notes: "",
  });

  // Quick booking from calendar
  const [showQuickBookDialog, setShowQuickBookDialog] = useState(false);
  const [selectedDate, setSelectedDate] = useState("");
  const [currentWeek, setCurrentWeek] = useState(new Date());

  // Calculate week dates for calendar
  const weekStart = startOfWeek(currentWeek, { weekStartsOn: 0 }); // Sunday
  const weekEnd = endOfWeek(currentWeek, { weekStartsOn: 0 }); // Saturday
  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  // Navigation functions
  const goToPreviousWeek = () => setCurrentWeek(subWeeks(currentWeek, 1));
  const goToNextWeek = () => setCurrentWeek(addWeeks(currentWeek, 1));
  const goToToday = () => setCurrentWeek(new Date());

  useEffect(() => {
    const loadDoctorInfo = async () => {
      // First check localStorage for traditional login
      const storedDoctor = localStorage.getItem("doctorUser");
      if (storedDoctor) {
        setDoctor(JSON.parse(storedDoctor));
        return;
      }
      
      // If no localStorage data, try to get doctor info via API (for OIDC users)
      try {
        const response = await fetch("/api/doctor/current", {
          credentials: "include"
        });
        
        if (response.ok) {
          const doctorData = await response.json();
          setDoctor(doctorData);
          console.log("OIDC user mapped to doctor:", doctorData);
        } else if (response.status === 404) {
          // No doctor profile found, redirect to login
          setLocation("/doctor-login");
        } else {
          console.error("Failed to fetch doctor info:", response.statusText);
          setLocation("/doctor-login");
        }
      } catch (error) {
        console.error("Error fetching doctor info:", error);
        setLocation("/doctor-login");
      }
    };
    
    loadDoctorInfo();
  }, [setLocation]);

  const today = new Date().toISOString().split('T')[0];
  const currentWeekday = new Date().getDay(); // 0 = Sunday, 1 = Monday, etc.

  // Fetch today's appointments
  const { data: todaysAppointments = [], isLoading: appointmentsLoading } = useQuery<Appointment[]>({
    queryKey: [`/api/appointments?doctorId=${doctor?.id}&date=${today}`],
    enabled: !!doctor,
  });

  // Fetch all upcoming appointments for this doctor
  const { data: allAppointments = [], isLoading: allAppointmentsLoading } = useQuery<Appointment[]>({
    queryKey: [`/api/appointments?doctorId=${doctor?.id}`],
    enabled: !!doctor,
  });

  // Fetch weekly appointments for calendar
  const { data: weeklyAppointments = [], isLoading: weeklyAppointmentsLoading } = useQuery<Appointment[]>({
    queryKey: [`/api/appointments?doctorId=${doctor?.id}&startDate=${format(weekStart, 'yyyy-MM-dd')}&endDate=${format(weekEnd, 'yyyy-MM-dd')}`],
    enabled: !!doctor,
  });

  // Group appointments by day for weekly calendar
  const appointmentsByDay = weekDays.reduce((acc, day) => {
    const dayKey = format(day, 'yyyy-MM-dd');
    acc[dayKey] = weeklyAppointments.filter(apt => apt.appointmentDate === dayKey);
    return acc;
  }, {} as Record<string, Appointment[]>);

  // Fetch clinic assignments for this doctor only
  const { data: clinicAssignments = [], isLoading: assignmentsLoading } = useQuery<ClinicAssignment[]>({
    queryKey: [`/api/clinic-assignments?doctorId=${doctor?.id}`],
    enabled: !!doctor,
  });

  // Fetch leaves for this doctor only
  const { data: leaves = [], isLoading: leavesLoading } = useQuery<Leave[]>({
    queryKey: [`/api/leaves?doctorId=${doctor?.id}`],
    enabled: !!doctor,
  });

  // Permission view state
  const [selectedPermissionMonth, setSelectedPermissionMonth] = useState(new Date().getMonth());
  const [selectedPermissionYear, setSelectedPermissionYear] = useState(new Date().getFullYear());

  // Procedure questionnaire state
  const [showProcedureQuestionnaire, setShowProcedureQuestionnaire] = useState(false);
  const [appointmentToComplete, setAppointmentToComplete] = useState<Appointment | null>(null);
  
  // Notification state
  const [notification, setNotification] = useState<any>(null);

  // Clinic-day view state
  const [clinicDayDate, setClinicDayDate] = useState(format(new Date(), "yyyy-MM-dd"));
  const [clinicAddDialog, setClinicAddDialog] = useState<{
    clinic: { id: number; name: string; startTime: string; endTime: string };
    windowStart: number;
    windowEnd: number;
  } | null>(null);
  const [clinicAddForm, setClinicAddForm] = useState({ patientName: "", patientPhone: "", procedure: "", notes: "", startTime: "", endTime: "" });

  // My Stats state
  const [statsStartDate, setStatsStartDate] = useState(format(startOfMonth(new Date()), "yyyy-MM-dd"));
  const [statsEndDate, setStatsEndDate] = useState(format(new Date(), "yyyy-MM-dd"));

  // Fetch permissions for this doctor only for selected month
  const { data: permissions = [], isLoading: permissionsLoading } = useQuery<Permission[]>({
    queryKey: [`/api/permissions?doctorId=${doctor?.id}&month=${selectedPermissionMonth + 1}&year=${selectedPermissionYear}`],
    enabled: !!doctor,
  });

  // Calculate permissions left for the selected month (max 4 per month)
  const maxPermissionsPerMonth = 4;
  const permissionsUsed = permissions.length;
  const permissionsLeft = Math.max(0, maxPermissionsPerMonth - permissionsUsed);

  // Clinic-day query (doctor's clinics on selected date)
  const { data: clinicDayEntries = [], isLoading: clinicDayLoading, refetch: refetchClinicDay } = useQuery<any[]>({
    queryKey: ["/api/doctor/clinic-day", doctor?.id, clinicDayDate],
    queryFn: async () => {
      if (!doctor?.id) return [];
      const res = await fetch(`/api/doctor/${doctor.id}/clinic-day?date=${clinicDayDate}`);
      if (!res.ok) throw new Error("Failed to fetch");
      return res.json();
    },
    enabled: !!doctor,
    refetchInterval: 30000,
  });

  // My Stats query
  const { data: myStats, isLoading: myStatsLoading } = useQuery<any>({
    queryKey: ["/api/doctor/my-stats", doctor?.id, statsStartDate, statsEndDate],
    queryFn: async () => {
      if (!doctor?.id) return null;
      const res = await fetch(`/api/doctor/${doctor.id}/my-stats?startDate=${statsStartDate}&endDate=${statsEndDate}`);
      if (!res.ok) throw new Error("Failed to fetch");
      return res.json();
    },
    enabled: !!doctor,
  });

  // Derived stats computations
  const myTotalProcedures = useMemo(() => {
    if (!myStats) return 0;
    return Object.values(myStats.departmentTotals?.procedureTotals || {}).reduce((s: number, v) => s + (v as number), 0);
  }, [myStats]);

  const mySortedProcedures = useMemo(() => {
    if (!myStats) return [];
    return Object.keys(procedureLabelsDr)
      .map(key => ({ key, label: procedureLabelsDr[key], count: myStats.departmentTotals?.procedureTotals?.[key] || 0 }))
      .sort((a, b) => b.count - a.count);
  }, [myStats]);

  const handleLogout = () => {
    localStorage.removeItem("doctorUser");
    toast({
      title: "Logged out",
      description: "You have been successfully logged out.",
    });
    setLocation("/doctor-login");
  };

  // Patient scheduling mutation
  const schedulePatientMutation = useMutation({
    mutationFn: async (appointmentData: any) => {
      return await apiRequest("/api/appointments", {
        method: "POST",
        body: JSON.stringify(appointmentData),
      });
    },
    onSuccess: () => {
      toast({
        title: "Appointment Scheduled",
        description: "Patient appointment has been successfully scheduled.",
      });
      // Invalidate all appointment queries for this doctor
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}`] });
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}&date=${today}`] });
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}&startDate=${format(weekStart, 'yyyy-MM-dd')}&endDate=${format(weekEnd, 'yyyy-MM-dd')}`] });
      queryClient.invalidateQueries({ queryKey: ['/api/appointments'] });
      setIsSchedulingOpen(false);
      // Reset form
      setPatientName("");
      setPatientPhone("");
      setProcedure("");
      setAppointmentStartTime("");
      setAppointmentEndTime("");
      setNotes("");
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description: error.message || "Failed to schedule appointment",
        variant: "destructive",
      });
    },
  });

  const handleSchedulePatient = () => {
    if (!patientName.trim() || !patientPhone.trim() || !procedure.trim() || !appointmentStartTime || !appointmentEndTime) {
      toast({
        title: "Missing Information",
        description: "Please fill in all required fields including start and end times.",
        variant: "destructive",
      });
      return;
    }

    const appointmentData = {
      doctorId: doctor?.id,
      patientName: patientName.trim(),
      patientPhone: patientPhone.trim(),
      procedure: procedure.trim(),
      appointmentDate,
      startTime: appointmentStartTime,
      endTime: appointmentEndTime,
      notes: notes.trim(),
      status: "scheduled",
      type: "consultation"
    };

    schedulePatientMutation.mutate(appointmentData);
  };

  const updateAppointmentMutation = useMutation({
    mutationFn: async (appointmentData: any) => {
      console.log('Updating appointment with data:', appointmentData);
      console.log('Selected appointment ID:', selectedAppointment?.id);
      
      const updateData = {
        doctorId: doctor?.id,
        patientName: appointmentData.patientName,
        patientPhone: appointmentData.patientPhone,
        reasonForVisit: appointmentData.procedure,
        appointmentDate: appointmentData.appointmentDate,
        startTime: appointmentData.startTime,
        endTime: appointmentData.endTime,
        notes: appointmentData.notes,
        status: 'scheduled',
        type: 'consultation'
      };
      
      console.log('Sending update data:', updateData);
      
      return apiRequest(`/api/appointments/${selectedAppointment.id}`, {
        method: 'PUT',
        body: JSON.stringify(updateData),
      });
    },
    onSuccess: () => {
      toast({
        title: "Appointment Updated",
        description: "The appointment has been successfully updated.",
      });
      setShowEditDialog(false);
      setSelectedAppointment(null);
      // Invalidate all appointment queries for this doctor
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}`] });
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}&date=${today}`] });
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}&startDate=${format(weekStart, 'yyyy-MM-dd')}&endDate=${format(weekEnd, 'yyyy-MM-dd')}`] });
      queryClient.invalidateQueries({ queryKey: ['/api/appointments'] });
      queryClient.invalidateQueries({ queryKey: ["/api/doctor/clinic-day", doctor?.id, clinicDayDate] });
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: "Failed to update appointment. Please try again.",
        variant: "destructive",
      });
      console.error('Update error:', error);
    },
  });

  const deleteAppointmentMutation = useMutation({
    mutationFn: async (appointmentId: number) => {
      return apiRequest(`/api/appointments/${appointmentId}`, {
        method: 'DELETE',
      });
    },
    onSuccess: () => {
      toast({
        title: "Appointment Deleted",
        description: "The appointment has been successfully deleted.",
      });
      setShowDeleteDialog(false);
      setSelectedAppointment(null);
      // Invalidate all appointment queries for this doctor
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}`] });
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}&date=${today}`] });
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}&startDate=${format(weekStart, 'yyyy-MM-dd')}&endDate=${format(weekEnd, 'yyyy-MM-dd')}`] });
      queryClient.invalidateQueries({ queryKey: ['/api/appointments'] });
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: "Failed to delete appointment. Please try again.",
        variant: "destructive",
      });
      console.error('Delete error:', error);
    },
  });

  // Add appointment status update mutation
  const updateAppointmentStatusMutation = useMutation({
    mutationFn: async ({ appointmentId, status }: { appointmentId: number; status: string }) => {
      return apiRequest(`/api/appointments/${appointmentId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });
    },
    onSuccess: (_, { status }) => {
      toast({
        title: "Status Updated",
        description: `Appointment marked as ${status}.`,
      });
      // Invalidate all appointment queries for this doctor
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}`] });
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}&date=${today}`] });
      queryClient.invalidateQueries({ queryKey: [`/api/appointments?doctorId=${doctor?.id}&startDate=${format(weekStart, 'yyyy-MM-dd')}&endDate=${format(weekEnd, 'yyyy-MM-dd')}`] });
      queryClient.invalidateQueries({ queryKey: ['/api/appointments'] });
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: "Failed to update appointment status. Please try again.",
        variant: "destructive",
      });
      console.error('Status update error:', error);
    },
  });

  const handleStatusUpdate = (appointmentId: number, status: string) => {
    // If marking as completed, show procedure questionnaire first
    if (status === 'completed') {
      const appointment = todaysAppointments?.find(apt => apt.id === appointmentId) ||
                         weeklyAppointments?.find(apt => apt.id === appointmentId);
      if (appointment) {
        setAppointmentToComplete(appointment);
        setShowProcedureQuestionnaire(true);
      }
    } else {
      // For other status updates, proceed directly
      updateAppointmentStatusMutation.mutate({ appointmentId, status });
    }
  };

  const handleProcedureQuestionnaireComplete = () => {
    if (appointmentToComplete) {
      // Now update the appointment status to completed
      updateAppointmentStatusMutation.mutate({ 
        appointmentId: appointmentToComplete.id, 
        status: 'completed' 
      });
      setShowProcedureQuestionnaire(false);
      setAppointmentToComplete(null);
    }
  };

  const handleProcedureQuestionnaireCancel = () => {
    setShowProcedureQuestionnaire(false);
    setAppointmentToComplete(null);
  };

  // Clinic-day add appointment mutation
  const clinicAddMutation = useMutation({
    mutationFn: async (data: any) => {
      const res = await apiRequest("/api/appointments", { method: "POST", body: JSON.stringify(data) });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/doctor/clinic-day", doctor?.id, clinicDayDate] });
      setClinicAddDialog(null);
      setClinicAddForm({ patientName: "", patientPhone: "", procedure: "", notes: "", startTime: "", endTime: "" });
      toast({ title: "Patient booked", description: "Appointment added to your clinic slot." });
    },
    onError: () => toast({ title: "Failed to book patient", variant: "destructive" }),
  });

  // Handler to open add-patient dialog from a free timeline slot
  const openClinicAddDialog = (clinic: any, windowStart: number, windowEnd: number) => {
    setClinicAddDialog({ clinic, windowStart, windowEnd });
    setClinicAddForm({
      patientName: "", patientPhone: "", procedure: "", notes: "",
      startTime: minsToHHMMDr(windowStart),
      endTime: minsToHHMMDr(Math.min(windowStart + 30, windowEnd)),
    });
  };

  // Handle status update for clinic-day appointments (supports procedure questionnaire)
  const handleClinicStatusUpdate = (appointment: any, status: string) => {
    if (status === "completed") {
      setAppointmentToComplete({ ...appointment, appointmentDate: clinicDayDate } as any);
      setShowProcedureQuestionnaire(true);
    } else {
      updateAppointmentStatusMutation.mutate({ appointmentId: appointment.id, status });
      setTimeout(() => refetchClinicDay(), 600);
    }
  };

  // WebSocket connection for notifications (only when doctor is loaded)
  const { isConnected } = useWebSocket({
    userId: doctor ? `doctor_${doctor.id}` : '',
    onNotification: (notificationData) => {
      setNotification(notificationData);
      // Refresh appointments when a patient arrives to show updated status
      queryClient.invalidateQueries({ queryKey: ['/api/appointments', { doctorId: doctor?.id }] });
      queryClient.invalidateQueries({ queryKey: ['/api/appointments', { doctorId: doctor?.id, date: today }] });
      queryClient.invalidateQueries({ queryKey: ['/api/appointments', { doctorId: doctor?.id, type: 'weekly' }] });
    }
  });

  const handleDismissNotification = () => {
    setNotification(null);
  };

  if (!doctor) {
    return <div>Loading...</div>;
  }

  const weekdayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-2 sm:px-4 lg:px-8">
          <div className="flex justify-between items-center py-3 sm:py-4">
            <div className="flex items-center space-x-2 sm:space-x-4">
              <div className="p-1.5 sm:p-2 bg-blue-600 rounded-lg">
                <User className="h-4 w-4 sm:h-6 sm:w-6 text-white" />
              </div>
              <div>
                <h1 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-gray-100">
                  Welcome, {doctor.title} {doctor.name}
                </h1>
                <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">
                  Doctor Dashboard
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                onClick={() => {
                  const deptId = doctor?.departmentId;
                  const url = deptId ? `/exam-schedule?dept=${deptId}` : "/exam-schedule";
                  setLocation(url);
                }}
                variant="outline"
                size="sm"
                className="flex items-center space-x-1 sm:space-x-2 px-2 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm border-violet-300 text-violet-600 hover:bg-violet-50"
              >
                <CalendarCheck className="h-3 w-3 sm:h-4 sm:w-4" />
                <span className="hidden sm:inline">Exam Schedule</span>
              </Button>
              <Button
                onClick={() => setLocation("/overtime")}
                variant="outline"
                size="sm"
                className="flex items-center space-x-1 sm:space-x-2 px-2 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm border-orange-300 text-orange-600 hover:bg-orange-50"
              >
                <Clock className="h-3 w-3 sm:h-4 sm:w-4" />
                <span className="hidden sm:inline">Overtime</span>
              </Button>
              <Button
                onClick={handleLogout}
                variant="outline"
                size="sm"
                className="flex items-center space-x-1 sm:space-x-2 px-2 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm"
                data-testid="button-logout"
              >
                <LogOut className="h-3 w-3 sm:h-4 sm:w-4" />
                <span className="hidden sm:inline">Logout</span>
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-2 sm:px-4 lg:px-8 py-3 sm:py-6">
        <Tabs defaultValue="today" className="space-y-4 sm:space-y-6">
          <TabsList className="grid w-full grid-cols-4 sm:grid-cols-7 gap-1 sm:gap-0 p-1">
            <TabsTrigger value="today" className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm px-1 sm:px-3">
              <Calendar className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Today</span>
              <span className="sm:hidden">📅</span>
            </TabsTrigger>
            <TabsTrigger value="calendar" className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm px-1 sm:px-3">
              <Building2 className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Clinic Day</span>
              <span className="sm:hidden">🏥</span>
            </TabsTrigger>
            <TabsTrigger value="schedule" className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm px-1 sm:px-3">
              <Clock className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">My Schedule</span>
              <span className="sm:hidden">⏰</span>
            </TabsTrigger>
            <TabsTrigger value="book" className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm px-1 sm:px-3">
              <Plus className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Book Patient</span>
              <span className="sm:hidden">➕</span>
            </TabsTrigger>
            <TabsTrigger value="leaves" className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm px-1 sm:px-3">
              <AlertCircle className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Leaves</span>
              <span className="sm:hidden">🚫</span>
            </TabsTrigger>
            <TabsTrigger value="permissions" className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm px-1 sm:px-3">
              <Clock className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">Permissions</span>
              <span className="sm:hidden">🔐</span>
            </TabsTrigger>
            <TabsTrigger value="my-stats" className="flex items-center space-x-1 sm:space-x-2 text-xs sm:text-sm px-1 sm:px-3">
              <BarChart3 className="h-3 w-3 sm:h-4 sm:w-4" />
              <span className="hidden sm:inline">My Stats</span>
              <span className="sm:hidden">📊</span>
            </TabsTrigger>
          </TabsList>

          {/* Today's Appointments */}
          <TabsContent value="today">
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <Calendar className="h-5 w-5" />
                    <span>Today's Appointments - {format(new Date(), 'EEEE, MMMM d, yyyy')}</span>
                  </CardTitle>
                  <CardDescription>
                    Your scheduled appointments for today
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {appointmentsLoading ? (
                    <div>Loading appointments...</div>
                  ) : todaysAppointments.length === 0 ? (
                    <p className="text-gray-600 dark:text-gray-400">No appointments scheduled for today.</p>
                  ) : (
                    <div className="space-y-4">
                      {todaysAppointments
                        .sort((a, b) => {
                          // Sort by start time chronologically
                          const timeA = a.startTime || '00:00';
                          const timeB = b.startTime || '00:00';
                          return timeA.localeCompare(timeB);
                        })
                        .map((appointment: Appointment) => (
                        <div
                          key={appointment.id}
                          className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg"
                          data-testid={`appointment-${appointment.id}`}
                        >
                          <div className="flex-1">
                            <div className="flex items-center space-x-3">
                              <div>
                                <h3 className="font-medium text-gray-900 dark:text-gray-100">
                                  {appointment.patient ? 
                                    `${appointment.patient.firstName} ${appointment.patient.lastName}` :
                                    'Unknown Patient'
                                  }
                                </h3>
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                  {appointment.startTime && appointment.endTime 
                                    ? `${appointment.startTime} - ${appointment.endTime}` 
                                    : 'Time not set'}
                                </p>
                                {appointment.patient?.phone && (
                                  <p className="text-sm text-gray-600 dark:text-gray-400">
                                    Phone: {appointment.patient.phone}
                                  </p>
                                )}
                              </div>
                            </div>
                            {appointment.reasonForVisit && (
                              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                                Procedure: {appointment.reasonForVisit}
                              </p>
                            )}
                            {appointment.notes && (
                              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                                Notes: {appointment.notes}
                              </p>
                            )}
                            {appointment.clinic && (
                              <p className="text-sm text-gray-600 dark:text-gray-400">
                                Clinic: {appointment.clinic.name}
                              </p>
                            )}
                          </div>
                          <div className="flex flex-col items-end space-y-2">
                            <div className="flex items-center space-x-2">
                              <Badge variant={
                                appointment.status === 'completed' ? 'default' : 
                                appointment.status === 'cancelled' ? 'destructive' : 
                                appointment.status === 'missed' ? 'destructive' : 'secondary'
                              }>
                                {appointment.status}
                              </Badge>
                              <Badge variant="outline">
                                {appointment.type}
                              </Badge>
                            </div>
                            {(appointment.status === 'scheduled' || appointment.status === 'arrived') && (
                              <div className="flex space-x-1">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 px-2 text-xs bg-green-50 hover:bg-green-100 text-green-700 border-green-200"
                                  onClick={() => handleStatusUpdate(appointment.id, 'completed')}
                                  disabled={updateAppointmentStatusMutation.isPending}
                                  data-testid={`button-complete-${appointment.id}`}
                                >
                                  ✓ Complete
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 px-2 text-xs bg-yellow-50 hover:bg-yellow-100 text-yellow-700 border-yellow-200"
                                  onClick={() => handleStatusUpdate(appointment.id, 'missed')}
                                  disabled={updateAppointmentStatusMutation.isPending}
                                  data-testid={`button-missed-${appointment.id}`}
                                >
                                  ✗ Missed
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 px-2 text-xs bg-red-50 hover:bg-red-100 text-red-700 border-red-200"
                                  onClick={() => handleStatusUpdate(appointment.id, 'cancelled')}
                                  disabled={updateAppointmentStatusMutation.isPending}
                                  data-testid={`button-cancel-${appointment.id}`}
                                >
                                  ✗ Cancel
                                </Button>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
            
            {/* Upcoming Appointments Summary - Only in Today tab */}
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <FileText className="h-5 w-5" />
                  <span>Upcoming Appointments</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {allAppointmentsLoading ? (
                  <div className="text-center py-4">
                    <p className="text-gray-600 dark:text-gray-400">Loading appointments...</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {allAppointments.length === 0 ? (
                      <p className="text-gray-600 dark:text-gray-400">No upcoming appointments scheduled.</p>
                    ) : (
                      allAppointments
                        .filter(apt => new Date(apt.appointmentDate) >= new Date())
                        .sort((a, b) => {
                          const dateCompare = new Date(a.appointmentDate).getTime() - new Date(b.appointmentDate).getTime();
                          if (dateCompare !== 0) return dateCompare;
                          const timeA = a.startTime || '00:00';
                          const timeB = b.startTime || '00:00';
                          return timeA.localeCompare(timeB);
                        })
                        .slice(0, 5)
                        .map((appointment) => (
                        <div
                          key={appointment.id}
                          className="flex items-center justify-between p-3 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800"
                        >
                          <div className="flex-1">
                            <div className="flex items-center space-x-3">
                              <div>
                                <h4 className="font-medium text-gray-900 dark:text-gray-100">
                                  {appointment.patient?.firstName} {appointment.patient?.lastName}
                                </h4>
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                  {format(parseISO(appointment.appointmentDate), 'MMM d, yyyy')} at {appointment.startTime}
                                </p>
                                {appointment.reasonForVisit && (
                                  <p className="text-sm text-gray-600 dark:text-gray-400">
                                    Procedure: {appointment.reasonForVisit}
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Badge variant={appointment.status === 'confirmed' || appointment.status === 'scheduled' ? 'default' : 'secondary'}>
                              {appointment.status}
                            </Badge>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Calendar View */}
          <TabsContent value="calendar">
            <div className="space-y-4">
              {/* Date Navigation */}
              <Card>
                <CardHeader className="py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Building2 className="h-5 w-5 text-blue-600" />
                      <div>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">My Clinic Day</span>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Your assigned clinics for the selected day</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-wrap">
                      <Button size="sm" variant="outline"
                        onClick={() => setClinicDayDate(format(subDays(new Date(clinicDayDate + "T12:00"), 1), "yyyy-MM-dd"))}>
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <input
                        type="date"
                        value={clinicDayDate}
                        onChange={e => setClinicDayDate(e.target.value)}
                        className="border border-gray-300 dark:border-gray-600 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                      />
                      {isToday(new Date(clinicDayDate + "T12:00")) && (
                        <Badge className="bg-blue-100 text-blue-800 text-xs">Today</Badge>
                      )}
                      <Button size="sm" variant="outline"
                        onClick={() => setClinicDayDate(format(addDays(new Date(clinicDayDate + "T12:00"), 1), "yyyy-MM-dd"))}>
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                      {!isToday(new Date(clinicDayDate + "T12:00")) && (
                        <Button size="sm" variant="outline"
                          onClick={() => setClinicDayDate(format(new Date(), "yyyy-MM-dd"))}>
                          Today
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => refetchClinicDay()}>
                        <RefreshCw className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
              </Card>

              {/* Clinic Cards */}
              {clinicDayLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {[1, 2].map(i => (
                    <div key={i} className="h-64 bg-white dark:bg-gray-800 rounded-xl border border-blue-100 animate-pulse" />
                  ))}
                </div>
              ) : clinicDayEntries.length === 0 ? (
                <Card>
                  <CardContent className="py-16 text-center text-gray-500">
                    <Building2 className="w-12 h-12 mx-auto mb-3 text-blue-200" />
                    <p className="text-lg font-semibold text-gray-700 dark:text-gray-300">
                      No clinics scheduled for {format(new Date(clinicDayDate + "T12:00"), "EEEE, MMM d")}
                    </p>
                    <p className="text-sm text-gray-400 mt-1">You have no clinic assignments on this day.</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {clinicDayEntries.map((ce: any) => {
                    const timeline = buildTimelineDr(ce.clinic.startTime, ce.clinic.endTime, ce.appointments || []);
                    const clinicDurMin = parseTimeDr(ce.clinic.endTime) - parseTimeDr(ce.clinic.startTime);
                    const bookedMin = timeline.filter(b => b.kind === "booked").reduce((s: number, b: any) => s + b.endMin - b.startMin, 0);
                    const freeMin = timeline.filter(b => b.kind === "free").reduce((s: number, b: any) => s + b.endMin - b.startMin, 0);
                    const fillPct = clinicDurMin > 0 ? Math.round((bookedMin / clinicDurMin) * 100) : 0;

                    return (
                      <Card key={ce.assignmentId} className={`border shadow-sm flex flex-col ${ce.isOnLeave ? "border-amber-200 opacity-80" : "border-blue-100"}`}>
                        <CardHeader className={`px-4 py-3 rounded-t-xl ${ce.isOnLeave ? "bg-amber-50" : "bg-gradient-to-r from-blue-600 to-indigo-600"}`}>
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <h3 className={`font-bold text-base leading-tight ${ce.isOnLeave ? "text-amber-900" : "text-white"}`}>
                                {ce.clinic.name}
                              </h3>
                              <div className={`flex items-center gap-1.5 mt-0.5 text-xs ${ce.isOnLeave ? "text-amber-700" : "text-blue-100"}`}>
                                <Clock className="w-3 h-3" />
                                {formatTime12Dr(ce.clinic.startTime)} – {formatTime12Dr(ce.clinic.endTime)}
                              </div>
                            </div>
                            {ce.isOnLeave ? (
                              <Badge className="bg-amber-400 text-amber-900 text-xs shrink-0">On Leave</Badge>
                            ) : (
                              <div className="text-right shrink-0">
                                <p className="text-white font-bold text-sm">{fillPct}%</p>
                                <p className="text-blue-200 text-[10px]">full</p>
                              </div>
                            )}
                          </div>
                          {!ce.isOnLeave && (
                            <>
                              <div className="mt-2 h-1.5 bg-blue-800/40 rounded-full overflow-hidden">
                                <div className="h-full bg-white/70 rounded-full transition-all" style={{ width: `${fillPct}%` }} />
                              </div>
                              <div className="mt-1 text-[10px] text-blue-200">
                                {durationLabelDr(freeMin)} free · {durationLabelDr(bookedMin)} booked
                              </div>
                            </>
                          )}
                        </CardHeader>

                        <CardContent className="p-2 flex-1">
                          <div className="space-y-1">
                            {timeline.length === 0 ? (
                              <p className="text-xs text-gray-400 text-center py-4">No data for this clinic</p>
                            ) : (
                              timeline.map((block: any, idx: number) => {
                                const durMin = block.endMin - block.startMin;

                                if (block.kind === "free") {
                                  return (
                                    <div
                                      key={idx}
                                      onClick={() => !ce.isOnLeave && openClinicAddDialog(ce.clinic, block.startMin, block.endMin)}
                                      className={`flex items-stretch rounded-lg border text-xs overflow-hidden transition-all ${
                                        !ce.isOnLeave
                                          ? "border-green-200 bg-green-50 hover:bg-green-100 hover:border-green-300 cursor-pointer group"
                                          : "border-gray-100 bg-gray-50"
                                      }`}
                                    >
                                      <div className="w-1 bg-green-400 shrink-0" />
                                      <div className="px-2 py-2 flex items-center gap-2 flex-1">
                                        <div className="font-mono text-[10px] text-green-700 font-semibold min-w-[80px]">
                                          {formatTime12Dr(minsToHHMMDr(block.startMin))} – {formatTime12Dr(minsToHHMMDr(block.endMin))}
                                        </div>
                                        <div className="text-green-600 text-[10px] flex-1">{durationLabelDr(durMin)} free</div>
                                        {!ce.isOnLeave && (
                                          <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                                            <Plus className="w-3 h-3 text-green-600" />
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  );
                                } else {
                                  const appt = block.appointment;
                                  const isActive = appt.status === "scheduled" || appt.status === "arrived";
                                  const statusColor =
                                    appt.status === "completed" ? "bg-blue-50 border-blue-200" :
                                    appt.status === "cancelled" ? "bg-red-50 border-red-200 opacity-60" :
                                    appt.status === "missed" ? "bg-yellow-50 border-yellow-200 opacity-70" :
                                    "bg-indigo-50 border-indigo-200";

                                  return (
                                    <div key={idx} className={`flex items-stretch rounded-lg border text-xs overflow-hidden ${statusColor}`}>
                                      <div className={`w-1 shrink-0 ${
                                        appt.status === "completed" ? "bg-blue-500" :
                                        appt.status === "cancelled" ? "bg-red-400" :
                                        appt.status === "missed" ? "bg-yellow-400" : "bg-indigo-500"
                                      }`} />
                                      <div className="px-2 py-2 flex items-start gap-2 flex-1 min-w-0">
                                        <div className="font-mono text-[10px] font-semibold min-w-[80px] text-gray-600 shrink-0">
                                          {formatTime12Dr(appt.startTime)}<br />
                                          <span className="text-gray-400">{durationLabelDr(durMin)}</span>
                                        </div>
                                        <div className="flex-1 min-w-0">
                                          <div className="font-medium text-gray-800 dark:text-gray-200 truncate">
                                            {appt.patient?.firstName} {appt.patient?.lastName}
                                          </div>
                                          {appt.reasonForVisit && (
                                            <div className="text-[10px] text-gray-500 truncate">{appt.reasonForVisit}</div>
                                          )}
                                          <Badge
                                            variant={appt.status === "completed" ? "default" : appt.status === "cancelled" || appt.status === "missed" ? "destructive" : "secondary"}
                                            className="text-[9px] px-1 py-0 mt-0.5"
                                          >
                                            {appt.status}
                                          </Badge>
                                        </div>
                                        <div className="flex flex-col gap-0.5 shrink-0">
                                          <Button size="sm" variant="outline"
                                            className="h-5 px-1.5 text-[10px] bg-gray-50 hover:bg-gray-100 text-gray-600 border-gray-200"
                                            onClick={e => {
                                              e.stopPropagation();
                                              setSelectedAppointment({ ...appt, appointmentDate: clinicDayDate });
                                              setEditFormData({
                                                patientName: `${appt.patient?.firstName || ""} ${appt.patient?.lastName || ""}`.trim(),
                                                patientPhone: appt.patient?.phone || "",
                                                procedure: appt.reasonForVisit || "",
                                                appointmentDate: clinicDayDate,
                                                startTime: appt.startTime || "",
                                                endTime: appt.endTime || "",
                                                notes: appt.notes || "",
                                              });
                                              setShowEditDialog(true);
                                            }}>
                                            <Pencil className="h-2.5 w-2.5" />
                                          </Button>
                                          {isActive && (
                                            <>
                                              <Button size="sm" variant="outline"
                                                className="h-5 px-1.5 text-[10px] bg-green-50 hover:bg-green-100 text-green-700 border-green-200"
                                                disabled={updateAppointmentStatusMutation.isPending}
                                                onClick={e => { e.stopPropagation(); handleClinicStatusUpdate(appt, "completed"); }}>
                                                ✓
                                              </Button>
                                              <Button size="sm" variant="outline"
                                                className="h-5 px-1.5 text-[10px] bg-yellow-50 hover:bg-yellow-100 text-yellow-700 border-yellow-200"
                                                disabled={updateAppointmentStatusMutation.isPending}
                                                onClick={e => { e.stopPropagation(); handleClinicStatusUpdate(appt, "missed"); }}>
                                                ✗
                                              </Button>
                                              <Button size="sm" variant="outline"
                                                className="h-5 px-1.5 text-[10px] bg-red-50 hover:bg-red-100 text-red-700 border-red-200"
                                                disabled={updateAppointmentStatusMutation.isPending}
                                                onClick={e => { e.stopPropagation(); handleClinicStatusUpdate(appt, "cancelled"); }}>
                                                C
                                              </Button>
                                            </>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                }
                              })
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          </TabsContent>

          {/* My Schedule Tab */}
          <TabsContent value="schedule">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Clock className="h-5 w-5" />
                  <span>My Weekly Clinic Schedule</span>
                </CardTitle>
                <CardDescription>
                  Your assigned clinic schedules and examination slots
                </CardDescription>
              </CardHeader>
              <CardContent>
                {assignmentsLoading ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-2 text-gray-600 dark:text-gray-400">Loading your clinic schedule...</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Clinic Assignments */}
                    <div>
                      <h3 className="text-lg font-semibold mb-4">Clinic Assignments</h3>
                      {clinicAssignments.length === 0 ? (
                        <div className="text-center py-8">
                          <CalendarDays className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                          <p className="text-gray-600 dark:text-gray-400">No clinic assignments found.</p>
                          <p className="text-sm text-gray-500 dark:text-gray-500 mt-1">
                            Contact your department head to assign you to clinics.
                          </p>
                        </div>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {clinicAssignments.map((assignment) => (
                            <div
                              key={assignment.id}
                              className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 hover:shadow-md transition-shadow"
                            >
                              <div className="flex items-center space-x-3">
                                <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                                  <CalendarDays className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                                </div>
                                <div className="flex-1">
                                  <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                                    {assignment.clinic?.name || 'Unknown Clinic'}
                                  </h4>
                                  <p className="text-sm text-gray-600 dark:text-gray-400">
                                    Every {weekdayNames[assignment.weekday]}
                                  </p>
                                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                                    {assignment.clinic?.startTime} - {assignment.clinic?.endTime}
                                  </p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Leaves Tab */}
          <TabsContent value="leaves">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <AlertCircle className="h-5 w-5" />
                  <span>My Leaves</span>
                </CardTitle>
                <CardDescription>
                  Your approved and pending leave requests
                </CardDescription>
              </CardHeader>
              <CardContent>
                {leavesLoading ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-2 text-gray-600 dark:text-gray-400">Loading your leaves...</p>
                  </div>
                ) : leaves.length === 0 ? (
                  <div className="text-center py-8">
                    <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-600 dark:text-gray-400">No leaves found.</p>
                    <p className="text-sm text-gray-500 dark:text-gray-500 mt-1">
                      You haven't taken any leaves yet.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {leaves.map((leave) => (
                      <div
                        key={leave.id}
                        className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1">
                            <div className="flex items-center space-x-3">
                              <div className="p-2 bg-red-100 dark:bg-red-900 rounded-lg">
                                <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
                              </div>
                              <div>
                                <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                                  {leave.type} Leave
                                </h4>
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                  {format(parseISO(leave.startDate), 'MMM d, yyyy')} - {format(parseISO(leave.endDate), 'MMM d, yyyy')}
                                </p>
                                {leave.reason && (
                                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                                    Reason: {leave.reason}
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>
                          <Badge variant="outline">
                            {leave.type}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Permissions Tab */}
          <TabsContent value="permissions">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Clock className="h-5 w-5" />
                    <span>My Permissions</span>
                  </div>
                  <div className="flex items-center space-x-4">
                    {/* Month/Year Selector */}
                    <div className="flex items-center space-x-2">
                      <Select 
                        value={selectedPermissionMonth.toString()} 
                        onValueChange={(value) => setSelectedPermissionMonth(parseInt(value))}
                      >
                        <SelectTrigger className="w-32">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 12 }, (_, i) => (
                            <SelectItem key={i} value={i.toString()}>
                              {format(new Date(2024, i, 1), 'MMMM')}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Select 
                        value={selectedPermissionYear.toString()} 
                        onValueChange={(value) => setSelectedPermissionYear(parseInt(value))}
                      >
                        <SelectTrigger className="w-20">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 5 }, (_, i) => {
                            const year = new Date().getFullYear() - 2 + i;
                            return (
                              <SelectItem key={year} value={year.toString()}>
                                {year}
                              </SelectItem>
                            );
                          })}
                        </SelectContent>
                      </Select>
                    </div>
                    {/* Permissions Counter */}
                    <div className="text-right">
                      <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Permissions Used: {permissionsUsed}/{maxPermissionsPerMonth}
                      </div>
                      <div className={`text-xs ${permissionsLeft > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                        {permissionsLeft > 0 ? `${permissionsLeft} remaining` : 'Limit reached'}
                      </div>
                    </div>
                  </div>
                </CardTitle>
                <CardDescription>
                  Monthly permission requests (4 permissions allowed per month)
                </CardDescription>
              </CardHeader>
              <CardContent>
                {permissionsLoading ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-2 text-gray-600 dark:text-gray-400">Loading permissions...</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Monthly Stats Card */}
                    <div className="p-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-semibold text-blue-900 dark:text-blue-100">
                            {format(new Date(selectedPermissionYear, selectedPermissionMonth), 'MMMM yyyy')} Summary
                          </h3>
                          <p className="text-sm text-blue-700 dark:text-blue-300">
                            Hospital policy allows 4 permissions per month
                          </p>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-blue-900 dark:text-blue-100">
                            {permissionsUsed}/4
                          </div>
                          <div className="text-sm text-blue-700 dark:text-blue-300">
                            Used
                          </div>
                        </div>
                      </div>
                      <div className="mt-3">
                        <div className="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-2">
                          <div 
                            className={`h-2 rounded-full transition-all duration-300 ${
                              permissionsUsed >= maxPermissionsPerMonth 
                                ? 'bg-red-500' 
                                : permissionsUsed >= 3 
                                  ? 'bg-yellow-500' 
                                  : 'bg-green-500'
                            }`}
                            style={{ width: `${Math.min((permissionsUsed / maxPermissionsPerMonth) * 100, 100)}%` }}
                          ></div>
                        </div>
                        <div className="flex justify-between text-xs text-blue-600 dark:text-blue-400 mt-1">
                          <span>0</span>
                          <span>{maxPermissionsPerMonth}</span>
                        </div>
                      </div>
                    </div>

                    {/* Permissions List */}
                    {permissions.length === 0 ? (
                      <div className="text-center py-8">
                        <Clock className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                        <p className="text-gray-600 dark:text-gray-400">
                          No permissions for {format(new Date(selectedPermissionYear, selectedPermissionMonth), 'MMMM yyyy')}
                        </p>
                        <p className="text-sm text-gray-500 dark:text-gray-500 mt-1">
                          You have {permissionsLeft} permissions remaining this month
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <h4 className="font-medium text-gray-900 dark:text-gray-100">
                          Permission Details
                        </h4>
                        {permissions
                          .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
                          .map((permission, index) => (
                          <div
                            key={permission.id}
                            className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 hover:shadow-md transition-shadow"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex-1">
                                <div className="flex items-center space-x-3">
                                  <div className="p-2 bg-yellow-100 dark:bg-yellow-900 rounded-lg">
                                    <Clock className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                                  </div>
                                  <div className="flex-1">
                                    <div className="flex items-center space-x-2">
                                      <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                                        {permission.type} Permission
                                      </h4>
                                      <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 px-2 py-1 rounded">
                                        #{index + 1}
                                      </span>
                                    </div>
                                    <p className="text-sm text-gray-600 dark:text-gray-400">
                                      {format(parseISO(permission.date), 'EEEE, MMM d, yyyy')} • {permission.startTime} - {permission.endTime}
                                    </p>
                                    {permission.reason && (
                                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                                        Reason: {permission.reason}
                                      </p>
                                    )}
                                  </div>
                                </div>
                              </div>
                              <Badge variant="outline">
                                {permission.type}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Book Patient Tab */}
          <TabsContent value="book">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Plus className="h-5 w-5" />
                  <span>Schedule New Patient</span>
                </CardTitle>
                <CardDescription>
                  Book appointments for patients in your clinic
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="patientName">Patient Name *</Label>
                    <Input
                      id="patientName"
                      placeholder="Enter patient's full name"
                      value={patientName}
                      onChange={(e) => setPatientName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="patientPhone">Phone Number *</Label>
                    <Input
                      id="patientPhone"
                      placeholder="Enter phone number"
                      value={patientPhone}
                      onChange={(e) => setPatientPhone(e.target.value)}
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="procedure">Procedure/Treatment *</Label>
                  <Input
                    id="procedure"
                    placeholder="Enter procedure or treatment"
                    value={procedure}
                    onChange={(e) => setProcedure(e.target.value)}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="appointmentDate">Date *</Label>
                    <Input
                      id="appointmentDate"
                      type="date"
                      value={appointmentDate}
                      onChange={(e) => setAppointmentDate(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="appointmentStartTime">Start Time *</Label>
                    <Select value={appointmentStartTime} onValueChange={setAppointmentStartTime}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select start time" />
                      </SelectTrigger>
                      <SelectContent>
                        {Array.from({ length: 48 }, (_, i) => {
                          const hour = Math.floor(i / 2);
                          const minute = (i % 2) * 30;
                          const time = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
                          return (
                            <SelectItem key={time} value={time}>
                              {time}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="appointmentEndTime">End Time *</Label>
                    <Select value={appointmentEndTime} onValueChange={setAppointmentEndTime}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select end time" />
                      </SelectTrigger>
                      <SelectContent>
                        {Array.from({ length: 48 }, (_, i) => {
                          const hour = Math.floor(i / 2);
                          const minute = (i % 2) * 30;
                          const time = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
                          return (
                            <SelectItem key={time} value={time}>
                              {time}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="notes">Notes (Optional)</Label>
                  <Textarea
                    id="notes"
                    placeholder="Additional notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>

                <Button
                  onClick={handleSchedulePatient}
                  disabled={schedulePatientMutation.isPending}
                  className="w-full"
                >
                  {schedulePatientMutation.isPending ? "Booking..." : "Book Appointment"}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* My Stats Tab */}
          <TabsContent value="my-stats">
            <div className="space-y-6">
              {/* Date range controls */}
              <Card>
                <CardHeader className="py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <BarChart3 className="h-5 w-5 text-blue-600" />
                      <div>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">My Procedure Statistics</span>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Your completed appointment stats for the selected period</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="flex gap-1">
                        {[
                          { label: "This Month", action: () => { setStatsStartDate(format(startOfMonth(new Date()), "yyyy-MM-dd")); setStatsEndDate(format(new Date(), "yyyy-MM-dd")); } },
                          { label: "Last Month", action: () => { const m = subMonths(new Date(), 1); setStatsStartDate(format(startOfMonth(m), "yyyy-MM-dd")); setStatsEndDate(format(endOfMonth(m), "yyyy-MM-dd")); } },
                          { label: "3 Months", action: () => { setStatsStartDate(format(startOfMonth(subMonths(new Date(), 2)), "yyyy-MM-dd")); setStatsEndDate(format(new Date(), "yyyy-MM-dd")); } },
                        ].map(btn => (
                          <Button key={btn.label} size="sm" variant="outline" className="text-xs h-7 px-2" onClick={btn.action}>
                            {btn.label}
                          </Button>
                        ))}
                      </div>
                      <div className="flex items-center gap-1 text-xs text-gray-500">
                        <input type="date" value={statsStartDate} onChange={e => setStatsStartDate(e.target.value)}
                          className="border border-gray-300 dark:border-gray-600 rounded-md px-2 py-1 text-xs bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
                        <span>–</span>
                        <input type="date" value={statsEndDate} onChange={e => setStatsEndDate(e.target.value)}
                          className="border border-gray-300 dark:border-gray-600 rounded-md px-2 py-1 text-xs bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
                      </div>
                    </div>
                  </div>
                </CardHeader>
              </Card>

              {myStatsLoading ? (
                <div className="flex items-center justify-center py-16">
                  <div className="text-center">
                    <BarChart3 className="h-10 w-10 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-500">Loading your statistics...</p>
                  </div>
                </div>
              ) : !myStats ? (
                <Card>
                  <CardContent className="py-12 text-center text-gray-500">
                    <BarChart3 className="w-12 h-12 mx-auto mb-3 text-gray-200" />
                    <p>No data available for the selected period.</p>
                  </CardContent>
                </Card>
              ) : (
                <>
                  {/* Summary Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <Card className="border-blue-100">
                      <CardContent className="pt-5 pb-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2.5 bg-blue-100 rounded-lg">
                            <Users className="h-5 w-5 text-blue-600" />
                          </div>
                          <div>
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">{myStats.departmentTotals?.treatedPatients ?? 0}</p>
                            <p className="text-xs text-gray-500">Patients Treated</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    <Card className="border-green-100">
                      <CardContent className="pt-5 pb-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2.5 bg-green-100 rounded-lg">
                            <CheckCircle2 className="h-5 w-5 text-green-600" />
                          </div>
                          <div>
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">{myStats.departmentTotals?.completedAppointments ?? 0}</p>
                            <p className="text-xs text-gray-500">Completed Appointments</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    <Card className="border-purple-100">
                      <CardContent className="pt-5 pb-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2.5 bg-purple-100 rounded-lg">
                            <Stethoscope className="h-5 w-5 text-purple-600" />
                          </div>
                          <div>
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">{myTotalProcedures}</p>
                            <p className="text-xs text-gray-500">Total Procedures Logged</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Top Procedures */}
                  {mySortedProcedures.filter(p => p.count > 0).length > 0 && (
                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center gap-2">
                          <TrendingUp className="h-4 w-4 text-blue-600" />
                          Top Procedures
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-3">
                          {mySortedProcedures.filter(p => p.count > 0).slice(0, 10).map((proc, i) => {
                            const maxCount = mySortedProcedures[0]?.count || 1;
                            const barWidth = Math.max(2, (proc.count / maxCount) * 100);
                            return (
                              <div key={proc.key} className="flex items-center gap-3">
                                <span className="text-xs text-gray-400 w-5 text-right shrink-0">{i + 1}</span>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center justify-between mb-1">
                                    <span className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{proc.label}</span>
                                    <span className="text-sm font-bold text-blue-600 ml-2 shrink-0">{proc.count}</span>
                                  </div>
                                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                    <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${barWidth}%` }} />
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Daily Breakdown */}
                  {myStats.dailyBreakdown?.length > 0 && (
                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center gap-2">
                          <CalendarDays className="h-4 w-4 text-indigo-600" />
                          Daily Activity
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-1.5 max-h-64 overflow-y-auto">
                          {[...myStats.dailyBreakdown]
                            .sort((a: any, b: any) => b.date.localeCompare(a.date))
                            .map((day: any) => (
                              <div key={day.date} className="flex items-center justify-between text-sm py-1.5 border-b border-gray-50 dark:border-gray-800 last:border-0">
                                <span className="text-gray-600 dark:text-gray-400">
                                  {format(new Date(day.date + "T12:00"), "EEE, MMM d")}
                                </span>
                                <div className="flex items-center gap-4">
                                  <span className="text-blue-600 font-medium">{day.treatedPatients} pts</span>
                                  <span className="text-gray-500 text-xs">{day.totalProcedures} procedures</span>
                                </div>
                              </div>
                            ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Full Procedure Breakdown */}
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <FileText className="h-4 w-4 text-gray-600" />
                        Full Procedure Breakdown
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-gray-200 dark:border-gray-700">
                              <th className="text-left py-2 text-gray-600 dark:text-gray-400 font-medium">Procedure</th>
                              <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Count</th>
                            </tr>
                          </thead>
                          <tbody>
                            {mySortedProcedures.map(proc => (
                              <tr key={proc.key} className={`border-b border-gray-50 dark:border-gray-800 ${proc.count === 0 ? "opacity-40" : ""}`}>
                                <td className="py-1.5 text-gray-800 dark:text-gray-200">{proc.label}</td>
                                <td className="py-1.5 text-right font-semibold text-gray-900 dark:text-white">{proc.count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                </>
              )}
            </div>
          </TabsContent>

        </Tabs>

        {/* Procedure Questionnaire Modal */}
        {showProcedureQuestionnaire && appointmentToComplete && doctor && (
          <ProcedureQuestionnaire
            appointmentId={appointmentToComplete.id}
            doctorId={doctor.id}
            departmentId={doctor.departmentId}
            appointmentDate={appointmentToComplete.appointmentDate}
            onComplete={handleProcedureQuestionnaireComplete}
            onCancel={handleProcedureQuestionnaireCancel}
          />
        )}

        {/* Edit Appointment Dialog */}
        <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>Edit Appointment</DialogTitle>
              <DialogDescription>
                Update the appointment details below.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-patient-name" className="text-right">
                  Patient Name
                </Label>
                <Input
                  id="edit-patient-name"
                  value={editFormData.patientName}
                  onChange={(e) => setEditFormData({...editFormData, patientName: e.target.value})}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-patient-phone" className="text-right">
                  Phone
                </Label>
                <Input
                  id="edit-patient-phone"
                  value={editFormData.patientPhone}
                  onChange={(e) => setEditFormData({...editFormData, patientPhone: e.target.value})}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-procedure" className="text-right">
                  Procedure
                </Label>
                <Input
                  id="edit-procedure"
                  value={editFormData.procedure}
                  onChange={(e) => setEditFormData({...editFormData, procedure: e.target.value})}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-date" className="text-right">
                  Date
                </Label>
                <Input
                  id="edit-date"
                  type="date"
                  value={editFormData.appointmentDate}
                  onChange={(e) => setEditFormData({...editFormData, appointmentDate: e.target.value})}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-start-time" className="text-right">
                  Start Time
                </Label>
                <Select value={editFormData.startTime} onValueChange={(value) => setEditFormData({...editFormData, startTime: value})}>
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Select start time" />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 48 }, (_, i) => {
                      const hour = Math.floor(i / 2);
                      const minute = (i % 2) * 30;
                      const time = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
                      return (
                        <SelectItem key={time} value={time}>
                          {time}
                        </SelectItem>
                      );
                    })}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-end-time" className="text-right">
                  End Time
                </Label>
                <Select value={editFormData.endTime} onValueChange={(value) => setEditFormData({...editFormData, endTime: value})}>
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Select end time" />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 48 }, (_, i) => {
                      const hour = Math.floor(i / 2);
                      const minute = (i % 2) * 30;
                      const time = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
                      return (
                        <SelectItem key={time} value={time}>
                          {time}
                        </SelectItem>
                      );
                    })}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-notes" className="text-right">
                  Notes
                </Label>
                <Textarea
                  id="edit-notes"
                  value={editFormData.notes}
                  onChange={(e) => setEditFormData({...editFormData, notes: e.target.value})}
                  className="col-span-3"
                  placeholder="Additional notes"
                />
              </div>
            </div>
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setShowEditDialog(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  updateAppointmentMutation.mutate({
                    patientName: editFormData.patientName,
                    patientPhone: editFormData.patientPhone,
                    procedure: editFormData.procedure,
                    appointmentDate: editFormData.appointmentDate,
                    startTime: editFormData.startTime,
                    endTime: editFormData.endTime,
                    notes: editFormData.notes,
                  });
                }}
                disabled={updateAppointmentMutation.isPending}
              >
                {updateAppointmentMutation.isPending ? "Updating..." : "Update Appointment"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Delete Appointment Dialog */}
        <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Appointment</AlertDialogTitle>
              <AlertDialogDescription>
                <div>
                  Are you sure you want to delete this appointment? This action cannot be undone.
                  {selectedAppointment && (
                    <div className="mt-2 p-2 bg-gray-100 dark:bg-gray-800 rounded">
                      <div><strong>Patient:</strong> {selectedAppointment.patient?.firstName} {selectedAppointment.patient?.lastName}</div>
                      <div><strong>Date:</strong> {format(parseISO(selectedAppointment.appointmentDate), 'MMM d, yyyy')}</div>
                      <div><strong>Time:</strong> {selectedAppointment.startTime} - {selectedAppointment.endTime}</div>
                    </div>
                  )}
                </div>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => {
                  if (selectedAppointment) {
                    deleteAppointmentMutation.mutate(selectedAppointment.id);
                  }
                }}
                className="bg-red-600 hover:bg-red-700"
                disabled={deleteAppointmentMutation.isPending}
              >
                {deleteAppointmentMutation.isPending ? "Deleting..." : "Delete"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Quick Book Dialog */}
        <Dialog open={showQuickBookDialog} onOpenChange={setShowQuickBookDialog}>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>Book Appointment</DialogTitle>
              <DialogDescription>
                Schedule a new appointment for {selectedDate}.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="quick-patient-name" className="text-right">
                  Patient Name
                </Label>
                <Input
                  id="quick-patient-name"
                  value={patientName}
                  onChange={(e) => setPatientName(e.target.value)}
                  className="col-span-3"
                  placeholder="Enter patient's full name"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="quick-patient-phone" className="text-right">
                  Phone
                </Label>
                <Input
                  id="quick-patient-phone"
                  value={patientPhone}
                  onChange={(e) => setPatientPhone(e.target.value)}
                  className="col-span-3"
                  placeholder="Enter phone number"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="quick-procedure" className="text-right">
                  Procedure
                </Label>
                <Input
                  id="quick-procedure"
                  value={procedure}
                  onChange={(e) => setProcedure(e.target.value)}
                  className="col-span-3"
                  placeholder="Enter procedure or treatment"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="quick-start-time" className="text-right">
                  Start Time
                </Label>
                <Select value={appointmentStartTime} onValueChange={setAppointmentStartTime}>
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Select start time" />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 48 }, (_, i) => {
                      const hour = Math.floor(i / 2);
                      const minute = (i % 2) * 30;
                      const time = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
                      return (
                        <SelectItem key={time} value={time}>
                          {time}
                        </SelectItem>
                      );
                    })}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="quick-end-time" className="text-right">
                  End Time
                </Label>
                <Select value={appointmentEndTime} onValueChange={setAppointmentEndTime}>
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Select end time" />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 48 }, (_, i) => {
                      const hour = Math.floor(i / 2);
                      const minute = (i % 2) * 30;
                      const time = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
                      return (
                        <SelectItem key={time} value={time}>
                          {time}
                        </SelectItem>
                      );
                    })}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setShowQuickBookDialog(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  setAppointmentDate(selectedDate);
                  const appointmentData = {
                    doctorId: doctor?.id,
                    patientName: patientName.trim(),
                    patientPhone: patientPhone.trim(),
                    procedure: procedure.trim(),
                    appointmentDate: selectedDate,
                    startTime: appointmentStartTime,
                    endTime: appointmentEndTime,
                    notes: notes.trim(),
                    status: "scheduled",
                    type: "consultation"
                  };
                  schedulePatientMutation.mutate(appointmentData);
                }}
                disabled={schedulePatientMutation.isPending || !patientName.trim() || !patientPhone.trim() || !procedure.trim() || !appointmentStartTime || !appointmentEndTime}
              >
                {schedulePatientMutation.isPending ? "Booking..." : "Book Appointment"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        {/* Clinic Day Add Patient Dialog */}
        <Dialog open={!!clinicAddDialog} onOpenChange={open => { if (!open) setClinicAddDialog(null); }}>
          <DialogContent className="sm:max-w-[420px]">
            <DialogHeader>
              <DialogTitle>Add Patient to Clinic</DialogTitle>
              <DialogDescription>
                {clinicAddDialog && (
                  <span>
                    {clinicAddDialog.clinic.name} · {formatTime12Dr(minsToHHMMDr(clinicAddDialog.windowStart))} – {formatTime12Dr(minsToHHMMDr(clinicAddDialog.windowEnd))}
                  </span>
                )}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div>
                <Label htmlFor="clinic-patient-name">Patient Name *</Label>
                <Input id="clinic-patient-name" placeholder="Full name" value={clinicAddForm.patientName}
                  onChange={e => setClinicAddForm(f => ({ ...f, patientName: e.target.value }))} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="clinic-patient-phone">Phone *</Label>
                <Input id="clinic-patient-phone" placeholder="Phone number" value={clinicAddForm.patientPhone}
                  onChange={e => setClinicAddForm(f => ({ ...f, patientPhone: e.target.value }))} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="clinic-procedure">Procedure *</Label>
                <Input id="clinic-procedure" placeholder="e.g. Consultation, Crown Preparation" value={clinicAddForm.procedure}
                  onChange={e => setClinicAddForm(f => ({ ...f, procedure: e.target.value }))} className="mt-1" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="clinic-start-time">Start Time</Label>
                  <Input id="clinic-start-time" type="time" value={clinicAddForm.startTime}
                    onChange={e => setClinicAddForm(f => ({ ...f, startTime: e.target.value }))} className="mt-1" />
                </div>
                <div>
                  <Label htmlFor="clinic-end-time">End Time</Label>
                  <Input id="clinic-end-time" type="time" value={clinicAddForm.endTime}
                    onChange={e => setClinicAddForm(f => ({ ...f, endTime: e.target.value }))} className="mt-1" />
                </div>
              </div>
              <div>
                <Label htmlFor="clinic-notes">Notes</Label>
                <Input id="clinic-notes" placeholder="Optional notes" value={clinicAddForm.notes}
                  onChange={e => setClinicAddForm(f => ({ ...f, notes: e.target.value }))} className="mt-1" />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setClinicAddDialog(null)}>Cancel</Button>
              <Button
                disabled={clinicAddMutation.isPending || !clinicAddForm.patientName.trim() || !clinicAddForm.patientPhone.trim() || !clinicAddForm.procedure.trim()}
                onClick={() => {
                  if (!clinicAddDialog || !doctor) return;
                  clinicAddMutation.mutate({
                    doctorId: doctor.id,
                    clinicId: clinicAddDialog.clinic.id,
                    patientName: clinicAddForm.patientName.trim(),
                    patientPhone: clinicAddForm.patientPhone.trim(),
                    procedure: clinicAddForm.procedure.trim(),
                    notes: clinicAddForm.notes.trim(),
                    appointmentDate: clinicDayDate,
                    startTime: clinicAddForm.startTime,
                    endTime: clinicAddForm.endTime,
                    status: "scheduled",
                    type: "consultation",
                  });
                }}
              >
                {clinicAddMutation.isPending ? "Booking..." : "Book Patient"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

      </main>

      {/* Patient Arrival Notification */}
      <PatientArrivalNotification 
        notification={notification} 
        onDismiss={handleDismissNotification} 
      />
    </div>
  );
}

