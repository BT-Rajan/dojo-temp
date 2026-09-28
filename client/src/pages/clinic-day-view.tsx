import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format, addDays, subDays, isToday } from "date-fns";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/hooks/useAuth";
import { apiRequest } from "@/lib/queryClient";
import {
  ChevronLeft, ChevronRight, Building2, User, Clock, Plus,
  CheckCircle2, ArrowLeft, RefreshCw, Timer,
} from "lucide-react";
import { Link } from "wouter";

// ─── Time helpers ────────────────────────────────────────────────────────────

function parseTime(t: string): number {
  const parts = t.split(":").map(Number);
  return parts[0] * 60 + (parts[1] || 0);
}

function minsToHHMM(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function formatTime12(t: string): string {
  const mins = parseTime(t);
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
}

function durationLabel(mins: number): string {
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}min` : `${h}h`;
}

// ─── Types ───────────────────────────────────────────────────────────────────

interface Appointment {
  id: number;
  startTime: string;
  endTime: string;
  status: string;
  procedure?: string;
  reasonForVisit?: string;
  patient: { firstName: string; lastName: string; phone: string };
}

interface ClinicEntry {
  assignmentId: number;
  clinic: { id: number; name: string; startTime: string; endTime: string };
  doctor: { id: number; name: string; title: string };
  isOnLeave: boolean;
  appointments: Appointment[];
}

type TimelineBlock =
  | { kind: "booked"; appt: Appointment; startMin: number; endMin: number }
  | { kind: "free"; startMin: number; endMin: number }
  | { kind: "inactive"; appt: Appointment; startMin: number; endMin: number };

const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string; border: string }> = {
  scheduled: { label: "Scheduled", bg: "bg-blue-50",   text: "text-blue-800",   border: "border-blue-200" },
  confirmed:  { label: "Confirmed", bg: "bg-indigo-50", text: "text-indigo-800", border: "border-indigo-200" },
  arrived:    { label: "Arrived",   bg: "bg-purple-50", text: "text-purple-800", border: "border-purple-200" },
  completed:  { label: "Completed", bg: "bg-green-50",  text: "text-green-700",  border: "border-green-200" },
  cancelled:  { label: "Cancelled", bg: "bg-gray-50",   text: "text-gray-400",   border: "border-gray-200" },
  missed:     { label: "Missed",    bg: "bg-red-50",    text: "text-red-400",    border: "border-red-200" },
};

const DURATION_OPTIONS = [15, 20, 30, 45, 60, 90, 120];

// ─── Build a timeline for one clinic ─────────────────────────────────────────

function buildTimeline(
  clinicStart: string,
  clinicEnd: string,
  appointments: Appointment[],
): TimelineBlock[] {
  const clinicStartMin = parseTime(clinicStart);
  const clinicEndMin   = parseTime(clinicEnd);

  // Active = occupies the timeslot; inactive = cancelled/missed (shown but don't block time)
  const active   = appointments.filter(a => a.status !== "cancelled" && a.status !== "missed");
  const inactive = appointments.filter(a => a.status === "cancelled" || a.status === "missed");

  // Sort active appointments by start time
  const sorted = [...active].sort((a, b) => parseTime(a.startTime) - parseTime(b.startTime));

  const blocks: TimelineBlock[] = [];
  let cursor = clinicStartMin;

  for (const appt of sorted) {
    const apptStart = parseTime(appt.startTime);
    const rawEnd    = appt.endTime ? parseTime(appt.endTime) : apptStart + 30;
    const apptEnd   = rawEnd > apptStart ? rawEnd : apptStart + 30;

    // Clamp to clinic hours
    const clampedStart = Math.max(apptStart, clinicStartMin);
    const clampedEnd   = Math.min(apptEnd,   clinicEndMin);

    // Free gap before this appointment
    if (clampedStart > cursor) {
      blocks.push({ kind: "free", startMin: cursor, endMin: clampedStart });
    }

    if (clampedEnd > clampedStart) {
      blocks.push({ kind: "booked", appt, startMin: clampedStart, endMin: clampedEnd });
    }
    cursor = Math.max(cursor, clampedEnd);
  }

  // Free gap at end of clinic
  if (cursor < clinicEndMin) {
    blocks.push({ kind: "free", startMin: cursor, endMin: clinicEndMin });
  }

  // Scatter inactive entries into their time positions (displayed but non-blocking)
  for (const appt of inactive) {
    const s = parseTime(appt.startTime);
    const rawE = appt.endTime ? parseTime(appt.endTime) : s + 30;
    const e = rawE > s ? rawE : s + 30;
    blocks.push({ kind: "inactive", appt, startMin: s, endMin: e });
  }

  // Sort final timeline by startMin
  blocks.sort((a, b) => a.startMin - b.startMin);

  return blocks;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function ClinicDayView() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const { isAuthenticated } = useAuth();

  const centerId = localStorage.getItem("selectedCenterId") || "";
  const [selectedDeptId, setSelectedDeptId] = useState<string>("");
  const [selectedDate, setSelectedDate] = useState(format(new Date(), "yyyy-MM-dd"));

  // Add-patient dialog state
  const [addDialog, setAddDialog] = useState<{
    clinic: ClinicEntry["clinic"];
    doctor: ClinicEntry["doctor"];
    windowStart: number; // minutes from midnight
    windowEnd: number;
  } | null>(null);
  const [addForm, setAddForm] = useState({
    patientName: "",
    patientPhone: "",
    procedure: "",
    notes: "",
    startTime: "",   // HH:MM
    duration: "30",  // minutes as string
  });

  // Derived end time for display
  const addEndTime = (() => {
    if (!addForm.startTime) return "";
    const s = parseTime(addForm.startTime);
    const d = parseInt(addForm.duration, 10) || 30;
    return minsToHHMM(s + d);
  })();

  const { data: departments = [] } = useQuery<any[]>({
    queryKey: ["/api/user/departments", centerId],
    queryFn: async () => {
      const url = centerId ? `/api/user/departments?centerId=${centerId}` : "/api/user/departments";
      const res = await fetch(url, { credentials: "include" });
      return res.json();
    },
    enabled: isAuthenticated,
  });

  useEffect(() => {
    if (departments.length > 0 && !selectedDeptId) {
      setSelectedDeptId(String(departments[0].id));
    }
  }, [departments, selectedDeptId]);

  const { data: clinicEntries = [], isLoading, refetch } = useQuery<ClinicEntry[]>({
    queryKey: ["/api/department/clinic-day", selectedDeptId, selectedDate],
    queryFn: async () => {
      const res = await fetch(
        `/api/department/${selectedDeptId}/clinic-day?date=${selectedDate}`,
        { credentials: "include" }
      );
      if (!res.ok) throw new Error("Failed to load clinic schedule");
      return res.json();
    },
    enabled: !!selectedDeptId,
    refetchInterval: 30000,
  });

  const addAppointment = useMutation({
    mutationFn: async (data: any) => {
      const res = await apiRequest("/api/appointments", {
        method: "POST",
        body: JSON.stringify(data),
      });
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/department/clinic-day", selectedDeptId, selectedDate] });
      setAddDialog(null);
      toast({ title: "Patient added successfully" });
    },
    onError: () => toast({ title: "Failed to add patient", variant: "destructive" }),
  });

  const handleOpenAddDialog = (
    clinic: ClinicEntry["clinic"],
    doctor: ClinicEntry["doctor"],
    windowStart: number,
    windowEnd: number,
  ) => {
    setAddForm({
      patientName: "",
      patientPhone: "",
      procedure: "",
      notes: "",
      startTime: minsToHHMM(windowStart),
      duration: "30",
    });
    setAddDialog({ clinic, doctor, windowStart, windowEnd });
  };

  const handleSubmitAdd = () => {
    if (!addDialog) return;
    if (!addForm.patientName.trim() || !addForm.patientPhone.trim() || !addForm.procedure.trim()) {
      toast({ title: "Please fill all required fields", variant: "destructive" });
      return;
    }
    const startMin = parseTime(addForm.startTime);
    const dur      = parseInt(addForm.duration, 10) || 30;
    const endMin   = startMin + dur;

    if (startMin < addDialog.windowStart || endMin > addDialog.windowEnd) {
      toast({ title: "The selected time extends outside the free window", variant: "destructive" });
      return;
    }

    addAppointment.mutate({
      doctorId:        addDialog.doctor.id,
      clinicId:        addDialog.clinic.id,
      patientName:     addForm.patientName.trim(),
      patientPhone:    addForm.patientPhone.trim(),
      procedure:       addForm.procedure.trim(),
      notes:           addForm.notes.trim() || undefined,
      appointmentDate: selectedDate,
      startTime:       `${addForm.startTime}:00`,
      endTime:         `${minsToHHMM(endMin)}:00`,
      status:          "scheduled",
      type:            "consultation",
    });
  };

  // Summary stats
  const totalActiveClinics = clinicEntries.filter(c => !c.isOnLeave).length;
  const totalActiveAppts   = clinicEntries.reduce(
    (s, c) => s + c.appointments.filter(a => a.status !== "cancelled" && a.status !== "missed").length, 0
  );
  const totalFreeMin = clinicEntries.reduce((s, ce) => {
    const blocks = buildTimeline(ce.clinic.startTime, ce.clinic.endTime, ce.appointments);
    return s + blocks.filter(b => b.kind === "free").reduce((fs, b) => fs + b.endMin - b.startMin, 0);
  }, 0);
  const completedCount = clinicEntries.reduce(
    (s, c) => s + c.appointments.filter(a => a.status === "completed").length, 0
  );

  const dateObj   = new Date(selectedDate + "T12:00:00");
  const dayName   = format(dateObj, "EEEE");
  const isTodayFlag = isToday(dateObj);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">

      {/* ── Header ── */}
      <div className="bg-gradient-to-r from-blue-700 to-indigo-700 text-white px-6 py-4 shadow-lg">
        <div className="max-w-screen-2xl mx-auto">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <Link href="/dashboard">
                <Button size="sm" variant="ghost" className="text-white hover:bg-white/20 -ml-1">
                  <ArrowLeft className="w-4 h-4 mr-1" /> Back
                </Button>
              </Link>
              <div className="w-px h-6 bg-white/30" />
              <Building2 className="w-6 h-6 text-blue-200" />
              <div>
                <h1 className="text-xl font-bold leading-tight">Clinic Day Schedule</h1>
                <p className="text-blue-200 text-sm">Live daily view — actual appointment times, free windows, and patient slots</p>
              </div>
            </div>
            <Button size="sm" variant="ghost" className="text-white hover:bg-white/20" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-1" /> Refresh
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {departments.length > 1 && (
              <Select value={selectedDeptId} onValueChange={setSelectedDeptId}>
                <SelectTrigger className="w-52 bg-white/10 border-white/20 text-white">
                  <SelectValue placeholder="Select department..." />
                </SelectTrigger>
                <SelectContent>
                  {departments.map((d: any) => (
                    <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {/* Date nav */}
            <div className="flex items-center gap-1 ml-auto">
              <Button size="sm" variant="ghost" className="text-white hover:bg-white/20"
                onClick={() => setSelectedDate(format(subDays(dateObj, 1), "yyyy-MM-dd"))}>
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5 border border-white/20">
                <Clock className="w-4 h-4 text-blue-200" />
                <input
                  type="date"
                  value={selectedDate}
                  onChange={e => setSelectedDate(e.target.value)}
                  className="bg-transparent text-white text-sm font-medium outline-none cursor-pointer"
                />
                <span className="text-blue-200 text-sm">{dayName}</span>
                {isTodayFlag && <Badge className="bg-yellow-400 text-yellow-900 text-xs px-1.5 py-0">Today</Badge>}
              </div>
              <Button size="sm" variant="ghost" className="text-white hover:bg-white/20"
                onClick={() => setSelectedDate(format(addDays(dateObj, 1), "yyyy-MM-dd"))}>
                <ChevronRight className="w-4 h-4" />
              </Button>
              {!isTodayFlag && (
                <Button size="sm" variant="ghost" className="text-white hover:bg-white/20 text-xs"
                  onClick={() => setSelectedDate(format(new Date(), "yyyy-MM-dd"))}>
                  Today
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Summary bar ── */}
      {clinicEntries.length > 0 && (
        <div className="bg-white border-b border-blue-100 px-6 py-2.5">
          <div className="max-w-screen-2xl mx-auto flex flex-wrap items-center gap-6 text-sm">
            <span className="text-gray-500 font-medium">{totalActiveClinics} clinics active</span>
            <div className="flex items-center gap-1.5 text-green-700">
              <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
              <span><strong>{durationLabel(totalFreeMin)}</strong> free time total</span>
            </div>
            <div className="flex items-center gap-1.5 text-blue-700">
              <div className="w-2.5 h-2.5 rounded-full bg-blue-400" />
              <span><strong>{totalActiveAppts}</strong> patients booked</span>
            </div>
            <div className="flex items-center gap-1.5 text-gray-600">
              <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
              <span><strong>{completedCount}</strong> completed</span>
            </div>
          </div>
        </div>
      )}

      {/* ── Main grid ── */}
      <div className="max-w-screen-2xl mx-auto px-4 py-6">
        {!selectedDeptId ? (
          <Card className="border-blue-100">
            <CardContent className="py-16 text-center text-gray-500">
              <Building2 className="w-12 h-12 mx-auto mb-3 text-blue-200" />
              <p className="text-lg font-medium">Select a department to view the clinic schedule</p>
            </CardContent>
          </Card>
        ) : isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-72 bg-white rounded-xl border border-blue-100 animate-pulse" />
            ))}
          </div>
        ) : clinicEntries.length === 0 ? (
          <Card className="border-blue-100">
            <CardContent className="py-16 text-center text-gray-500">
              <Clock className="w-14 h-14 mx-auto mb-4 text-blue-200" />
              <p className="text-lg font-semibold text-gray-700">No clinics scheduled for {dayName}</p>
              <p className="text-sm text-gray-400 mt-1">No doctor-clinic assignments exist for this day in this department.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5 items-start">
            {clinicEntries.map(ce => {
              const timeline = buildTimeline(ce.clinic.startTime, ce.clinic.endTime, ce.appointments);
              const clinicDurMin  = parseTime(ce.clinic.endTime) - parseTime(ce.clinic.startTime);
              const bookedMin     = timeline.filter(b => b.kind === "booked").reduce((s, b) => s + b.endMin - b.startMin, 0);
              const fillPct       = clinicDurMin > 0 ? Math.round((bookedMin / clinicDurMin) * 100) : 0;
              const freeMin       = timeline.filter(b => b.kind === "free").reduce((s, b) => s + b.endMin - b.startMin, 0);

              return (
                <Card key={ce.assignmentId}
                  className={`border shadow-sm flex flex-col ${ce.isOnLeave ? "border-amber-200 opacity-75" : "border-blue-100"}`}
                >
                  {/* Card header */}
                  <CardHeader className={`px-4 py-3 rounded-t-xl ${ce.isOnLeave ? "bg-amber-50" : "bg-gradient-to-r from-blue-600 to-indigo-600"}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className={`font-bold text-base leading-tight ${ce.isOnLeave ? "text-amber-900" : "text-white"}`}>
                          {ce.clinic.name}
                        </h3>
                        <div className={`flex items-center gap-1.5 mt-0.5 text-xs ${ce.isOnLeave ? "text-amber-700" : "text-blue-100"}`}>
                          <Clock className="w-3 h-3" />
                          {formatTime12(ce.clinic.startTime)} – {formatTime12(ce.clinic.endTime)}
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
                    <div className={`flex items-center gap-1.5 mt-1.5 text-xs ${ce.isOnLeave ? "text-amber-700" : "text-blue-100"}`}>
                      <User className="w-3 h-3" />
                      <span className={`font-medium ${ce.isOnLeave ? "text-amber-900" : "text-white"}`}>
                        Dr. {ce.doctor.name}
                      </span>
                      <span className="opacity-75">· {ce.doctor.title}</span>
                    </div>
                    {!ce.isOnLeave && (
                      <>
                        <div className="mt-2 h-1.5 bg-blue-800/40 rounded-full overflow-hidden">
                          <div className="h-full bg-white/70 rounded-full transition-all" style={{ width: `${fillPct}%` }} />
                        </div>
                        <div className="mt-1 text-[10px] text-blue-200">
                          {durationLabel(freeMin)} free · {durationLabel(bookedMin)} booked
                        </div>
                      </>
                    )}
                  </CardHeader>

                  {/* Timeline */}
                  <CardContent className="p-2 flex-1">
                    <div className="space-y-1">
                      {timeline.length === 0 ? (
                        <p className="text-xs text-gray-400 text-center py-4">No data for this clinic</p>
                      ) : (
                        timeline.map((block, idx) => {
                          const durMin = block.endMin - block.startMin;

                          if (block.kind === "free") {
                            const canAdd = !ce.isOnLeave;
                            return (
                              <div
                                key={idx}
                                onClick={() => canAdd && handleOpenAddDialog(ce.clinic, ce.doctor, block.startMin, block.endMin)}
                                className={`flex items-stretch rounded-lg border text-xs overflow-hidden transition-all ${
                                  canAdd
                                    ? "border-green-200 bg-green-50 hover:bg-green-100 hover:border-green-300 cursor-pointer group"
                                    : "border-gray-100 bg-gray-50"
                                }`}
                              >
                                <div className="px-2 py-2.5 border-r border-green-200 flex flex-col justify-center min-w-[72px] font-mono text-[10px] text-green-700 font-semibold">
                                  <span>{formatTime12(minsToHHMM(block.startMin))}</span>
                                  <span className="opacity-60">–{formatTime12(minsToHHMM(block.endMin))}</span>
                                </div>
                                <div className="flex-1 px-2 py-2.5 flex items-center justify-between">
                                  <span className={`font-medium flex items-center gap-1 ${canAdd ? "text-green-600 group-hover:text-green-700" : "text-gray-400"}`}>
                                    {canAdd && <Plus className="w-3 h-3" />}
                                    {canAdd ? `Free — ${durationLabel(durMin)}` : "Unavailable"}
                                  </span>
                                  {canAdd && (
                                    <Badge className="bg-green-100 text-green-700 border border-green-300 text-[10px] px-1.5 py-0 group-hover:bg-green-200">
                                      + Add
                                    </Badge>
                                  )}
                                </div>
                              </div>
                            );
                          }

                          if (block.kind === "booked") {
                            const appt = block.appt;
                            const cfg  = STATUS_CONFIG[appt.status] ?? STATUS_CONFIG.scheduled;
                            return (
                              <div key={idx} className={`flex items-stretch rounded-lg border text-xs overflow-hidden ${cfg.bg} ${cfg.border}`}>
                                <div className={`px-2 py-2.5 border-r flex flex-col justify-center min-w-[72px] font-mono text-[10px] font-semibold ${cfg.text} border-current/20`}>
                                  <span>{formatTime12(minsToHHMM(block.startMin))}</span>
                                  <span className="opacity-60">–{formatTime12(minsToHHMM(block.endMin))}</span>
                                  <span className="opacity-50 font-normal mt-0.5">{durationLabel(durMin)}</span>
                                </div>
                                <div className="flex-1 px-2 py-2.5 flex items-center justify-between min-w-0">
                                  <div className="min-w-0">
                                    <p className={`font-semibold truncate ${cfg.text}`}>
                                      {appt.patient.firstName} {appt.patient.lastName}
                                    </p>
                                    <p className="text-gray-500 text-[11px] truncate">
                                      {appt.procedure || appt.reasonForVisit || "—"}
                                    </p>
                                    {appt.patient.phone && (
                                      <p className="text-gray-400 text-[10px]">{appt.patient.phone}</p>
                                    )}
                                  </div>
                                  <div className="ml-2 shrink-0">
                                    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 border ${cfg.text} border-current/30 whitespace-nowrap`}>
                                      {appt.status === "completed" && <CheckCircle2 className="w-2.5 h-2.5 mr-0.5 inline" />}
                                      {appt.status === "arrived" && <div className="w-1.5 h-1.5 rounded-full bg-purple-500 inline-block mr-0.5" />}
                                      {cfg.label}
                                    </Badge>
                                  </div>
                                </div>
                              </div>
                            );
                          }

                          // inactive (cancelled / missed)
                          if (block.kind === "inactive") {
                            const appt = block.appt;
                            const cfg  = STATUS_CONFIG[appt.status] ?? STATUS_CONFIG.cancelled;
                            return (
                              <div key={idx} className="flex items-stretch rounded-lg border border-dashed border-gray-200 bg-gray-50 text-xs overflow-hidden opacity-60">
                                <div className="px-2 py-1.5 border-r border-gray-200 flex flex-col justify-center min-w-[72px] font-mono text-[10px] font-semibold text-gray-400">
                                  <span>{formatTime12(minsToHHMM(block.startMin))}</span>
                                  <span className="opacity-60">–{formatTime12(minsToHHMM(block.endMin))}</span>
                                </div>
                                <div className="flex-1 px-2 py-1.5 flex items-center justify-between min-w-0">
                                  <p className="text-gray-400 line-through truncate">
                                    {appt.patient.firstName} {appt.patient.lastName}
                                  </p>
                                  <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ml-1 shrink-0 ${cfg.text} border-current/30`}>
                                    {cfg.label}
                                  </Badge>
                                </div>
                              </div>
                            );
                          }

                          return null;
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

      {/* ── Legend ── */}
      {clinicEntries.length > 0 && (
        <div className="max-w-screen-2xl mx-auto px-4 pb-6">
          <div className="flex flex-wrap gap-3 text-xs text-gray-500">
            <span className="font-medium text-gray-700">Legend:</span>
            <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-green-100 border border-green-300" /> Free window</span>
            <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-blue-100 border border-blue-300" /> Scheduled</span>
            <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-purple-100 border border-purple-300" /> Arrived</span>
            <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-green-200 border border-green-400" /> Completed</span>
            <span className="flex items-center gap-1"><div className="w-3 h-3 rounded border border-dashed border-gray-300 bg-gray-50" /> Cancelled / Missed</span>
          </div>
        </div>
      )}

      {/* ── Add Patient Dialog ── */}
      <Dialog open={!!addDialog} onOpenChange={open => !open && setAddDialog(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-blue-700">
              <Plus className="w-5 h-5" />
              Add Patient to Clinic
            </DialogTitle>
          </DialogHeader>

          {addDialog && (
            <div className="bg-blue-50 rounded-lg px-3 py-2 border border-blue-100 text-sm -mt-2 mb-1 space-y-0.5">
              <p className="font-semibold text-blue-900">{addDialog.clinic.name} · Dr. {addDialog.doctor.name}</p>
              <p className="text-blue-500 text-xs">
                Free window: {formatTime12(minsToHHMM(addDialog.windowStart))} – {formatTime12(minsToHHMM(addDialog.windowEnd))}
                &nbsp;({durationLabel(addDialog.windowEnd - addDialog.windowStart)})
              </p>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <Label>Patient Name <span className="text-red-500">*</span></Label>
              <Input
                placeholder="Full name"
                value={addForm.patientName}
                onChange={e => setAddForm(f => ({ ...f, patientName: e.target.value }))}
                autoFocus
              />
            </div>
            <div>
              <Label>Phone Number <span className="text-red-500">*</span></Label>
              <Input
                placeholder="e.g. 99912345"
                value={addForm.patientPhone}
                onChange={e => setAddForm(f => ({ ...f, patientPhone: e.target.value }))}
              />
            </div>
            <div>
              <Label>Procedure / Reason <span className="text-red-500">*</span></Label>
              <Input
                placeholder="e.g. Crown prep, Composite filling..."
                value={addForm.procedure}
                onChange={e => setAddForm(f => ({ ...f, procedure: e.target.value }))}
              />
            </div>

            {/* Time selection */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" /> Start Time <span className="text-red-500">*</span>
                </Label>
                <Input
                  type="time"
                  value={addForm.startTime}
                  min={addDialog ? minsToHHMM(addDialog.windowStart) : undefined}
                  max={addDialog ? minsToHHMM(addDialog.windowEnd - 15) : undefined}
                  onChange={e => setAddForm(f => ({ ...f, startTime: e.target.value }))}
                />
              </div>
              <div>
                <Label className="flex items-center gap-1">
                  <Timer className="w-3.5 h-3.5" /> Duration
                </Label>
                <Select value={addForm.duration} onValueChange={v => setAddForm(f => ({ ...f, duration: v }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DURATION_OPTIONS.map(d => (
                      <SelectItem key={d} value={String(d)}>{durationLabel(d)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* End time display */}
            {addForm.startTime && addEndTime && (
              <div className="bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2 text-sm text-indigo-700">
                Appointment: <strong>{formatTime12(addForm.startTime)}</strong> → <strong>{formatTime12(addEndTime)}</strong>
                {addDialog && parseTime(addEndTime) > addDialog.windowEnd && (
                  <p className="text-red-500 text-xs mt-1">⚠ Exceeds the free window end — reduce duration or start time</p>
                )}
              </div>
            )}

            <div>
              <Label>Notes (optional)</Label>
              <Input
                placeholder="Any additional notes..."
                value={addForm.notes}
                onChange={e => setAddForm(f => ({ ...f, notes: e.target.value }))}
              />
            </div>
          </div>

          <DialogFooter className="mt-2">
            <Button variant="outline" onClick={() => setAddDialog(null)}>Cancel</Button>
            <Button
              onClick={handleSubmitAdd}
              disabled={
                addAppointment.isPending ||
                !addForm.patientName.trim() ||
                !addForm.patientPhone.trim() ||
                !addForm.procedure.trim() ||
                !addForm.startTime ||
                (!!addDialog && parseTime(addEndTime) > addDialog.windowEnd)
              }
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {addAppointment.isPending ? "Adding..." : "Add Patient"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
