import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Calendar, Clock, Users, Plus, Search, Filter, ChevronLeft, ChevronRight, CalendarDays, AlertTriangle, Info, Ban } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { format, parseISO, startOfWeek, endOfWeek, addWeeks, subWeeks, addDays, isSameDay, isToday, isWithinInterval, parseISO as parseDateISO } from "date-fns";
import { apiRequest } from "@/lib/queryClient";
import type { Appointment, Patient, Doctor, AppointmentSlot, Leave, Permission } from "@shared/schema";

export default function Appointments() {
  const [currentWeek, setCurrentWeek] = useState(new Date());
  const [selectedDoctor, setSelectedDoctor] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedAppointment, setSelectedAppointment] = useState<(Appointment & { patient: Patient; doctor: Doctor }) | null>(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Calculate week dates
  const weekStart = startOfWeek(currentWeek, { weekStartsOn: 0 });
  const weekEnd = endOfWeek(currentWeek, { weekStartsOn: 0 });
  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  // Fetch weekly appointments
  const { data: weeklyAppointments = [], isLoading: appointmentsLoading } = useQuery<(Appointment & { patient: Patient; doctor: Doctor })[]>({
    queryKey: [`/api/appointments?startDate=${format(weekStart, 'yyyy-MM-dd')}&endDate=${format(weekEnd, 'yyyy-MM-dd')}${selectedDoctor ? `&doctorId=${selectedDoctor}` : ''}`],
  });

  const centerId = localStorage.getItem("selectedCenterId") || "";

  // Fetch doctors — scoped to the selected center
  const { data: doctors = [] } = useQuery<Doctor[]>({
    queryKey: ["/api/doctors", centerId],
    queryFn: async () => {
      const url = centerId ? `/api/doctors?centerId=${centerId}` : "/api/doctors";
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch doctors");
      return res.json();
    },
  });

  // Fetch patients
  const { data: patients = [] } = useQuery<Patient[]>({
    queryKey: ["/api/patients"],
  });

  // Fetch active leaves (to show blocked dates)
  const { data: activeLeaves = [] } = useQuery<(Leave & { doctor: Doctor })[]>({
    queryKey: ["/api/leaves/active"],
  });

  // Fetch permissions for current week's month (to show partial-day absences)
  const { data: monthPermissions = [] } = useQuery<(Permission & { doctor: Doctor })[]>({
    queryKey: [`/api/permissions/month/${format(currentWeek, 'yyyy')}/${format(currentWeek, 'M')}`],
  });

  // Filter leaves and permissions for the selected doctor
  const doctorLeaves = selectedDoctor
    ? activeLeaves.filter(l => l.doctorId === parseInt(selectedDoctor) && l.isActive)
    : [];

  const doctorPermissions = selectedDoctor
    ? monthPermissions.filter(p => p.doctorId === parseInt(selectedDoctor))
    : [];

  // Check if a date is blocked by a leave for the selected doctor
  const getDayLeave = (dateStr: string): (Leave & { doctor: Doctor }) | undefined => {
    if (!selectedDoctor) return undefined;
    return doctorLeaves.find(leave => {
      try {
        return isWithinInterval(parseDateISO(dateStr), {
          start: parseDateISO(leave.startDate),
          end: parseDateISO(leave.endDate),
        });
      } catch {
        return false;
      }
    });
  };

  // Check if a date has a permission for the selected doctor
  const getDayPermission = (dateStr: string): (Permission & { doctor: Doctor }) | undefined => {
    if (!selectedDoctor) return undefined;
    return doctorPermissions.find(p => p.date === dateStr);
  };

  // Build a set of doctor IDs that belong to the selected center for client-side isolation
  const centerDoctorIds = new Set(doctors.map(d => d.id));

  const filteredAppointments = weeklyAppointments.filter(appointment => {
    // Always scope to the current center's doctors when a centerId is selected
    if (centerId && centerDoctorIds.size > 0 && !centerDoctorIds.has(appointment.doctorId)) {
      return false;
    }
    return (
      !searchTerm ||
      appointment.patient.firstName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      appointment.patient.lastName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      appointment.doctor.name.toLowerCase().includes(searchTerm.toLowerCase())
    );
  });

  // Group appointments by day
  const appointmentsByDay = weekDays.reduce((acc, day) => {
    const dayKey = format(day, 'yyyy-MM-dd');
    acc[dayKey] = filteredAppointments.filter(apt => apt.appointmentDate === dayKey);
    return acc;
  }, {} as Record<string, (Appointment & { patient: Patient; doctor: Doctor })[]>);

  const getStatusColors = (status: string) => {
    switch (status) {
      case 'scheduled':
        return 'bg-blue-100 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-200';
      case 'confirmed':
        return 'bg-green-100 dark:bg-green-900/30 border-green-200 dark:border-green-800 text-green-800 dark:text-green-200';
      case 'arrived':
        return 'bg-purple-100 dark:bg-purple-900/30 border-purple-200 dark:border-purple-800 text-purple-800 dark:text-purple-200';
      case 'completed':
        return 'bg-gray-100 dark:bg-gray-900/30 border-gray-200 dark:border-gray-800 text-gray-800 dark:text-gray-200';
      case 'cancelled':
        return 'bg-red-100 dark:bg-red-900/30 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200';
      case 'missed':
        return 'bg-orange-100 dark:bg-orange-900/30 border-orange-200 dark:border-orange-800 text-orange-800 dark:text-orange-200';
      default:
        return 'bg-blue-100 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-200';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'arrived': return '👋';
      case 'confirmed': return '✅';
      case 'completed': return '✓';
      case 'cancelled': return '❌';
      case 'missed': return '⏰';
      default: return '📅';
    }
  };

  const getLeaveTypeLabel = (type: string) => {
    switch (type) {
      case 'annual': return 'Annual Leave';
      case 'sick': return 'Sick Leave';
      case 'emergency': return 'Emergency Leave';
      default: return type.charAt(0).toUpperCase() + type.slice(1) + ' Leave';
    }
  };

  const getPermissionTypeLabel = (type: string) => {
    switch (type) {
      case 'start_of_day': return 'Late Arrival';
      case 'end_of_day': return 'Early Departure';
      default: return 'Partial Absence';
    }
  };

  // Navigation
  const goToPreviousWeek = () => setCurrentWeek(subWeeks(currentWeek, 1));
  const goToNextWeek = () => setCurrentWeek(addWeeks(currentWeek, 1));
  const goToToday = () => setCurrentWeek(new Date());

  // Delete appointment mutation
  const deleteAppointmentMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiRequest(`/api/appointments/${id}`, { method: "DELETE" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/appointments"] });
      toast({
        title: "Success",
        description: "Appointment deleted successfully",
      });
      setShowEditDialog(false);
      setSelectedAppointment(null);
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to delete appointment",
        variant: "destructive",
      });
    },
  });

  const selectedDoctorInfo = selectedDoctor
    ? doctors.find(d => d.id === parseInt(selectedDoctor))
    : null;

  return (
    <div className="container mx-auto px-2 md:px-6 py-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-gray-100">
            Weekly Calendar
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Manage appointments and scheduling
          </p>
        </div>
        <Button className="flex items-center space-x-2" data-testid="button-new-appointment">
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New Appointment</span>
        </Button>
      </div>

      {/* Week Navigation */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={goToPreviousWeek}
                  data-testid="button-previous-week"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <div className="text-center min-w-[200px]">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    {format(weekStart, 'MMM d')} - {format(weekEnd, 'MMM d, yyyy')}
                  </h2>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={goToNextWeek}
                  data-testid="button-next-week"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={goToToday}
                data-testid="button-today"
              >
                Today
              </Button>
            </div>
            <div className="flex items-center space-x-2">
              <Select value={selectedDoctor} onValueChange={setSelectedDoctor}>
                <SelectTrigger className="w-[200px]" data-testid="select-filter-doctor">
                  <SelectValue placeholder="All doctors" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All doctors</SelectItem>
                  {doctors.map((doctor) => (
                    <SelectItem key={doctor.id} value={doctor.id.toString()}>
                      {doctor.title} {doctor.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {searchTerm && (
            <div className="mt-4">
              <div className="relative max-w-md">
                <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search patients or doctors..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                  data-testid="input-search"
                />
              </div>
            </div>
          )}
        </CardHeader>
      </Card>

      {/* Doctor Availability Notice — only shown when a specific doctor is selected */}
      {selectedDoctor && selectedDoctorInfo && (doctorLeaves.length > 0 || doctorPermissions.length > 0) && (
        <Card className="border-amber-200 bg-amber-50 dark:bg-amber-900/10 dark:border-amber-800">
          <CardHeader className="pb-2 pt-4">
            <CardTitle className="text-base flex items-center gap-2 text-amber-800 dark:text-amber-300">
              <AlertTriangle className="h-4 w-4" />
              Availability Notice — Dr. {selectedDoctorInfo.name}
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-4 space-y-3">
            {doctorLeaves.length > 0 && (
              <div>
                <p className="text-sm font-medium text-red-700 dark:text-red-400 mb-1 flex items-center gap-1">
                  <Ban className="h-3.5 w-3.5" /> Blocked Dates (Leave)
                </p>
                <div className="flex flex-wrap gap-2">
                  {doctorLeaves.map(leave => (
                    <div
                      key={leave.id}
                      className="text-xs bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-700 text-red-800 dark:text-red-300 rounded px-2 py-1"
                    >
                      <span className="font-semibold">{getLeaveTypeLabel(leave.type)}</span>
                      {' '}— {format(parseDateISO(leave.startDate), 'MMM d')}
                      {leave.startDate !== leave.endDate && ` to ${format(parseDateISO(leave.endDate), 'MMM d, yyyy')}`}
                      {leave.reason && <span className="text-red-600 dark:text-red-400"> ({leave.reason})</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {doctorPermissions.length > 0 && (
              <div>
                <p className="text-sm font-medium text-amber-700 dark:text-amber-400 mb-1 flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" /> Partial-Day Absences (Permissions)
                </p>
                <div className="flex flex-wrap gap-2">
                  {doctorPermissions.map(perm => (
                    <div
                      key={perm.id}
                      className="text-xs bg-amber-100 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 text-amber-800 dark:text-amber-300 rounded px-2 py-1"
                    >
                      <span className="font-semibold">{format(parseDateISO(perm.date), 'EEE, MMM d')}</span>
                      {' '}— {getPermissionTypeLabel(perm.type)}: {perm.startTime} – {perm.endTime}
                      {perm.reason && <span className="text-amber-600 dark:text-amber-400"> ({perm.reason})</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Weekly Calendar Grid */}
      <Card>
        <CardContent className="p-4">
          {appointmentsLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-center">
                <CalendarDays className="h-8 w-8 text-gray-400 mx-auto mb-2" />
                <p className="text-gray-600 dark:text-gray-400">Loading appointments...</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-7 gap-2 md:gap-4">
              {weekDays.map((day) => {
                const dayKey = format(day, 'yyyy-MM-dd');
                const dayAppointments = appointmentsByDay[dayKey] || [];
                const isCurrentDay = isToday(day);
                const dayLeave = getDayLeave(dayKey);
                const dayPermission = getDayPermission(dayKey);

                return (
                  <div
                    key={dayKey}
                    className={`min-h-[200px] border rounded-lg p-3 ${
                      dayLeave
                        ? 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800'
                        : isCurrentDay
                          ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
                          : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700'
                    }`}
                    data-testid={`day-${dayKey}`}
                  >
                    {/* Day Header */}
                    <div className="text-center mb-2">
                      <div className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">
                        {format(day, 'EEE')}
                      </div>
                      <div className={`text-lg font-semibold ${
                        dayLeave
                          ? 'text-red-600 dark:text-red-400'
                          : isCurrentDay
                            ? 'text-blue-600 dark:text-blue-400'
                            : 'text-gray-900 dark:text-gray-100'
                      }`}>
                        {format(day, 'd')}
                      </div>
                    </div>

                    {/* Leave Banner */}
                    {dayLeave && (
                      <div className="mb-2 text-center">
                        <div className="inline-flex items-center gap-1 bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-700 text-red-700 dark:text-red-300 rounded px-2 py-0.5 text-xs font-medium">
                          <Ban className="h-3 w-3" />
                          {getLeaveTypeLabel(dayLeave.type)}
                        </div>
                      </div>
                    )}

                    {/* Permission Banner */}
                    {!dayLeave && dayPermission && (
                      <div className="mb-2 text-center">
                        <div className="inline-flex items-center gap-1 bg-amber-100 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 text-amber-700 dark:text-amber-300 rounded px-2 py-0.5 text-xs font-medium">
                          <Clock className="h-3 w-3" />
                          {getPermissionTypeLabel(dayPermission.type)}
                        </div>
                        <div className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                          {dayPermission.startTime} – {dayPermission.endTime}
                        </div>
                      </div>
                    )}

                    {/* Appointments */}
                    <div className="space-y-2">
                      {dayAppointments.length === 0 ? (
                        <div
                          className={`text-center py-4 text-xs border-2 border-dashed rounded-lg transition-colors ${
                            dayLeave
                              ? 'text-red-300 dark:text-red-600 border-red-200 dark:border-red-800 cursor-not-allowed'
                              : 'text-gray-400 border-gray-200 dark:border-gray-600 cursor-pointer hover:border-gray-300 dark:hover:border-gray-500'
                          }`}
                          onClick={() => {
                            if (dayLeave) return;
                            toast({
                              title: "New Appointment",
                              description: `Create appointment for ${format(day, 'EEEE, MMM d')}`,
                            });
                          }}
                          data-testid={`add-appointment-${dayKey}`}
                        >
                          {dayLeave ? (
                            <>
                              <Ban className="h-4 w-4 mx-auto mb-1 text-red-300 dark:text-red-600" />
                              Unavailable
                            </>
                          ) : (
                            <>
                              <Plus className="h-4 w-4 mx-auto mb-1" />
                              Click to add
                            </>
                          )}
                        </div>
                      ) : (
                        dayAppointments.map((appointment) => (
                          <div
                            key={appointment.id}
                            className={`p-2 border rounded-md cursor-pointer hover:opacity-80 transition-all ${getStatusColors(appointment.status)} ${
                              appointment.status === 'arrived' ? 'ring-2 ring-purple-300 dark:ring-purple-700' : ''
                            }`}
                            onClick={() => {
                              setSelectedAppointment(appointment);
                              setShowEditDialog(true);
                            }}
                            data-testid={`appointment-${appointment.id}`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <div className="text-xs font-medium">
                                {appointment.startTime}
                              </div>
                              <span className="text-sm">{getStatusIcon(appointment.status)}</span>
                            </div>
                            <div className="text-xs font-medium truncate">
                              {appointment.patient.firstName} {appointment.patient.lastName}
                            </div>
                            <div className="text-xs truncate opacity-80">
                              Dr. {appointment.doctor.name}
                            </div>
                            <div className="flex items-center justify-between mt-1">
                              <Badge
                                variant="secondary"
                                className="text-xs"
                                style={{ fontSize: '10px', padding: '1px 4px' }}
                              >
                                {appointment.status}
                              </Badge>
                              {appointment.status === 'arrived' && (
                                <span className="text-xs font-bold text-purple-600 dark:text-purple-400">
                                  Ready!
                                </span>
                              )}
                            </div>
                            {/* Warn if appointment falls on a day with a permission */}
                            {dayPermission && !dayLeave && (
                              <div className="mt-1 text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
                                <AlertTriangle className="h-3 w-3" />
                                Dr. absent {dayPermission.startTime}–{dayPermission.endTime}
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Search Filter Toggle */}
      <div className="flex justify-center">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSearchTerm(searchTerm ? "" : " ")}
          className="flex items-center space-x-2"
        >
          <Search className="h-4 w-4" />
          <span>Search Appointments</span>
        </Button>
      </div>

      {/* Edit Appointment Dialog */}
      {showEditDialog && selectedAppointment && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold mb-4">Appointment Details</h3>
            <div className="space-y-3 text-sm">
              <div>
                <strong>Patient:</strong> {selectedAppointment.patient.firstName} {selectedAppointment.patient.lastName}
              </div>
              <div>
                <strong>Doctor:</strong> {selectedAppointment.doctor.title} {selectedAppointment.doctor.name}
              </div>
              <div>
                <strong>Date:</strong> {format(parseISO(selectedAppointment.appointmentDate), 'EEEE, MMM d, yyyy')}
              </div>
              <div>
                <strong>Time:</strong> {selectedAppointment.startTime} - {selectedAppointment.endTime}
              </div>
              {selectedAppointment.reasonForVisit && (
                <div>
                  <strong>Reason:</strong> {selectedAppointment.reasonForVisit}
                </div>
              )}
              {selectedAppointment.notes && (
                <div>
                  <strong>Notes:</strong> {selectedAppointment.notes}
                </div>
              )}
              <div>
                <strong>Status:</strong>
                <Badge className="ml-2">{selectedAppointment.status}</Badge>
              </div>

              {/* Show leave/permission warning in the detail dialog */}
              {(() => {
                const dateStr = selectedAppointment.appointmentDate;
                const apptLeave = activeLeaves.find(leave => {
                  if (leave.doctorId !== selectedAppointment.doctorId) return false;
                  try {
                    return isWithinInterval(parseDateISO(dateStr), {
                      start: parseDateISO(leave.startDate),
                      end: parseDateISO(leave.endDate),
                    });
                  } catch { return false; }
                });
                const apptPermission = monthPermissions.find(
                  p => p.doctorId === selectedAppointment.doctorId && p.date === dateStr
                );
                return (
                  <>
                    {apptLeave && (
                      <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded text-xs text-red-700 dark:text-red-300 flex items-start gap-1.5">
                        <Ban className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
                        <span>
                          <strong>Doctor is on {getLeaveTypeLabel(apptLeave.type)}</strong> on this date
                          {apptLeave.reason && ` — ${apptLeave.reason}`}. Consider rescheduling.
                        </span>
                      </div>
                    )}
                    {apptPermission && !apptLeave && (
                      <div className="mt-2 p-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded text-xs text-amber-700 dark:text-amber-300 flex items-start gap-1.5">
                        <AlertTriangle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
                        <span>
                          <strong>Doctor has a {getPermissionTypeLabel(apptPermission.type)}</strong> on this day ({apptPermission.startTime}–{apptPermission.endTime}).
                          {apptPermission.reason && ` Reason: ${apptPermission.reason}`}
                        </span>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
            <div className="flex space-x-2 mt-6">
              <Button
                variant="outline"
                onClick={() => {
                  setShowEditDialog(false);
                  setSelectedAppointment(null);
                }}
                className="flex-1"
              >
                Close
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  toast({
                    title: "Edit Feature",
                    description: "Edit functionality coming soon",
                  });
                }}
                className="flex-1"
              >
                Edit
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  if (window.confirm("Are you sure you want to delete this appointment?")) {
                    deleteAppointmentMutation.mutate(selectedAppointment.id);
                  }
                }}
                className="flex-1"
                disabled={deleteAppointmentMutation.isPending}
              >
                {deleteAppointmentMutation.isPending ? "Deleting..." : "Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
