import { useState, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format, addWeeks, subWeeks, startOfWeek, addDays, isToday } from "date-fns";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import {
  ChevronLeft, ChevronRight, PhoneCall, LogOut, CalendarDays,
  Plus, Trash2, Lock, Unlock, Pencil, ArrowLeft, RefreshCw,
} from "lucide-react";
import { Link } from "wouter";

// ── Constants ────────────────────────────────────────────────────────────────
const SLOT_START = "08:00";
const SLOT_END   = "14:00";
const SLOT_STEP  = 10; // minutes

const WEEK_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"];
const WEEK_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu"];

// ── Time helpers ─────────────────────────────────────────────────────────────
function parseMin(t: string) { const [h, m] = t.split(":").map(Number); return h * 60 + m; }
function toHHMM(mins: number) { return `${String(Math.floor(mins / 60)).padStart(2, "0")}:${String(mins % 60).padStart(2, "0")}`; }
function fmt12(t: string) {
  const m = parseMin(t); const h = Math.floor(m / 60); const mn = m % 60;
  return `${h % 12 || 12}:${String(mn).padStart(2, "0")} ${h >= 12 ? "PM" : "AM"}`;
}
function generateSlots(): string[] {
  const slots: string[] = [];
  let cur = parseMin(SLOT_START);
  const end = parseMin(SLOT_END);
  while (cur < end) { slots.push(toHHMM(cur)); cur += SLOT_STEP; }
  return slots;
}
const ALL_SLOTS = generateSlots();

// ── Derive week's Sunday→Thursday dates from a reference date ────────────────
function getWeekDates(ref: Date): Date[] {
  const sun = startOfWeek(ref, { weekStartsOn: 0 });
  return WEEK_DAYS.map((_, i) => addDays(sun, i));
}

// ── Types ────────────────────────────────────────────────────────────────────
interface ExamSlot {
  id: number; departmentId: number; appointmentDate: string; slotTime: string;
  status: "booked" | "blocked";
  patientName?: string; patientPhone?: string; patientFileId?: string;
  doctorName?: string; notes?: string; blockReason?: string;
}

interface CallCenterUser { departmentId: number; departmentName: string; code: string }

// ── Helpers ──────────────────────────────────────────────────────────────────
function getCallCenterUser(): CallCenterUser | null {
  try { return JSON.parse(localStorage.getItem("callCenterUser") || "null"); } catch { return null; }
}
function getDoctorUser(): any | null {
  try { return JSON.parse(localStorage.getItem("doctorUser") || "null"); } catch { return null; }
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function ExamSchedule() {
  const { toast } = useToast();
  const qc = useQueryClient();

  const ccUser = getCallCenterUser();
  const doctorUser = getDoctorUser();
  const isCallCenter = !!ccUser;

  // Department to show — from CC user, or passed via URL param, or doctor's dept
  const urlParams = new URLSearchParams(window.location.search);
  const urlDeptId = urlParams.get("dept");
  const [selectedDeptId, setSelectedDeptId] = useState<number | null>(
    ccUser?.departmentId ?? (urlDeptId ? parseInt(urlDeptId) : null) ?? doctorUser?.departmentId ?? null
  );
  const [selectedDeptName, setSelectedDeptName] = useState<string>(
    ccUser?.departmentName ?? urlParams.get("deptName") ?? ""
  );

  const [weekRef, setWeekRef] = useState(new Date());
  const weekDates = getWeekDates(weekRef);
  const startDate = format(weekDates[0], "yyyy-MM-dd");
  const endDate   = format(weekDates[4], "yyyy-MM-dd");

  // Dialog state
  type DialogMode = "add" | "edit" | "block" | "view-block" | "bulk-block" | null;
  const [dialog, setDialog] = useState<{
    mode: DialogMode;
    slot?: ExamSlot;
    date?: string;
    time?: string;
  } | null>(null);

  const [form, setForm] = useState({
    patientName: "", patientPhone: "", patientFileId: "", doctorName: "", notes: "",
    blockReason: "", blockStartTime: "", blockEndTime: "",
  });

  // Fetch departments for selection when no dept is set
  const { data: departments = [] } = useQuery<any[]>({
    queryKey: ["/api/departments/public-list"],
    queryFn: () => fetch("/api/departments/public-list").then(r => r.json()),
    enabled: !selectedDeptId,
  });

  // Fetch exam schedule slots
  const { data: slots = [], isLoading, refetch } = useQuery<ExamSlot[]>({
    queryKey: ["/api/exam-schedule", selectedDeptId, startDate, endDate],
    queryFn: async () => {
      const res = await fetch(`/api/exam-schedule?departmentId=${selectedDeptId}&startDate=${startDate}&endDate=${endDate}`);
      if (!res.ok) throw new Error("Failed");
      return res.json();
    },
    enabled: !!selectedDeptId,
    refetchInterval: 30000,
  });

  // Build lookup: "YYYY-MM-DD|HH:MM" → ExamSlot
  const slotMap = useMemo(() => {
    const m: Record<string, ExamSlot> = {};
    slots.forEach(s => { m[`${s.appointmentDate}|${s.slotTime}`] = s; });
    return m;
  }, [slots]);

  const createSlot = useMutation({
    mutationFn: async (data: any) => {
      const res = await fetch("/api/exam-schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...data, departmentId: selectedDeptId, callCenterCode: ccUser?.code }),
      });
      if (!res.ok) throw new Error((await res.json()).message);
      return res.json();
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["/api/exam-schedule", selectedDeptId] }); setDialog(null); toast({ title: "Saved" }); },
    onError: (e: any) => toast({ title: e.message || "Failed", variant: "destructive" }),
  });

  const updateSlot = useMutation({
    mutationFn: async ({ id, ...data }: any) => {
      const res = await fetch(`/api/exam-schedule/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...data, departmentId: selectedDeptId, callCenterCode: ccUser?.code }),
      });
      if (!res.ok) throw new Error((await res.json()).message);
      return res.json();
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["/api/exam-schedule", selectedDeptId] }); setDialog(null); toast({ title: "Updated" }); },
    onError: (e: any) => toast({ title: e.message || "Failed", variant: "destructive" }),
  });

  const deleteSlot = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/exam-schedule/${id}?departmentId=${selectedDeptId}&callCenterCode=${ccUser?.code}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete");
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["/api/exam-schedule", selectedDeptId] }); setDialog(null); toast({ title: "Deleted" }); },
    onError: () => toast({ title: "Failed to delete", variant: "destructive" }),
  });

  const handleCellClick = (date: string, time: string) => {
    if (!isCallCenter) return;
    const key = `${date}|${time}`;
    const existing = slotMap[key];
    if (!existing) {
      setForm({ patientName: "", patientPhone: "", patientFileId: "", doctorName: "", notes: "", blockReason: "", blockStartTime: time, blockEndTime: "" });
      setDialog({ mode: "add", date, time });
    } else if (existing.status === "booked") {
      setForm({ patientName: existing.patientName || "", patientPhone: existing.patientPhone || "", patientFileId: existing.patientFileId || "", doctorName: existing.doctorName || "", notes: existing.notes || "", blockReason: "", blockStartTime: "", blockEndTime: "" });
      setDialog({ mode: "edit", slot: existing, date, time });
    } else {
      setDialog({ mode: "view-block", slot: existing, date, time });
    }
  };

  const handleSaveAppointment = () => {
    if (!form.patientName.trim() || !form.patientPhone.trim()) {
      toast({ title: "Patient name and phone are required", variant: "destructive" }); return;
    }
    if (dialog?.mode === "add") {
      createSlot.mutate({ appointmentDate: dialog.date, slotTime: dialog.time, status: "booked", patientName: form.patientName.trim(), patientPhone: form.patientPhone.trim(), patientFileId: form.patientFileId.trim() || null, doctorName: form.doctorName.trim() || null, notes: form.notes.trim() || null });
    } else if (dialog?.mode === "edit" && dialog.slot) {
      updateSlot.mutate({ id: dialog.slot.id, status: "booked", patientName: form.patientName.trim(), patientPhone: form.patientPhone.trim(), patientFileId: form.patientFileId.trim() || null, doctorName: form.doctorName.trim() || null, notes: form.notes.trim() || null });
    }
  };

  const handleBlockSlot = () => {
    if (dialog?.mode === "block" && dialog.date && dialog.time) {
      createSlot.mutate({ appointmentDate: dialog.date, slotTime: dialog.time, status: "blocked", blockReason: form.blockReason.trim() || null });
    }
  };

  const handleBulkBlock = () => {
    if (!dialog?.date || !form.blockStartTime || !form.blockEndTime) {
      toast({ title: "Please fill start and end time", variant: "destructive" }); return;
    }
    const start = parseMin(form.blockStartTime);
    const end   = parseMin(form.blockEndTime);
    if (end <= start) { toast({ title: "End time must be after start time", variant: "destructive" }); return; }
    const timesToBlock: string[] = [];
    ALL_SLOTS.forEach(s => { const m = parseMin(s); if (m >= start && m < end) timesToBlock.push(s); });
    // Block all that are currently empty
    timesToBlock.forEach(t => {
      const key = `${dialog.date}|${t}`;
      if (!slotMap[key]) {
        createSlot.mutate({ appointmentDate: dialog.date, slotTime: t, status: "blocked", blockReason: form.blockReason.trim() || null });
      }
    });
    setDialog(null);
    toast({ title: `Blocking ${timesToBlock.length} slots...` });
  };

  const handleLogout = () => {
    localStorage.removeItem("callCenterUser");
    window.location.href = "/callcenter-login";
  };

  // Summary
  const booked  = slots.filter(s => s.status === "booked").length;
  const blocked = slots.filter(s => s.status === "blocked").length;
  const total   = ALL_SLOTS.length * 5; // 5 weekdays
  const free    = total - booked - blocked;

  if (!selectedDeptId) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-50 to-white flex items-center justify-center p-4">
        <div className="w-full max-w-sm space-y-4">
          <h2 className="text-xl font-bold text-center text-violet-800">Select Department</h2>
          <Select onValueChange={v => { const d = departments.find((x: any) => x.id === parseInt(v)); setSelectedDeptId(parseInt(v)); setSelectedDeptName(d?.name || ""); }}>
            <SelectTrigger><SelectValue placeholder="Choose department..." /></SelectTrigger>
            <SelectContent>
              {departments.map((d: any) => <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* ── Header ── */}
      <div className="bg-gradient-to-r from-violet-700 to-purple-700 text-white px-4 py-3 shadow-lg flex-shrink-0">
        <div className="max-w-full mx-auto">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {!isCallCenter && (
                <Button size="sm" variant="ghost" className="text-white hover:bg-white/20 -ml-1" onClick={() => history.back()}>
                  <ArrowLeft className="w-4 h-4 mr-1" /> Back
                </Button>
              )}
              <div className="p-1.5 bg-white/20 rounded-lg"><PhoneCall className="w-5 h-5" /></div>
              <div>
                <h1 className="text-lg font-bold leading-tight">Examination Schedule</h1>
                <p className="text-violet-200 text-xs">{selectedDeptName || `Department #${selectedDeptId}`}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="ghost" className="text-white hover:bg-white/20" onClick={() => refetch()}>
                <RefreshCw className="w-3.5 h-3.5" />
              </Button>
              {isCallCenter && (
                <Button size="sm" variant="ghost" className="text-white hover:bg-white/20" onClick={handleLogout}>
                  <LogOut className="w-3.5 h-3.5 mr-1" /> Logout
                </Button>
              )}
            </div>
          </div>

          {/* Week navigation */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              <Button size="sm" variant="ghost" className="text-white hover:bg-white/20 h-7 w-7 p-0"
                onClick={() => setWeekRef(subWeeks(weekRef, 1))}><ChevronLeft className="w-4 h-4" /></Button>
              <div className="flex items-center gap-1.5 bg-white/10 rounded-lg px-2.5 py-1 text-sm font-medium">
                <CalendarDays className="w-3.5 h-3.5 text-violet-200" />
                <span>Week of {format(weekDates[0], "MMM d")} – {format(weekDates[4], "MMM d, yyyy")}</span>
              </div>
              <Button size="sm" variant="ghost" className="text-white hover:bg-white/20 h-7 w-7 p-0"
                onClick={() => setWeekRef(addWeeks(weekRef, 1))}><ChevronRight className="w-4 h-4" /></Button>
              <Button size="sm" variant="ghost" className="text-white hover:bg-white/20 text-xs px-2 h-7"
                onClick={() => setWeekRef(new Date())}>Today</Button>
            </div>
            <div className="flex items-center gap-3 text-xs text-violet-200">
              <span><strong className="text-white">{booked}</strong> booked</span>
              <span><strong className="text-green-300">{free}</strong> free</span>
              {blocked > 0 && <span><strong className="text-red-300">{blocked}</strong> blocked</span>}
            </div>
          </div>
        </div>
      </div>

      {/* ── Calendar Grid ── */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-48 text-gray-400">Loading schedule...</div>
        ) : (
          <div className="min-w-[700px]">
            <table className="w-full border-collapse text-xs">
              <thead className="sticky top-0 z-20 bg-white shadow-sm">
                <tr>
                  <th className="border-b border-r border-gray-200 bg-white w-16 min-w-[64px] py-2 text-gray-500 font-medium text-center">Time</th>
                  {weekDates.map((d, i) => (
                    <th key={i} className={`border-b border-r border-gray-200 py-2 px-1 font-medium min-w-[130px] ${isToday(d) ? "bg-violet-50 text-violet-700" : "bg-white text-gray-700"}`}>
                      <div className="font-semibold">{WEEK_SHORT[i]}</div>
                      <div className={`text-[11px] ${isToday(d) ? "text-violet-500" : "text-gray-400"}`}>{format(d, "MMM d")}</div>
                      {isCallCenter && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-[10px] h-5 px-1 text-orange-600 hover:bg-orange-50 mt-0.5 w-full"
                          onClick={() => { setForm(f => ({ ...f, blockStartTime: "08:00", blockEndTime: "14:00", blockReason: "" })); setDialog({ mode: "bulk-block", date: format(d, "yyyy-MM-dd") }); }}
                        >
                          <Lock className="w-2.5 h-2.5 mr-0.5" /> Block range
                        </Button>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ALL_SLOTS.map((slotTime, si) => (
                  <tr key={slotTime} className={si % 6 === 0 ? "border-t-2 border-violet-100" : ""}>
                    {/* Time label */}
                    <td className="border-r border-b border-gray-100 bg-gray-50 text-center text-[10px] font-mono text-gray-500 py-0 w-16 sticky left-0">
                      {si % 3 === 0 ? fmt12(slotTime) : ""}
                    </td>
                    {/* Day cells */}
                    {weekDates.map((d, di) => {
                      const dateStr = format(d, "yyyy-MM-dd");
                      const key     = `${dateStr}|${slotTime}`;
                      const slot    = slotMap[key];
                      const isEmpty = !slot;
                      const isBooked  = slot?.status === "booked";
                      const isBlocked = slot?.status === "blocked";

                      return (
                        <td
                          key={di}
                          onClick={() => handleCellClick(dateStr, slotTime)}
                          className={`border-r border-b border-gray-100 h-7 px-1 transition-colors ${
                            isBlocked
                              ? "bg-red-50 text-red-700 cursor-pointer hover:bg-red-100"
                              : isBooked
                              ? "bg-blue-50 hover:bg-blue-100 cursor-pointer"
                              : isCallCenter
                              ? "hover:bg-violet-50 cursor-pointer group"
                              : "bg-white"
                          } ${isToday(d) ? "bg-opacity-80" : ""}`}
                        >
                          {isBlocked && (
                            <div className="flex items-center gap-0.5 text-[10px] text-red-600 font-medium truncate">
                              <Lock className="w-2.5 h-2.5 shrink-0" />
                              <span className="truncate">{slot.blockReason || "Blocked"}</span>
                            </div>
                          )}
                          {isBooked && (
                            <div className="leading-tight">
                              <div className="font-semibold text-blue-800 text-[10px] truncate">{slot.patientName}</div>
                              {slot.doctorName && <div className="text-[9px] text-blue-500 truncate">{slot.doctorName}</div>}
                              {slot.patientPhone && <div className="text-[9px] text-gray-500 truncate">{slot.patientPhone}</div>}
                            </div>
                          )}
                          {isEmpty && isCallCenter && (
                            <div className="opacity-0 group-hover:opacity-100 flex items-center justify-center h-full">
                              <Plus className="w-3 h-3 text-violet-400" />
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Legend ── */}
      <div className="flex-shrink-0 bg-white border-t border-gray-100 px-4 py-2 flex flex-wrap gap-4 text-[11px] text-gray-500">
        <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-blue-100 border border-blue-300" /> Booked appointment</span>
        <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-red-100 border border-red-300" /> Blocked</span>
        <span className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-white border border-gray-200" /> Available</span>
        {isCallCenter && <span className="text-violet-600 font-medium">• Click any cell to add patient or block slot</span>}
      </div>

      {/* ── Add / Edit Patient Dialog ── */}
      <Dialog open={dialog?.mode === "add" || dialog?.mode === "edit"} onOpenChange={open => !open && setDialog(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-violet-700">
              {dialog?.mode === "edit" ? <Pencil className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
              {dialog?.mode === "edit" ? "Edit Appointment" : "Add Patient"}
            </DialogTitle>
          </DialogHeader>
          {dialog?.date && dialog?.time && (
            <div className="bg-violet-50 border border-violet-100 rounded-lg px-3 py-2 text-sm -mt-1 mb-1">
              <span className="font-semibold text-violet-800">{format(new Date(dialog.date + "T12:00"), "EEEE, MMMM d yyyy")}</span>
              <span className="text-violet-600 ml-2">@ {fmt12(dialog.time)}</span>
            </div>
          )}
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Patient Name <span className="text-red-500">*</span></Label>
                <Input placeholder="Full name" value={form.patientName} onChange={e => setForm(f => ({ ...f, patientName: e.target.value }))} autoFocus />
              </div>
              <div>
                <Label>Phone <span className="text-red-500">*</span></Label>
                <Input placeholder="Phone number" value={form.patientPhone} onChange={e => setForm(f => ({ ...f, patientPhone: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>File / Civil ID</Label>
                <Input placeholder="File or civil ID" value={form.patientFileId} onChange={e => setForm(f => ({ ...f, patientFileId: e.target.value }))} />
              </div>
              <div>
                <Label>Doctor Name</Label>
                <Input placeholder="Assigned doctor" value={form.doctorName} onChange={e => setForm(f => ({ ...f, doctorName: e.target.value }))} />
              </div>
            </div>
            <div>
              <Label>Notes</Label>
              <Textarea placeholder="Any notes..." value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} />
            </div>
          </div>
          <DialogFooter className="mt-2 flex items-center justify-between">
            <div>
              {dialog?.mode === "edit" && dialog.slot && (
                <Button variant="destructive" size="sm" onClick={() => deleteSlot.mutate(dialog.slot!.id)} disabled={deleteSlot.isPending}>
                  <Trash2 className="w-3.5 h-3.5 mr-1" />Delete
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setDialog(null)}>Cancel</Button>
              <Button
                onClick={handleSaveAppointment}
                disabled={createSlot.isPending || updateSlot.isPending || !form.patientName.trim() || !form.patientPhone.trim()}
                className="bg-violet-600 hover:bg-violet-700 text-white"
              >
                {createSlot.isPending || updateSlot.isPending ? "Saving..." : dialog?.mode === "edit" ? "Update" : "Add Patient"}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Block Single Slot Dialog ── */}
      <Dialog open={dialog?.mode === "block"} onOpenChange={open => !open && setDialog(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-orange-700"><Lock className="w-4 h-4" /> Block Slot</DialogTitle>
          </DialogHeader>
          {dialog?.date && dialog?.time && (
            <p className="text-sm text-gray-600 -mt-1">
              {format(new Date(dialog.date + "T12:00"), "EEE, MMM d")} @ {fmt12(dialog.time)}
            </p>
          )}
          <div>
            <Label>Reason (optional)</Label>
            <Input placeholder="e.g. Staff meeting, break..." value={form.blockReason} onChange={e => setForm(f => ({ ...f, blockReason: e.target.value }))} autoFocus />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)}>Cancel</Button>
            <Button onClick={handleBlockSlot} disabled={createSlot.isPending} className="bg-orange-600 hover:bg-orange-700 text-white">
              Block Slot
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── View Blocked Slot Dialog ── */}
      <Dialog open={dialog?.mode === "view-block"} onOpenChange={open => !open && setDialog(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-700"><Lock className="w-4 h-4" /> Blocked Slot</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            {dialog?.slot?.blockReason || "No reason given"}
          </p>
          <DialogFooter className="flex justify-between items-center">
            <Button variant="destructive" size="sm" onClick={() => dialog?.slot && deleteSlot.mutate(dialog.slot.id)} disabled={deleteSlot.isPending}>
              <Unlock className="w-3.5 h-3.5 mr-1" /> Unblock
            </Button>
            <Button variant="outline" onClick={() => setDialog(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Bulk Block Range Dialog ── */}
      <Dialog open={dialog?.mode === "bulk-block"} onOpenChange={open => !open && setDialog(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-orange-700"><Lock className="w-4 h-4" /> Block Time Range</DialogTitle>
          </DialogHeader>
          {dialog?.date && (
            <p className="text-sm font-medium text-gray-700 -mt-1">{format(new Date(dialog.date + "T12:00"), "EEEE, MMMM d yyyy")}</p>
          )}
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>From</Label>
                <Input type="time" value={form.blockStartTime} onChange={e => setForm(f => ({ ...f, blockStartTime: e.target.value }))} />
              </div>
              <div>
                <Label>To</Label>
                <Input type="time" value={form.blockEndTime} onChange={e => setForm(f => ({ ...f, blockEndTime: e.target.value }))} />
              </div>
            </div>
            <div>
              <Label>Reason (optional)</Label>
              <Input placeholder="e.g. Staff training..." value={form.blockReason} onChange={e => setForm(f => ({ ...f, blockReason: e.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)}>Cancel</Button>
            <Button onClick={handleBulkBlock} disabled={createSlot.isPending} className="bg-orange-600 hover:bg-orange-700 text-white">
              <Lock className="w-3.5 h-3.5 mr-1" /> Block Range
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
