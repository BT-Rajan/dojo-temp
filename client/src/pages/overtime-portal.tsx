import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import {
  format, startOfWeek, endOfWeek, addWeeks, subWeeks, addDays, isToday,
} from "date-fns";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  ChevronLeft, ChevronRight, Plus, LogOut, Clock, User, Stethoscope,
  Lock, Unlock, Trash2, Edit2, Building2, CalendarDays, ClipboardCheck,
  BarChart3, CheckCircle2, ScrollText, Copy, Check, X,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

const TIME_SLOTS = [
  { key: "14:00-15:00", label: "2:00 – 3:00 PM" },
  { key: "15:00-16:00", label: "3:00 – 4:00 PM" },
  { key: "16:00-17:00", label: "4:00 – 5:00 PM" },
  { key: "17:00-18:00", label: "5:00 – 6:00 PM" },
];

const PROCEDURE_FIELDS = [
  { key: "treatedPatients", label: "Treated Patients", icon: "👥" },
  { key: "alginatePreparation", label: "Alginate Preparation", icon: "🧪" },
  { key: "crownPreparation", label: "Crown Preparation", icon: "👑" },
  { key: "bridgePreparation", label: "Bridge Preparation", icon: "🌉" },
  { key: "finalImpression", label: "Final Impression", icon: "🖨️" },
  { key: "tempCementation", label: "Temp. Cementation", icon: "🔧" },
  { key: "cementAccBb", label: "Cement ACC & BB", icon: "🧱" },
  { key: "cementPorcelainCb", label: "Cement Porcelain C&B", icon: "🦷" },
  { key: "metalCrownCb", label: "Metal Crown C&B", icon: "⚙️" },
  { key: "porcelainCb", label: "Porcelain C&B", icon: "💎" },
  { key: "postPreparation", label: "Post Preparation", icon: "📍" },
  { key: "postCanal", label: "Post Canal", icon: "🔌" },
  { key: "compositeFilling", label: "Composite Filling", icon: "🎨" },
  { key: "amalgamFilling", label: "Amalgam Filling", icon: "⚪" },
  { key: "removableProstho", label: "Removable Prostho.", icon: "🦷" },
  { key: "removableProsthoRepair", label: "Removable Prostho. Repair", icon: "🔨" },
  { key: "cbRemovalPostCore", label: "C&B Removal / Post & Core", icon: "🗑️" },
  { key: "orthoAppliances", label: "Ortho Appliances", icon: "🦷" },
  { key: "buckleAppointment", label: "Buckle Appointment", icon: "📋" },
  { key: "implantUnits", label: "Implant Units", icon: "🔩" },
  { key: "tryIn", label: "Try-In", icon: "🔍" },
  { key: "miscellaneous", label: "Miscellaneous", icon: "📝" },
  { key: "examination", label: "Examination", icon: "🩺" },
] as const;

const EMPTY_PROC: Record<string, number> = Object.fromEntries(PROCEDURE_FIELDS.map(f => [f.key, 0]));

const SLOT_PROC_FIELDS = PROCEDURE_FIELDS.filter(f => f.key !== "treatedPatients");
const EMPTY_SLOT_PROC: Record<string, number> = Object.fromEntries(SLOT_PROC_FIELDS.map(f => [f.key, 0]));

interface DoctorUser {
  id: number;
  name: string;
  title: string;
  departmentId: number;
}

interface OvertimeSession {
  id: number;
  departmentId: number;
  clinicName: string;
  doctorId: number | null;
  sessionDate: string;
  isOpen: boolean;
  notes: string | null;
  doctor: { id: number; name: string; title: string } | null;
}

interface OvertimeSlotEntry {
  id: number;
  sessionId: number;
  timeSlot: string;
  patientName: string | null;
  civilId: string | null;
  phone: string | null;
  procedure: string | null;
  notes: string | null;
  status: string | null; // "completed", "cancelled", "no_show", null
}

interface OvertimeProcedureLog {
  id: number;
  sessionId: number;
  doctorId: number;
  departmentId: number;
  sessionDate: string;
  treatedPatients: number;
  [key: string]: any;
}

export default function OvertimePortal() {
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  const qc = useQueryClient();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [doctorUser, setDoctorUser] = useState<DoctorUser | null>(null);
  const centerId = localStorage.getItem("selectedCenterId") || "";
  const [selectedDeptId, setSelectedDeptId] = useState<string>("");
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date(), { weekStartsOn: 0 }));
  const [activeTab, setActiveTab] = useState<"schedule" | "stats">("schedule");

  // Session dialog
  const [showAddSession, setShowAddSession] = useState(false);
  const [sessionForm, setSessionForm] = useState({ clinicName: "", doctorId: "", sessionDate: format(new Date(), "yyyy-MM-dd"), notes: "" });

  // Slot entry dialog
  const [slotDialog, setSlotDialog] = useState<{ sessionId: number; timeSlot: string; existing?: OvertimeSlotEntry } | null>(null);
  const [slotForm, setSlotForm] = useState({ patientName: "", civilId: "", phone: "", procedure: "", notes: "" });

  // Per-patient slot procedure log dialog
  const [slotProcLogDialog, setSlotProcLogDialog] = useState<{ entry: OvertimeSlotEntry; session: OvertimeSession } | null>(null);
  const [slotProcLogForm, setSlotProcLogForm] = useState<Record<string, number>>({ ...EMPTY_SLOT_PROC });

  // Per-session procedure log dialog (feeds the stats page)
  const [procLogDialog, setProcLogDialog] = useState<{ session: OvertimeSession } | null>(null);
  const [procLogForm, setProcLogForm] = useState<Record<string, number>>({ ...EMPTY_PROC });

  // Delete confirms
  const [deleteSessionId, setDeleteSessionId] = useState<number | null>(null);
  const [deleteSlotId, setDeleteSlotId] = useState<number | null>(null);

  // Stats filters
  const [statsStartDate, setStatsStartDate] = useState(format(new Date(new Date().getFullYear(), new Date().getMonth(), 1), "yyyy-MM-dd"));
  const [statsEndDate, setStatsEndDate] = useState(format(new Date(), "yyyy-MM-dd"));
  const [statsFilterDoctor, setStatsFilterDoctor] = useState<string>("all");

  // Load doctor from localStorage
  useEffect(() => {
    const stored = localStorage.getItem("doctorUser");
    if (stored) {
      try { setDoctorUser(JSON.parse(stored)); } catch {}
    }
  }, []);

  // Redirect if not logged in
  useEffect(() => {
    if (authLoading) return;
    const stored = localStorage.getItem("doctorUser");
    if (!stored && !isAuthenticated) setLocation("/doctor-login");
  }, [authLoading, isAuthenticated, setLocation]);

  // Auto-select department for doctors
  useEffect(() => {
    if (doctorUser && !selectedDeptId) setSelectedDeptId(String(doctorUser.departmentId));
  }, [doctorUser, selectedDeptId]);

  // Departments
  const { data: departments = [] } = useQuery<any[]>({
    queryKey: ["/api/user/departments", centerId],
    queryFn: async () => {
      const url = centerId ? `/api/user/departments?centerId=${centerId}` : "/api/user/departments";
      const res = await fetch(url, { credentials: "include" });
      return res.json();
    },
    enabled: isAuthenticated,
  });

  // Doctors in selected department
  const { data: doctors = [] } = useQuery<any[]>({
    queryKey: ["/api/doctors", "dept", selectedDeptId],
    queryFn: async () => {
      const res = await fetch(`/api/doctors?departmentId=${selectedDeptId}`, { credentials: "include" });
      return res.json();
    },
    enabled: !!selectedDeptId,
  });

  // Current main user
  const { data: currentUser } = useQuery<any>({
    queryKey: ["/api/auth/user"],
    enabled: isAuthenticated,
  });

  const selectedDept = departments.find((d: any) => String(d.id) === selectedDeptId);
  const isDeptHead = isAuthenticated && currentUser && selectedDept && selectedDept.headUserId === currentUser.id;

  const weekEnd = endOfWeek(weekStart, { weekStartsOn: 0 });
  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  // Sessions for the week
  const { data: sessions = [] } = useQuery<OvertimeSession[]>({
    queryKey: ["/api/overtime/sessions", selectedDeptId, format(weekStart, "yyyy-MM-dd"), format(weekEnd, "yyyy-MM-dd")],
    queryFn: async () => {
      const res = await fetch(
        `/api/overtime/sessions?departmentId=${selectedDeptId}&startDate=${format(weekStart, "yyyy-MM-dd")}&endDate=${format(weekEnd, "yyyy-MM-dd")}`,
        { credentials: "include" }
      );
      return res.json();
    },
    enabled: !!selectedDeptId,
    refetchInterval: 30000,
  });

  const sessionIds = sessions.map(s => s.id);

  // Slot entries for visible sessions
  const { data: allSlotEntries = [] } = useQuery<OvertimeSlotEntry[]>({
    queryKey: ["/api/overtime/all-slots", sessionIds.join(",")],
    queryFn: async () => {
      if (sessionIds.length === 0) return [];
      const results = await Promise.all(
        sessionIds.map(id =>
          fetch(`/api/overtime/slots?sessionId=${id}`, { credentials: "include" }).then(r => r.json())
        )
      );
      return results.flat();
    },
    enabled: sessionIds.length > 0,
    refetchInterval: 30000,
  });

  // Per-patient slot procedure logs for visible sessions
  const { data: allSlotProcLogs = [] } = useQuery<any[]>({
    queryKey: ["/api/overtime/slot-logs-batch", sessionIds.join(",")],
    queryFn: async () => {
      if (sessionIds.length === 0) return [];
      const results = await Promise.all(
        sessionIds.map(id =>
          fetch(`/api/overtime/slot-logs?sessionId=${id}`, { credentials: "include" }).then(r => r.json())
        )
      );
      return results.flat().filter(Boolean);
    },
    enabled: sessionIds.length > 0,
    refetchInterval: 30000,
  });

  const slotProcLogBySlotId: Record<number, any> = {};
  for (const log of allSlotProcLogs) {
    if (log) slotProcLogBySlotId[log.slotEntryId] = log;
  }

  // Session-level procedure logs (feeds the Overtime Stats page)
  const { data: allSessionProcLogs = [] } = useQuery<any[]>({
    queryKey: ["/api/overtime/session-logs-batch", sessionIds.join(",")],
    queryFn: async () => {
      if (sessionIds.length === 0) return [];
      const results = await Promise.all(
        sessionIds.map(id =>
          fetch(`/api/overtime/procedure-logs?sessionId=${id}`, { credentials: "include" }).then(r => r.json())
        )
      );
      return results.filter(Boolean);
    },
    enabled: sessionIds.length > 0,
  });

  const sessionProcLogBySessionId: Record<number, any> = {};
  for (const log of allSessionProcLogs) {
    if (log) sessionProcLogBySessionId[log.sessionId] = log;
  }

  // Overtime stats query
  const { data: overtimeStats, isLoading: statsLoading } = useQuery<any>({
    queryKey: ["/api/overtime/stats", selectedDeptId, statsStartDate, statsEndDate, statsFilterDoctor],
    queryFn: async () => {
      const params = new URLSearchParams({
        departmentId: selectedDeptId,
        startDate: statsStartDate,
        endDate: statsEndDate,
      });
      if (statsFilterDoctor && statsFilterDoctor !== "all") params.set("doctorId", statsFilterDoctor);
      const res = await fetch(`/api/overtime/stats?${params}`, { credentials: "include" });
      return res.json();
    },
    enabled: !!selectedDeptId && activeTab === "stats",
  });

  const slotsBySession: Record<number, OvertimeSlotEntry[]> = {};
  for (const e of allSlotEntries) {
    if (!slotsBySession[e.sessionId]) slotsBySession[e.sessionId] = [];
    slotsBySession[e.sessionId].push(e);
  }

  const invalidateSessions = () => {
    qc.invalidateQueries({ queryKey: ["/api/overtime/sessions", selectedDeptId] });
    qc.invalidateQueries({ queryKey: ["/api/overtime/all-slots"] });
    qc.invalidateQueries({ queryKey: ["/api/overtime/slot-logs-batch"] });
  };

  // Mutations
  const createSession = useMutation({
    mutationFn: (data: any) => apiRequest("/api/overtime/sessions", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => { invalidateSessions(); setShowAddSession(false); toast({ title: "Session created" }); },
    onError: () => toast({ title: "Failed to create session", variant: "destructive" }),
  });

  const toggleSession = useMutation({
    mutationFn: ({ id, isOpen }: { id: number; isOpen: boolean }) =>
      apiRequest(`/api/overtime/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ isOpen }) }),
    onSuccess: () => invalidateSessions(),
    onError: () => toast({ title: "Failed to update session", variant: "destructive" }),
  });

  const deleteSession = useMutation({
    mutationFn: (id: number) => apiRequest(`/api/overtime/sessions/${id}`, { method: "DELETE" }),
    onSuccess: () => { invalidateSessions(); setDeleteSessionId(null); toast({ title: "Session deleted" }); },
    onError: () => toast({ title: "Failed to delete session", variant: "destructive" }),
  });

  const saveSlot = useMutation({
    mutationFn: async (data: { sessionId: number; timeSlot: string; form: typeof slotForm; existingId?: number }) => {
      const payload = { sessionId: data.sessionId, timeSlot: data.timeSlot, ...data.form };
      if (data.existingId) return apiRequest(`/api/overtime/slots/${data.existingId}`, { method: "PUT", body: JSON.stringify(payload) });
      return apiRequest("/api/overtime/slots", { method: "POST", body: JSON.stringify(payload) });
    },
    onSuccess: () => { invalidateSessions(); setSlotDialog(null); toast({ title: "Slot saved" }); },
    onError: () => toast({ title: "Failed to save slot", variant: "destructive" }),
  });

  const deleteSlot = useMutation({
    mutationFn: (id: number) => apiRequest(`/api/overtime/slots/${id}`, { method: "DELETE" }),
    onSuccess: () => { invalidateSessions(); setDeleteSlotId(null); toast({ title: "Slot cleared" }); },
    onError: () => toast({ title: "Failed to clear slot", variant: "destructive" }),
  });

  const updateSlotStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string | null }) =>
      apiRequest(`/api/overtime/slots/${id}`, { method: "PUT", body: JSON.stringify({ status }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["/api/overtime/all-slots"] }),
    onError: () => toast({ title: "Failed to update patient status", variant: "destructive" }),
  });

  const updateSessionDoctor = useMutation({
    mutationFn: ({ id, doctorId }: { id: number; doctorId: number | null }) =>
      apiRequest(`/api/overtime/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ doctorId }) }),
    onSuccess: () => invalidateSessions(),
    onError: () => toast({ title: "Failed to update doctor assignment", variant: "destructive" }),
  });

  const copyWeek = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("/api/overtime/copy-week", {
        method: "POST",
        body: JSON.stringify({
          departmentId: parseInt(selectedDeptId),
          fromStart: format(weekStart, "yyyy-MM-dd"),
          fromEnd: format(weekEnd, "yyyy-MM-dd"),
        }),
      });
      return res.json();
    },
    onSuccess: (data: any) => {
      setWeekStart(w => addWeeks(w, 1));
      invalidateSessions();
      toast({ title: `Copied to next week`, description: `${data.created} session${data.created !== 1 ? "s" : ""} created${data.skipped ? `, ${data.skipped} already existed` : ""}` });
    },
    onError: () => toast({ title: "Failed to copy sessions", variant: "destructive" }),
  });

  const saveSlotProcLog = useMutation({
    mutationFn: (data: any) => apiRequest("/api/overtime/slot-logs", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/overtime/slot-logs-batch"] });
      qc.invalidateQueries({ queryKey: ["/api/overtime/stats"] });
      setSlotProcLogDialog(null);
      toast({ title: "Procedures logged" });
    },
    onError: () => toast({ title: "Failed to save procedure log", variant: "destructive" }),
  });

  const saveSessionProcLog = useMutation({
    mutationFn: (data: any) => apiRequest("/api/overtime/procedure-logs", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/overtime/session-logs-batch"] });
      qc.invalidateQueries({ queryKey: ["/api/overtime/stats"] });
      setProcLogDialog(null);
      toast({ title: "Session procedures logged" });
    },
    onError: () => toast({ title: "Failed to save session log", variant: "destructive" }),
  });

  const handleLogout = () => {
    if (doctorUser) {
      localStorage.removeItem("doctorUser");
      setLocation("/doctor-login");
    } else {
      setLocation("/");
    }
  };

  const openSlotDialog = (session: OvertimeSession, timeSlot: string) => {
    if (!session.isOpen && !isDeptHead) return;
    const existing = slotsBySession[session.id]?.find(e => e.timeSlot === timeSlot);
    setSlotDialog({ sessionId: session.id, timeSlot, existing });
    setSlotForm({
      patientName: existing?.patientName || "",
      civilId: existing?.civilId || "",
      phone: existing?.phone || "",
      procedure: existing?.procedure || "",
      notes: existing?.notes || "",
    });
  };

  const openAddSession = () => {
    setSessionForm({ clinicName: "", doctorId: "", sessionDate: format(new Date(), "yyyy-MM-dd"), notes: "" });
    setShowAddSession(true);
  };

  const submitSession = () => {
    if (!sessionForm.clinicName || !sessionForm.sessionDate || !selectedDeptId) return;
    createSession.mutate({
      departmentId: parseInt(selectedDeptId),
      clinicName: sessionForm.clinicName,
      doctorId: sessionForm.doctorId ? parseInt(sessionForm.doctorId) : null,
      sessionDate: sessionForm.sessionDate,
      notes: sessionForm.notes || null,
      isOpen: true,
    });
  };

  const submitSlot = () => {
    if (!slotDialog) return;
    saveSlot.mutate({ sessionId: slotDialog.sessionId, timeSlot: slotDialog.timeSlot, form: slotForm, existingId: slotDialog.existing?.id });
  };

  const handleSlotStatusClick = (entry: OvertimeSlotEntry, session: OvertimeSession, newStatus: string) => {
    const currentStatus = entry.status;
    const toggledStatus = currentStatus === newStatus ? null : newStatus;
    updateSlotStatus.mutate({ id: entry.id, status: toggledStatus });
    if (newStatus === "completed" && toggledStatus === "completed") {
      // Open procedure dialog for completed patients
      const existing = slotProcLogBySlotId[entry.id];
      const vals: Record<string, number> = { ...EMPTY_SLOT_PROC };
      if (existing) {
        for (const f of SLOT_PROC_FIELDS) { vals[f.key] = existing[f.key] ?? 0; }
      }
      setSlotProcLogForm(vals);
      setSlotProcLogDialog({ entry, session });
    }
  };

  const openSlotProcLogDialog = (entry: OvertimeSlotEntry, session: OvertimeSession) => {
    const existing = slotProcLogBySlotId[entry.id];
    const vals: Record<string, number> = { ...EMPTY_SLOT_PROC };
    if (existing) {
      for (const f of SLOT_PROC_FIELDS) { vals[f.key] = existing[f.key] ?? 0; }
    }
    setSlotProcLogForm(vals);
    setSlotProcLogDialog({ entry, session });
  };

  const submitSlotProcLog = () => {
    if (!slotProcLogDialog) return;
    saveSlotProcLog.mutate({ slotEntryId: slotProcLogDialog.entry.id, ...slotProcLogForm });
  };

  const openSessionProcLog = (session: OvertimeSession) => {
    const existing = sessionProcLogBySessionId[session.id];
    const vals: Record<string, number> = { ...EMPTY_PROC };
    if (existing) {
      for (const f of PROCEDURE_FIELDS) { vals[f.key] = existing[f.key] ?? 0; }
    }
    setProcLogForm(vals);
    setProcLogDialog({ session });
  };

  const submitSessionProcLog = () => {
    if (!procLogDialog) return;
    const session = procLogDialog.session;
    const doctorId = session.doctorId || doctorUser?.id;
    if (!doctorId) {
      toast({ title: "Session has no assigned doctor", variant: "destructive" });
      return;
    }
    saveSessionProcLog.mutate({
      sessionId: session.id,
      doctorId,
      departmentId: session.departmentId,
      sessionDate: session.sessionDate,
      ...procLogForm,
    });
  };

  const sessionsByDate: Record<string, OvertimeSession[]> = {};
  for (const s of sessions) {
    if (!sessionsByDate[s.sessionDate]) sessionsByDate[s.sessionDate] = [];
    sessionsByDate[s.sessionDate].push(s);
  }

  const weekDaysDisplay = weekDays;

  // Stats helpers
  const statsProcs = PROCEDURE_FIELDS.filter(f => f.key !== "treatedPatients");
  const topProcedures = overtimeStats ? statsProcs
    .map(f => ({ label: f.label, icon: f.icon, count: overtimeStats.departmentTotals?.procedureTotals?.[f.key] || 0 }))
    .filter(p => p.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, 8) : [];
  const maxProc = topProcedures[0]?.count || 1;

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-amber-50 to-yellow-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-orange-600 to-amber-600 text-white px-6 py-4 shadow-lg">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
              <Clock className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Overtime Portal</h1>
              <p className="text-orange-100 text-sm">Overtime Clinic Schedule & Statistics</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {doctorUser && (
              <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5">
                <User className="w-4 h-4" />
                <span className="text-sm font-medium">Dr. {doctorUser.name}</span>
              </div>
            )}
            {isDeptHead && (
              <Badge className="bg-white/20 text-white border-white/30">Department Head</Badge>
            )}
            <Button size="sm" variant="ghost" className="text-white hover:bg-white/20" onClick={handleLogout}>
              <LogOut className="w-4 h-4 mr-1" />
              {doctorUser ? "Logout" : "Back"}
            </Button>
          </div>
        </div>

        {/* Tab bar */}
        <div className="max-w-7xl mx-auto mt-4 flex gap-1">
          <button
            onClick={() => setActiveTab("schedule")}
            className={`flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
              activeTab === "schedule"
                ? "bg-white text-orange-700"
                : "text-orange-100 hover:bg-white/10"
            }`}
          >
            <CalendarDays className="w-4 h-4" />
            Schedule
          </button>
          <button
            onClick={() => setActiveTab("stats")}
            className={`flex items-center gap-2 px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
              activeTab === "stats"
                ? "bg-white text-orange-700"
                : "text-orange-100 hover:bg-white/10"
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            Overtime Stats
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">

        {/* ═══ SCHEDULE TAB ═══════════════════════════════════════════ */}
        {activeTab === "schedule" && (
          <>
            {/* Controls row */}
            <div className="flex flex-wrap gap-4 items-center justify-between">
              {isAuthenticated && departments.length > 0 && (
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-orange-600" />
                  <Select value={selectedDeptId} onValueChange={setSelectedDeptId}>
                    <SelectTrigger className="w-56 border-orange-200">
                      <SelectValue placeholder="Select department..." />
                    </SelectTrigger>
                    <SelectContent>
                      {departments.map((d: any) => (
                        <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              {doctorUser && (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Stethoscope className="w-4 h-4 text-orange-500" />
                  <span>Your department's overtime schedule</span>
                </div>
              )}

              <div className="flex items-center gap-2 ml-auto">
                <Button variant="outline" size="sm" onClick={() => setWeekStart(w => subWeeks(w, 1))}>
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white rounded-lg border border-orange-200 text-sm font-medium text-gray-700">
                  <CalendarDays className="w-4 h-4 text-orange-500" />
                  <span>{format(weekStart, "MMM d")} – {format(weekEnd, "MMM d, yyyy")}</span>
                </div>
                <Button variant="outline" size="sm" onClick={() => setWeekStart(w => addWeeks(w, 1))}>
                  <ChevronRight className="w-4 h-4" />
                </Button>
                <Button variant="outline" size="sm" onClick={() => setWeekStart(startOfWeek(new Date(), { weekStartsOn: 0 }))} className="border-orange-200 text-orange-600 hover:bg-orange-50">
                  Today
                </Button>
                {isDeptHead && selectedDeptId && (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-orange-300 text-orange-700 hover:bg-orange-50 ml-2"
                      onClick={() => copyWeek.mutate()}
                      disabled={copyWeek.isPending || sessions.length === 0}
                      title="Copy this week's sessions to next week"
                    >
                      <Copy className="w-4 h-4 mr-1" />
                      {copyWeek.isPending ? "Copying..." : "Copy to Next Week"}
                    </Button>
                    <Button size="sm" onClick={openAddSession} className="bg-orange-600 hover:bg-orange-700 text-white ml-2">
                      <Plus className="w-4 h-4 mr-1" />
                      Add Session
                    </Button>
                  </>
                )}
              </div>
            </div>

            {!selectedDeptId && (
              <Card className="border-orange-200">
                <CardContent className="py-12 text-center text-gray-500">
                  <Building2 className="w-12 h-12 mx-auto mb-3 text-orange-300" />
                  <p className="text-lg font-medium">Select a department to view the overtime schedule</p>
                </CardContent>
              </Card>
            )}

            {selectedDeptId && sessions.length === 0 && (
              <Card className="border-orange-200">
                <CardContent className="py-14 text-center text-gray-500">
                  <CalendarDays className="w-14 h-14 mx-auto mb-4 text-orange-200" />
                  <p className="text-lg font-semibold text-gray-700 mb-1">No overtime sessions this week</p>
                  <p className="text-sm text-gray-400">
                    {isDeptHead
                      ? 'Click "Add Session" above to schedule an overtime clinic.'
                      : "No overtime clinics have been scheduled for this week yet."}
                  </p>
                </CardContent>
              </Card>
            )}

            {selectedDeptId && weekDaysDisplay.map(day => {
              const dateStr = format(day, "yyyy-MM-dd");
              const daySessions = sessionsByDate[dateStr] || [];
              if (daySessions.length === 0 && !isDeptHead) return null;

              return (
                <Card key={dateStr} className={`border-orange-100 shadow-sm ${isToday(day) ? "ring-2 ring-orange-400" : ""}`}>
                  <CardHeader className={`py-3 px-5 rounded-t-lg ${isToday(day) ? "bg-orange-50" : "bg-white"}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-12 h-12 rounded-lg flex flex-col items-center justify-center text-sm font-bold ${isToday(day) ? "bg-orange-600 text-white" : "bg-orange-100 text-orange-700"}`}>
                          <span className="text-xs font-normal leading-none">{format(day, "EEE")}</span>
                          <span className="text-lg leading-tight">{format(day, "d")}</span>
                        </div>
                        <div>
                          <p className="font-semibold text-gray-900">{format(day, "EEEE, MMMM d, yyyy")}</p>
                          <p className="text-sm text-gray-500">{daySessions.length} clinic{daySessions.length !== 1 ? "s" : ""} scheduled</p>
                        </div>
                      </div>
                    </div>
                  </CardHeader>

                  {daySessions.length > 0 && (
                    <CardContent className="p-0">
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="bg-amber-50 border-b border-orange-100">
                              <th className="text-left px-4 py-2 font-semibold text-gray-700 w-32">Clinic</th>
                              <th className="text-left px-4 py-2 font-semibold text-gray-700 w-44">Doctor</th>
                              {TIME_SLOTS.map(ts => (
                                <th key={ts.key} className="text-center px-2 py-2 font-semibold text-gray-700 min-w-[150px]">
                                  {ts.label}
                                </th>
                              ))}
                              {isDeptHead && <th className="text-center px-4 py-2 font-semibold text-gray-700 w-24">Actions</th>}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-orange-50">
                            {daySessions.map((session, idx) => {
                              const entries = slotsBySession[session.id] || [];
                              const canChangeDoctor = isDeptHead || (doctorUser?.id === session.doctorId && !!session.doctorId);
                              const canLogSlot = (doctorUser?.id === session.doctorId) || isDeptHead;

                              return (
                                <tr key={session.id} className={idx % 2 === 0 ? "bg-white" : "bg-orange-50/30"}>
                                  <td className="px-4 py-3 align-top">
                                    <div className="flex items-center gap-1.5">
                                      <span className="font-semibold text-gray-800">{session.clinicName}</span>
                                      {session.isOpen
                                        ? <Unlock className="w-3 h-3 text-green-500" />
                                        : <Lock className="w-3 h-3 text-red-400" />}
                                    </div>
                                    {!session.isOpen && (
                                      <Badge variant="outline" className="text-xs text-red-500 border-red-200 mt-0.5">Closed</Badge>
                                    )}
                                    {(isDeptHead || doctorUser?.id === session.doctorId) && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className={`mt-1.5 h-6 px-2 text-xs w-full ${sessionProcLogBySessionId[session.id] ? "border-green-400 text-green-700 bg-green-50 hover:bg-green-100" : "border-orange-300 text-orange-600 hover:bg-orange-50"}`}
                                        onClick={e => { e.stopPropagation(); openSessionProcLog(session); }}
                                      >
                                        <ScrollText className="w-3 h-3 mr-1" />
                                        {sessionProcLogBySessionId[session.id] ? "Logged ✓" : "Log"}
                                      </Button>
                                    )}
                                  </td>

                                  {/* Doctor cell — dropdown for dept head or assigned doctor, static text otherwise */}
                                  <td className="px-3 py-3 align-top">
                                    {canChangeDoctor ? (
                                      <Select
                                        value={session.doctorId ? String(session.doctorId) : "none"}
                                        onValueChange={val => updateSessionDoctor.mutate({ id: session.id, doctorId: val === "none" ? null : parseInt(val) })}
                                      >
                                        <SelectTrigger className="w-40 h-8 text-xs border-orange-200">
                                          <SelectValue placeholder="Unassigned" />
                                        </SelectTrigger>
                                        <SelectContent>
                                          <SelectItem value="none">Unassigned</SelectItem>
                                          {doctors.map((d: any) => (
                                            <SelectItem key={d.id} value={String(d.id)}>Dr. {d.name}</SelectItem>
                                          ))}
                                        </SelectContent>
                                      </Select>
                                    ) : session.doctor ? (
                                      <span className="text-gray-700 font-medium text-sm">Dr. {session.doctor.name}</span>
                                    ) : (
                                      <span className="text-gray-400 italic text-xs">Unassigned</span>
                                    )}
                                  </td>

                                  {TIME_SLOTS.map(ts => {
                                    const entry = entries.find(e => e.timeSlot === ts.key);
                                    const canEdit = session.isOpen || isDeptHead;
                                    const hasPatient = !!(entry && (entry.patientName || entry.civilId));
                                    const slotLog = entry ? slotProcLogBySlotId[entry.id] : null;
                                    return (
                                      <td
                                        key={ts.key}
                                        className={`px-2 py-2 align-top border-l border-orange-100 min-w-[160px] ${canEdit && !hasPatient ? "cursor-pointer hover:bg-orange-50 transition-colors" : ""}`}
                                        onClick={() => canEdit && !hasPatient && openSlotDialog(session, ts.key)}
                                      >
                                        {hasPatient && entry ? (
                                          <div className="space-y-1">
                                            {/* Patient info — click to edit */}
                                            <div
                                              className={`space-y-0.5 ${canEdit ? "cursor-pointer hover:bg-orange-50 rounded p-0.5 -m-0.5 transition-colors" : ""}`}
                                              onClick={e => { e.stopPropagation(); canEdit && openSlotDialog(session, ts.key); }}
                                            >
                                              {entry.patientName && <p className="font-medium text-gray-800 text-xs leading-tight">{entry.patientName}</p>}
                                              {entry.civilId && <p className="text-gray-500 text-xs">ID: {entry.civilId}</p>}
                                              {entry.phone && <p className="text-gray-500 text-xs">{entry.phone}</p>}
                                              {entry.procedure && <p className="text-orange-600 text-xs font-medium">{entry.procedure}</p>}
                                            </div>
                                            {/* C / X / ✓ status buttons + procedure log icon */}
                                            {canLogSlot && (
                                              <div className="flex items-center gap-1 pt-0.5" onClick={e => e.stopPropagation()}>
                                                {/* C = Cancelled */}
                                                <button
                                                  onClick={() => handleSlotStatusClick(entry, session, "cancelled")}
                                                  className={`w-6 h-6 rounded text-xs font-bold transition-colors ${entry.status === "cancelled" ? "bg-red-500 text-white" : "border border-red-300 text-red-400 hover:bg-red-50"}`}
                                                  title="Mark as Cancelled"
                                                >C</button>
                                                {/* X = No show */}
                                                <button
                                                  onClick={() => handleSlotStatusClick(entry, session, "no_show")}
                                                  className={`w-6 h-6 rounded text-xs font-bold transition-colors ${entry.status === "no_show" ? "bg-gray-500 text-white" : "border border-gray-300 text-gray-400 hover:bg-gray-50"}`}
                                                  title="Mark as No Show"
                                                >X</button>
                                                {/* ✓ = Completed */}
                                                <button
                                                  onClick={() => handleSlotStatusClick(entry, session, "completed")}
                                                  className={`w-6 h-6 rounded text-xs font-bold transition-colors ${entry.status === "completed" ? "bg-green-500 text-white" : "border border-green-300 text-green-500 hover:bg-green-50"}`}
                                                  title="Mark as Completed"
                                                >✓</button>
                                                {/* Procedures logged indicator */}
                                                {slotLog && (
                                                  <button
                                                    onClick={() => openSlotProcLogDialog(entry, session)}
                                                    className="w-6 h-6 rounded border border-orange-300 text-orange-500 hover:bg-orange-50 flex items-center justify-center transition-colors"
                                                    title="View/Edit Procedure Log"
                                                  >
                                                    <ClipboardCheck className="w-3 h-3" />
                                                  </button>
                                                )}
                                              </div>
                                            )}
                                            {/* Show status badge if not canLogSlot */}
                                            {!canLogSlot && entry.status && (
                                              <Badge variant="outline" className={`text-xs mt-0.5 ${entry.status === "completed" ? "border-green-300 text-green-600" : entry.status === "cancelled" ? "border-red-300 text-red-500" : "border-gray-300 text-gray-500"}`}>
                                                {entry.status === "completed" ? "Done" : entry.status === "cancelled" ? "Cancelled" : "No Show"}
                                              </Badge>
                                            )}
                                          </div>
                                        ) : (
                                          <div className="flex items-center justify-center h-10 text-gray-300">
                                            {canEdit ? (
                                              <div className="flex items-center gap-1 text-xs text-gray-400 hover:text-orange-500">
                                                <Plus className="w-3 h-3" />
                                                <span>Add patient</span>
                                              </div>
                                            ) : (
                                              <span className="text-xs">—</span>
                                            )}
                                          </div>
                                        )}
                                      </td>
                                    );
                                  })}

                                  {/* Dept head actions */}
                                  {isDeptHead && (
                                    <td className="px-4 py-3 align-top">
                                      <div className="flex flex-col gap-1 items-center">
                                        <Button
                                          size="sm"
                                          variant="ghost"
                                          className={`h-7 px-2 text-xs ${session.isOpen ? "text-red-600 hover:bg-red-50" : "text-green-600 hover:bg-green-50"}`}
                                          onClick={() => toggleSession.mutate({ id: session.id, isOpen: !session.isOpen })}
                                        >
                                          {session.isOpen ? <Lock className="w-3.5 h-3.5 mr-1" /> : <Unlock className="w-3.5 h-3.5 mr-1" />}
                                          {session.isOpen ? "Close" : "Open"}
                                        </Button>
                                        <Button
                                          size="sm"
                                          variant="ghost"
                                          className="h-7 px-2 text-xs text-red-500 hover:bg-red-50"
                                          onClick={() => setDeleteSessionId(session.id)}
                                        >
                                          <Trash2 className="w-3.5 h-3.5 mr-1" />
                                          Delete
                                        </Button>
                                      </div>
                                    </td>
                                  )}
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  )}

                  {daySessions.length === 0 && isDeptHead && (
                    <CardContent className="py-6 text-center text-gray-400 text-sm">
                      No overtime sessions on this day.
                      <Button variant="link" size="sm" className="text-orange-600 ml-1 p-0 h-auto" onClick={() => {
                        setSessionForm(f => ({ ...f, sessionDate: dateStr }));
                        setShowAddSession(true);
                      }}>
                        Add one
                      </Button>
                    </CardContent>
                  )}
                </Card>
              );
            })}

            {selectedDeptId && !isDeptHead && sessions.length === 0 && (
              <Card className="border-orange-100">
                <CardContent className="py-16 text-center text-gray-500">
                  <Clock className="w-14 h-14 mx-auto mb-4 text-orange-200" />
                  <p className="text-lg font-medium">No overtime sessions this week</p>
                  <p className="text-sm mt-1">Check back later or navigate to a different week.</p>
                </CardContent>
              </Card>
            )}
          </>
        )}

        {/* ═══ STATS TAB ══════════════════════════════════════════════ */}
        {activeTab === "stats" && (
          <>
            {/* Department selector for stats (if main auth user) */}
            {isAuthenticated && departments.length > 0 && (
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-orange-600" />
                <Select value={selectedDeptId} onValueChange={setSelectedDeptId}>
                  <SelectTrigger className="w-56 border-orange-200">
                    <SelectValue placeholder="Select department..." />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map((d: any) => (
                      <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {!selectedDeptId ? (
              <Card className="border-orange-200">
                <CardContent className="py-12 text-center text-gray-500">
                  <BarChart3 className="w-12 h-12 mx-auto mb-3 text-orange-300" />
                  <p className="text-lg font-medium">Select a department to view overtime statistics</p>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Filters */}
                <Card className="border-orange-100">
                  <CardContent className="py-4">
                    <div className="flex flex-wrap gap-4 items-end">
                      <div>
                        <Label className="text-xs text-gray-500 mb-1 block">From</Label>
                        <Input type="date" value={statsStartDate} onChange={e => setStatsStartDate(e.target.value)} className="w-40 border-orange-200" />
                      </div>
                      <div>
                        <Label className="text-xs text-gray-500 mb-1 block">To</Label>
                        <Input type="date" value={statsEndDate} onChange={e => setStatsEndDate(e.target.value)} className="w-40 border-orange-200" />
                      </div>
                      <div>
                        <Label className="text-xs text-gray-500 mb-1 block">Doctor</Label>
                        <Select value={statsFilterDoctor} onValueChange={setStatsFilterDoctor}>
                          <SelectTrigger className="w-52 border-orange-200">
                            <SelectValue placeholder="All doctors" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">All doctors</SelectItem>
                            {doctors.map((d: any) => (
                              <SelectItem key={d.id} value={String(d.id)}>Dr. {d.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {statsLoading && (
                  <Card className="border-orange-100">
                    <CardContent className="py-12 text-center text-gray-500">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500 mx-auto mb-3" />
                      <p>Loading overtime statistics...</p>
                    </CardContent>
                  </Card>
                )}

                {!statsLoading && overtimeStats && (
                  <>
                    {/* Summary cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <Card className="border-orange-100 bg-gradient-to-br from-orange-50 to-amber-50">
                        <CardContent className="py-4 text-center">
                          <p className="text-3xl font-bold text-orange-700">{overtimeStats.departmentTotals?.treatedPatients || 0}</p>
                          <p className="text-sm text-gray-600 mt-1">Total Patients Treated</p>
                        </CardContent>
                      </Card>
                      <Card className="border-orange-100 bg-gradient-to-br from-amber-50 to-yellow-50">
                        <CardContent className="py-4 text-center">
                          <p className="text-3xl font-bold text-amber-700">{overtimeStats.departmentTotals?.sessionCount || 0}</p>
                          <p className="text-sm text-gray-600 mt-1">Sessions Logged</p>
                        </CardContent>
                      </Card>
                      <Card className="border-orange-100 bg-gradient-to-br from-yellow-50 to-orange-50">
                        <CardContent className="py-4 text-center">
                          <p className="text-3xl font-bold text-yellow-700">
                            {Object.values(overtimeStats.departmentTotals?.procedureTotals || {}).reduce((a: number, b) => a + (b as number), 0)}
                          </p>
                          <p className="text-sm text-gray-600 mt-1">Total Procedures</p>
                        </CardContent>
                      </Card>
                      <Card className="border-orange-100 bg-gradient-to-br from-orange-50 to-red-50">
                        <CardContent className="py-4 text-center">
                          <p className="text-3xl font-bold text-red-600">
                            {overtimeStats.perDoctor?.filter((d: any) => d.sessionCount > 0).length || 0}
                          </p>
                          <p className="text-sm text-gray-600 mt-1">Active Doctors</p>
                        </CardContent>
                      </Card>
                    </div>

                    {/* Top procedures */}
                    {topProcedures.length > 0 && (
                      <Card className="border-orange-100">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-base text-orange-800">Top Procedures</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            {topProcedures.map(p => (
                              <div key={p.label} className="flex items-center gap-3">
                                <span className="text-sm w-6 text-center">{p.icon}</span>
                                <span className="text-sm text-gray-700 w-48 truncate">{p.label}</span>
                                <div className="flex-1 bg-orange-100 rounded-full h-2">
                                  <div
                                    className="bg-gradient-to-r from-orange-500 to-amber-400 h-2 rounded-full"
                                    style={{ width: `${Math.round((p.count / maxProc) * 100)}%` }}
                                  />
                                </div>
                                <span className="text-sm font-semibold text-orange-700 w-8 text-right">{p.count}</span>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Daily breakdown */}
                    {overtimeStats.dailyBreakdown?.length > 0 && (
                      <Card className="border-orange-100">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-base text-orange-800">Daily Activity</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="flex gap-2 overflow-x-auto pb-2">
                            {overtimeStats.dailyBreakdown.map((day: any) => {
                              const maxPatients = Math.max(...overtimeStats.dailyBreakdown.map((d: any) => d.treatedPatients), 1);
                              const heightPct = Math.round((day.treatedPatients / maxPatients) * 80) + 20;
                              return (
                                <div key={day.date} className="flex flex-col items-center gap-1 min-w-[52px]">
                                  <span className="text-xs font-semibold text-orange-700">{day.treatedPatients}</span>
                                  <div className="w-8 bg-orange-100 rounded-t-md flex items-end" style={{ height: 80 }}>
                                    <div
                                      className="w-full bg-gradient-to-t from-orange-500 to-amber-400 rounded-t-md"
                                      style={{ height: `${heightPct}%` }}
                                    />
                                  </div>
                                  <span className="text-xs text-gray-500">{format(new Date(day.date + "T00:00:00"), "d MMM")}</span>
                                </div>
                              );
                            })}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Per-doctor breakdown table */}
                    {overtimeStats.perDoctor?.length > 0 && (
                      <Card className="border-orange-100">
                        <CardHeader className="pb-2">
                          <CardTitle className="text-base text-orange-800">Procedure Breakdown by Doctor</CardTitle>
                        </CardHeader>
                        <CardContent className="p-0">
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="bg-amber-50 border-b border-orange-100">
                                  <th className="text-left px-4 py-2 font-semibold text-gray-700 sticky left-0 bg-amber-50 w-48">Procedure</th>
                                  {overtimeStats.perDoctor.map((pd: any) => (
                                    <th key={pd.doctor.id} className="text-center px-3 py-2 font-semibold text-gray-700 min-w-[100px]">
                                      <div className="text-xs leading-tight">Dr. {pd.doctor.name}</div>
                                      <div className="text-xs text-gray-400 font-normal">{pd.sessionCount} sessions</div>
                                    </th>
                                  ))}
                                  <th className="text-center px-3 py-2 font-semibold text-orange-700 min-w-[80px]">Total</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-orange-50">
                                <tr className="bg-orange-50/50 font-semibold">
                                  <td className="px-4 py-2 sticky left-0 bg-orange-50/50">👥 Treated Patients</td>
                                  {overtimeStats.perDoctor.map((pd: any) => (
                                    <td key={pd.doctor.id} className="text-center px-3 py-2 text-orange-700">{pd.treatedPatients}</td>
                                  ))}
                                  <td className="text-center px-3 py-2 text-orange-800 font-bold">{overtimeStats.departmentTotals?.treatedPatients}</td>
                                </tr>
                                {statsProcs.map(f => {
                                  const deptTotal = overtimeStats.departmentTotals?.procedureTotals?.[f.key] || 0;
                                  if (deptTotal === 0) return null;
                                  return (
                                    <tr key={f.key} className="hover:bg-orange-50/30">
                                      <td className="px-4 py-2 sticky left-0 bg-white hover:bg-orange-50/30">
                                        <span className="mr-1">{f.icon}</span>{f.label}
                                      </td>
                                      {overtimeStats.perDoctor.map((pd: any) => (
                                        <td key={pd.doctor.id} className="text-center px-3 py-2">
                                          {pd.procedureTotals?.[f.key] || 0}
                                        </td>
                                      ))}
                                      <td className="text-center px-3 py-2 font-semibold text-orange-700">{deptTotal}</td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {overtimeStats.perDoctor?.every((pd: any) => pd.sessionCount === 0) && (
                      <Card className="border-orange-100">
                        <CardContent className="py-12 text-center text-gray-500">
                          <BarChart3 className="w-12 h-12 mx-auto mb-3 text-orange-200" />
                          <p className="font-medium">No overtime procedure logs found for this period</p>
                          <p className="text-sm mt-1">Doctors can log their procedures from the Schedule tab after completing sessions.</p>
                        </CardContent>
                      </Card>
                    )}
                  </>
                )}
              </>
            )}
          </>
        )}
      </div>

      {/* ─── Add Session Dialog ────────────────────────────────────── */}
      <Dialog open={showAddSession} onOpenChange={setShowAddSession}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-orange-700">
              <Plus className="w-5 h-5" />
              Open Overtime Session
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Date</Label>
              <Input type="date" value={sessionForm.sessionDate} onChange={e => setSessionForm(f => ({ ...f, sessionDate: e.target.value }))} />
            </div>
            <div>
              <Label>Clinic Name</Label>
              <Input placeholder="e.g. Clinic 4" value={sessionForm.clinicName} onChange={e => setSessionForm(f => ({ ...f, clinicName: e.target.value }))} />
            </div>
            <div>
              <Label>Assign Doctor</Label>
              <Select value={sessionForm.doctorId} onValueChange={v => setSessionForm(f => ({ ...f, doctorId: v }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a doctor..." />
                </SelectTrigger>
                <SelectContent>
                  {doctors.map((d: any) => (
                    <SelectItem key={d.id} value={String(d.id)}>Dr. {d.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Notes (optional)</Label>
              <Textarea placeholder="Any notes for this session..." value={sessionForm.notes} onChange={e => setSessionForm(f => ({ ...f, notes: e.target.value }))} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddSession(false)}>Cancel</Button>
            <Button onClick={submitSession} disabled={!sessionForm.clinicName || createSession.isPending} className="bg-orange-600 hover:bg-orange-700 text-white">
              {createSession.isPending ? "Creating..." : "Create Session"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ─── Slot Entry Dialog ─────────────────────────────────────── */}
      <Dialog open={!!slotDialog} onOpenChange={open => !open && setSlotDialog(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-orange-700">
              <Edit2 className="w-5 h-5" />
              {slotDialog?.existing?.patientName ? "Edit Patient" : "Add Patient"}
              <Badge variant="outline" className="ml-1 border-orange-200 text-orange-600 text-xs">
                {TIME_SLOTS.find(ts => ts.key === slotDialog?.timeSlot)?.label}
              </Badge>
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Patient Name</Label>
              <Input placeholder="Full name" value={slotForm.patientName} onChange={e => setSlotForm(f => ({ ...f, patientName: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Civil ID</Label>
                <Input placeholder="Civil ID" value={slotForm.civilId} onChange={e => setSlotForm(f => ({ ...f, civilId: e.target.value }))} />
              </div>
              <div>
                <Label>Phone</Label>
                <Input placeholder="Phone number" value={slotForm.phone} onChange={e => setSlotForm(f => ({ ...f, phone: e.target.value }))} />
              </div>
            </div>
            <div>
              <Label>Procedure</Label>
              <Input placeholder="e.g. Crown prep, Composite filling..." value={slotForm.procedure} onChange={e => setSlotForm(f => ({ ...f, procedure: e.target.value }))} />
            </div>
            <div>
              <Label>Notes (optional)</Label>
              <Textarea placeholder="Any additional notes..." value={slotForm.notes} onChange={e => setSlotForm(f => ({ ...f, notes: e.target.value }))} rows={2} />
            </div>
          </div>
          <DialogFooter className="flex justify-between items-center">
            {slotDialog?.existing && (
              <Button variant="ghost" className="text-red-500 hover:bg-red-50 mr-auto"
                onClick={() => { setDeleteSlotId(slotDialog.existing!.id); setSlotDialog(null); }}>
                <Trash2 className="w-4 h-4 mr-1" />
                Clear slot
              </Button>
            )}
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setSlotDialog(null)}>Cancel</Button>
              <Button onClick={submitSlot} disabled={saveSlot.isPending} className="bg-orange-600 hover:bg-orange-700 text-white">
                {saveSlot.isPending ? "Saving..." : "Save"}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ─── Per-Patient Procedure Log Dialog ─────────────────────── */}
      <Dialog open={!!slotProcLogDialog} onOpenChange={open => !open && setSlotProcLogDialog(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-orange-700">
              <ClipboardCheck className="w-5 h-5" />
              Log Patient Procedures
              {slotProcLogDialog && (
                <span className="text-sm font-normal text-gray-500 ml-2">
                  — {slotProcLogDialog.entry.patientName || "Patient"} · {slotProcLogDialog.session.clinicName} · {format(new Date(slotProcLogDialog.session.sessionDate + "T00:00:00"), "MMM d, yyyy")}
                </span>
              )}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-500 -mt-2">
            Enter the count for each dental procedure performed for this patient.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 py-2">
            {SLOT_PROC_FIELDS.map(({ key, label, icon }) => (
              <div key={key} className="space-y-1">
                <Label className="text-sm font-medium flex items-center gap-2">
                  <span>{icon}</span>
                  {label}
                </Label>
                <Input
                  type="number"
                  min="0"
                  max="999"
                  value={slotProcLogForm[key] ?? 0}
                  onChange={e => setSlotProcLogForm(f => ({ ...f, [key]: Math.max(0, parseInt(e.target.value) || 0) }))}
                  className="w-full"
                />
              </div>
            ))}
          </div>
          <DialogFooter className="pt-2 border-t">
            <Button variant="outline" onClick={() => setSlotProcLogDialog(null)}>Cancel</Button>
            <Button
              onClick={submitSlotProcLog}
              disabled={saveSlotProcLog.isPending}
              className="bg-orange-600 hover:bg-orange-700 text-white"
            >
              <ClipboardCheck className="w-4 h-4 mr-1.5" />
              {saveSlotProcLog.isPending ? "Saving..." : "Save Procedures"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ─── Session Procedure Log Dialog ──────────────────────────── */}
      <Dialog open={!!procLogDialog} onOpenChange={open => !open && setProcLogDialog(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-orange-700">
              <ScrollText className="w-5 h-5" />
              Log Session Procedures
              {procLogDialog && (
                <span className="text-sm font-normal text-gray-500 ml-2">
                  — {procLogDialog.session.clinicName} · {format(new Date(procLogDialog.session.sessionDate + "T00:00:00"), "MMM d, yyyy")}
                </span>
              )}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-500 -mt-2">
            Enter the count for each dental procedure performed during this overtime session. This will appear in the Overtime Stats.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 py-2">
            {PROCEDURE_FIELDS.map(({ key, label, icon }) => (
              <div key={key} className="space-y-1">
                <Label className="text-sm font-medium flex items-center gap-2">
                  <span>{icon}</span>
                  {label}
                </Label>
                <Input
                  type="number"
                  min="0"
                  max="999"
                  value={procLogForm[key] ?? 0}
                  onChange={e => setProcLogForm(f => ({ ...f, [key]: Math.max(0, parseInt(e.target.value) || 0) }))}
                  className="w-full"
                />
              </div>
            ))}
          </div>
          <DialogFooter className="pt-2 border-t">
            <Button variant="outline" onClick={() => setProcLogDialog(null)}>Cancel</Button>
            <Button
              onClick={submitSessionProcLog}
              disabled={saveSessionProcLog.isPending}
              className="bg-orange-600 hover:bg-orange-700 text-white"
            >
              <ScrollText className="w-4 h-4 mr-1.5" />
              {saveSessionProcLog.isPending ? "Saving..." : "Save Procedures"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ─── Delete Session Confirm ─────────────────────────────────── */}
      <AlertDialog open={!!deleteSessionId} onOpenChange={open => !open && setDeleteSessionId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this overtime session?</AlertDialogTitle>
            <AlertDialogDescription>This will also remove all patient entries in its time slots. This action cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => deleteSessionId && deleteSession.mutate(deleteSessionId)}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ─── Delete Slot Confirm ────────────────────────────────────── */}
      <AlertDialog open={!!deleteSlotId} onOpenChange={open => !open && setDeleteSlotId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear this patient slot?</AlertDialogTitle>
            <AlertDialogDescription>The patient's information will be removed from this time slot.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => deleteSlotId && deleteSlot.mutate(deleteSlotId)}>
              Clear
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
