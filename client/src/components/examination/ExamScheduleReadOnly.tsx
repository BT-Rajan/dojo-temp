import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { format, addWeeks, subWeeks, startOfWeek, addDays, isToday } from "date-fns";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChevronLeft, ChevronRight, CalendarDays, Lock } from "lucide-react";

// ── Constants ─────────────────────────────────────────────────────────────────
const SLOT_START = "08:00";
const SLOT_END   = "14:00";
const SLOT_STEP  = 10;

const WEEK_DAYS  = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"];
const WEEK_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu"];

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

function getWeekDates(ref: Date): Date[] {
  const sun = startOfWeek(ref, { weekStartsOn: 0 });
  return WEEK_DAYS.map((_, i) => addDays(sun, i));
}

interface ExamSlot {
  id: number;
  departmentId: number;
  appointmentDate: string;
  slotTime: string;
  status: "booked" | "blocked";
  patientName?: string;
  patientPhone?: string;
  patientFileId?: string;
  doctorName?: string;
  notes?: string;
  blockReason?: string;
}

interface Props {
  departmentId: number;
  departmentName?: string;
  initialWeek?: Date;
}

export default function ExamScheduleReadOnly({ departmentId, departmentName, initialWeek }: Props) {
  const [weekRef, setWeekRef] = useState(initialWeek ?? new Date());
  const weekDates = getWeekDates(weekRef);
  const startDate = format(weekDates[0], "yyyy-MM-dd");
  const endDate   = format(weekDates[4], "yyyy-MM-dd");

  const { data: slots = [], isLoading } = useQuery<ExamSlot[]>({
    queryKey: ["/api/exam-schedule", departmentId, startDate, endDate],
    queryFn: async () => {
      const res = await fetch(`/api/exam-schedule?departmentId=${departmentId}&startDate=${startDate}&endDate=${endDate}`);
      if (!res.ok) throw new Error("Failed to load exam schedule");
      return res.json();
    },
    enabled: !!departmentId,
    refetchInterval: 60000,
  });

  const slotMap = useMemo(() => {
    const m: Record<string, ExamSlot> = {};
    slots.forEach(s => { m[`${s.appointmentDate}|${s.slotTime}`] = s; });
    return m;
  }, [slots]);

  const booked  = slots.filter(s => s.status === "booked").length;
  const blocked = slots.filter(s => s.status === "blocked").length;
  const total   = ALL_SLOTS.length * 5;
  const free    = total - booked - blocked;

  return (
    <div className="flex flex-col rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-gray-800">
      {/* Header */}
      <div className="bg-gradient-to-r from-violet-700 to-purple-700 text-white px-4 py-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-white/20 rounded-lg">
              <CalendarDays className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold leading-tight">Examination Schedule</h3>
              {departmentName && (
                <p className="text-violet-200 text-xs">{departmentName}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-violet-200">
            <Badge variant="secondary" className="bg-blue-500/20 text-white border-0 text-xs">
              {booked} booked
            </Badge>
            <Badge variant="secondary" className="bg-green-500/20 text-white border-0 text-xs">
              {free} free
            </Badge>
            {blocked > 0 && (
              <Badge variant="secondary" className="bg-red-500/20 text-white border-0 text-xs">
                {blocked} blocked
              </Badge>
            )}
          </div>
        </div>

        {/* Week navigation */}
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            className="text-white hover:bg-white/20 h-7 w-7 p-0"
            onClick={() => setWeekRef(subWeeks(weekRef, 1))}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <div className="flex items-center gap-1.5 bg-white/10 rounded-lg px-2.5 py-1 text-sm font-medium">
            <span>Week of {format(weekDates[0], "MMM d")} – {format(weekDates[4], "MMM d, yyyy")}</span>
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="text-white hover:bg-white/20 h-7 w-7 p-0"
            onClick={() => setWeekRef(addWeeks(weekRef, 1))}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-white hover:bg-white/20 text-xs px-2 h-7"
            onClick={() => setWeekRef(new Date())}
          >
            Today
          </Button>
        </div>
      </div>

      {/* Grid */}
      <div className="overflow-auto max-h-[500px]">
        {isLoading ? (
          <div className="flex items-center justify-center h-48 text-gray-400 dark:text-gray-500">
            <div className="text-center">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-violet-600 mx-auto mb-2"></div>
              Loading exam schedule...
            </div>
          </div>
        ) : (
          <div className="min-w-[600px]">
            <table className="w-full border-collapse text-xs">
              <thead className="sticky top-0 z-20 bg-white dark:bg-gray-800 shadow-sm">
                <tr>
                  <th className="border-b border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 w-16 min-w-[64px] py-2 text-gray-500 font-medium text-center">
                    Time
                  </th>
                  {weekDates.map((d, i) => (
                    <th
                      key={i}
                      className={`border-b border-r border-gray-200 dark:border-gray-700 py-2 px-1 font-medium min-w-[110px] ${
                        isToday(d)
                          ? "bg-violet-50 dark:bg-violet-900/20 text-violet-700 dark:text-violet-300"
                          : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
                      }`}
                    >
                      <div className="font-semibold">{WEEK_SHORT[i]}</div>
                      <div className={`text-[11px] ${isToday(d) ? "text-violet-500" : "text-gray-400"}`}>
                        {format(d, "MMM d")}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ALL_SLOTS.map((slotTime, si) => (
                  <tr key={slotTime} className={si % 6 === 0 ? "border-t-2 border-violet-100 dark:border-violet-900/30" : ""}>
                    <td className="border-r border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-center text-[10px] font-mono text-gray-500 py-0 w-16 sticky left-0">
                      {si % 3 === 0 ? fmt12(slotTime) : ""}
                    </td>
                    {weekDates.map((d, di) => {
                      const dateStr = format(d, "yyyy-MM-dd");
                      const key     = `${dateStr}|${slotTime}`;
                      const slot    = slotMap[key];
                      const isBooked  = slot?.status === "booked";
                      const isBlocked = slot?.status === "blocked";

                      return (
                        <td
                          key={di}
                          className={`border-r border-b border-gray-100 dark:border-gray-700 h-7 px-1 ${
                            isBlocked
                              ? "bg-red-50 dark:bg-red-900/20 text-red-700"
                              : isBooked
                              ? "bg-blue-50 dark:bg-blue-900/20"
                              : "bg-white dark:bg-gray-800"
                          } ${isToday(d) ? "bg-opacity-80" : ""}`}
                        >
                          {isBlocked && (
                            <div className="flex items-center gap-0.5 text-[10px] text-red-600 dark:text-red-400 font-medium truncate">
                              <Lock className="w-2.5 h-2.5 shrink-0" />
                              <span className="truncate">{slot.blockReason || "Blocked"}</span>
                            </div>
                          )}
                          {isBooked && (
                            <div className="leading-tight">
                              <div className="font-semibold text-blue-800 dark:text-blue-300 text-[10px] truncate">
                                {slot.patientName}
                              </div>
                              {slot.doctorName && (
                                <div className="text-[9px] text-blue-500 dark:text-blue-400 truncate">{slot.doctorName}</div>
                              )}
                              {slot.patientPhone && (
                                <div className="text-[9px] text-gray-500 truncate">{slot.patientPhone}</div>
                              )}
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

      {/* Legend */}
      <div className="flex-shrink-0 bg-white dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700 px-4 py-2 flex flex-wrap gap-4 text-[11px] text-gray-500 dark:text-gray-400">
        <span className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-blue-100 border border-blue-300" /> Booked
        </span>
        <span className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-red-100 border border-red-300" /> Blocked
        </span>
        <span className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-white border border-gray-200" /> Available
        </span>
        <span className="text-violet-500 dark:text-violet-400 font-medium ml-auto">Read-only view</span>
      </div>
    </div>
  );
}
