import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { format, parseISO, startOfWeek, endOfWeek, addWeeks, subWeeks, addDays } from "date-fns";
import { apiRequest } from "@/lib/queryClient";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { CalendarDays, Users, TrendingUp, ChevronLeft, ChevronRight, Home, Eye, Clock, User, Activity, FileText, Stethoscope } from "lucide-react";
import DoctorOfTheMonthBanner from "@/components/doctor-of-month/DoctorOfTheMonthBanner";
import { MonthlyProcedureReport } from "@/components/reports/monthly-procedure-report";
import ExamScheduleReadOnly from "@/components/examination/ExamScheduleReadOnly";

interface Doctor {
  id: number;
  name: string;
  title: string;
  departmentId: number;
}

interface Patient {
  id: number;
  firstName: string;
  lastName: string;
  phone: string;
  email?: string;
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
  patient: Patient;
  doctor: Doctor;
}

interface Department {
  id: number;
  name: string;
  description?: string;
}

interface AppointmentStats {
  totalAppointments: number;
  completedAppointments: number;
  cancelledAppointments: number;
  scheduledAppointments: number;
  doctorStats: Array<{
    doctor: Doctor;
    appointmentCount: number;
    completionRate: number;
  }>;
}

interface DoctorPerformance {
  doctor: Doctor;
  totalAppointments: number;
  completedAppointments: number;
  cancelledAppointments: number;
  completionRate: number;
  avgAppointmentsPerDay: number;
  leavesDays: number;
  permissionsCount: number;
}

export default function DepartmentMonitoring() {
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  
  // State management
  const [selectedDepartment, setSelectedDepartment] = useState<number | null>(null);
  const [selectedDoctor, setSelectedDoctor] = useState<number | null>(null);
  const [currentWeek, setCurrentWeek] = useState(new Date());
  const [dateRange, setDateRange] = useState({
    start: format(new Date(), 'yyyy-MM-01'),
    end: format(new Date(), 'yyyy-MM-dd')
  });

  // Calculate week dates for calendar
  const weekStart = startOfWeek(currentWeek, { weekStartsOn: 0 }); // Sunday
  const weekEnd = endOfWeek(currentWeek, { weekStartsOn: 0 }); // Saturday
  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  // Navigation functions
  const goToPreviousWeek = () => setCurrentWeek(subWeeks(currentWeek, 1));
  const goToNextWeek = () => setCurrentWeek(addWeeks(currentWeek, 1));
  const goToToday = () => setCurrentWeek(new Date());

  const centerId = localStorage.getItem("selectedCenterId") || "";

  // Fetch user departments — scoped to the selected center
  const { data: departments = [], isLoading: departmentsLoading } = useQuery<Department[]>({
    queryKey: ["/api/user/departments", centerId],
    queryFn: async () => {
      const url = centerId ? `/api/user/departments?centerId=${centerId}` : "/api/user/departments";
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch departments");
      return res.json();
    },
  });

  // Fetch doctors in selected department
  const { data: doctors = [], isLoading: doctorsLoading } = useQuery<Doctor[]>({
    queryKey: ["/api/doctors", selectedDepartment],
    queryFn: async () => {
      const response = await apiRequest(`/api/doctors?departmentId=${selectedDepartment}`);
      return response.json();
    },
    enabled: !!selectedDepartment,
  });

  // Fetch department appointments for weekly view
  const { data: weeklyAppointments = [], isLoading: weeklyLoading } = useQuery<Appointment[]>({
    queryKey: ["/api/department/appointments", selectedDepartment, format(weekStart, 'yyyy-MM-dd'), format(weekEnd, 'yyyy-MM-dd'), selectedDoctor],
    queryFn: async () => {
      const params = new URLSearchParams({
        startDate: format(weekStart, 'yyyy-MM-dd'),
        endDate: format(weekEnd, 'yyyy-MM-dd')
      });
      if (selectedDoctor) {
        params.append('doctorId', selectedDoctor.toString());
      }
      const response = await apiRequest(`/api/department/${selectedDepartment}/appointments?${params}`);
      return response.json();
    },
    enabled: !!selectedDepartment,
  });

  // Fetch department appointment statistics
  const { data: appointmentStats, isLoading: statsLoading } = useQuery<AppointmentStats>({
    queryKey: ["/api/department/appointments/stats", selectedDepartment, dateRange.start, dateRange.end],
    queryFn: async () => {
      const params = new URLSearchParams({
        startDate: dateRange.start,
        endDate: dateRange.end
      });
      const response = await apiRequest(`/api/department/${selectedDepartment}/appointments/stats?${params}`);
      return response.json();
    },
    enabled: !!selectedDepartment,
  });

  // Fetch exam schedule slots for current week (Sun–Thu) for stat counts
  const examWeekStart = format(addDays(weekStart, 0), 'yyyy-MM-dd');
  const examWeekEnd   = format(addDays(weekStart, 4), 'yyyy-MM-dd');
  const { data: examSlots = [] } = useQuery<Array<{ status: string }>>({
    queryKey: ["/api/exam-schedule", selectedDepartment, examWeekStart, examWeekEnd],
    queryFn: async () => {
      const res = await fetch(`/api/exam-schedule?departmentId=${selectedDepartment}&startDate=${examWeekStart}&endDate=${examWeekEnd}`);
      if (!res.ok) throw new Error("Failed to fetch exam slots");
      return res.json();
    },
    enabled: !!selectedDepartment,
  });

  const EXAM_SLOT_STEP = 10;
  const examTotalPerWeek = (6 * 60 / EXAM_SLOT_STEP) * 5; // 08:00–14:00, 5 days
  const examBooked  = examSlots.filter(s => s.status === "booked").length;
  const examBlocked = examSlots.filter(s => s.status === "blocked").length;
  const examFree    = examTotalPerWeek - examBooked - examBlocked;

  // Fetch doctor performance metrics
  const { data: performanceMetrics = [], isLoading: performanceLoading } = useQuery<DoctorPerformance[]>({
    queryKey: ["/api/department/doctors/performance", selectedDepartment, selectedDoctor, dateRange.start, dateRange.end],
    queryFn: async () => {
      const params = new URLSearchParams({
        startDate: dateRange.start,
        endDate: dateRange.end
      });
      if (selectedDoctor) {
        params.append('doctorId', selectedDoctor.toString());
      }
      const response = await apiRequest(`/api/department/${selectedDepartment}/doctors/performance?${params}`);
      return response.json();
    },
    enabled: !!selectedDepartment,
  });

  // Group appointments by day for weekly calendar
  const appointmentsByDay = weekDays.reduce((acc, day) => {
    const dayKey = format(day, 'yyyy-MM-dd');
    acc[dayKey] = weeklyAppointments.filter(apt => apt.appointmentDate === dayKey);
    return acc;
  }, {} as Record<string, Appointment[]>);

  // Auto-select first department if only one exists
  useEffect(() => {
    if (departments.length === 1 && !selectedDepartment) {
      setSelectedDepartment(departments[0].id);
    }
  }, [departments, selectedDepartment]);

  const weekdayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-4">
              <div className="p-2 bg-blue-600 rounded-lg">
                <Activity className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                  Department Monitoring
                </h1>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Monitor doctor schedules and performance
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={() => setLocation("/")}
              className="flex items-center space-x-2"
            >
              <Home className="h-4 w-4" />
              <span>Back to Home</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Department Selection */}
        <div className="mb-6">
          <div className="flex items-center space-x-4">
            <div className="flex-1">
              <label htmlFor="department-select" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Select Department
              </label>
              <Select 
                value={selectedDepartment?.toString() || ""} 
                onValueChange={(value) => {
                  setSelectedDepartment(parseInt(value));
                  setSelectedDoctor(null); // Reset doctor selection
                }}
                disabled={departmentsLoading}
              >
                <SelectTrigger className="w-full max-w-md">
                  <SelectValue placeholder={departmentsLoading ? "Loading departments..." : "Choose a department"} />
                </SelectTrigger>
                <SelectContent>
                  {departments.map((dept) => (
                    <SelectItem key={dept.id} value={dept.id.toString()}>
                      {dept.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedDepartment && doctors.length > 0 && (
              <div className="flex-1">
                <label htmlFor="doctor-select" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Filter by Doctor (Optional)
                </label>
                <Select 
                  value={selectedDoctor?.toString() || ""} 
                  onValueChange={(value) => setSelectedDoctor(value ? parseInt(value) : null)}
                  disabled={doctorsLoading}
                >
                  <SelectTrigger className="w-full max-w-md">
                    <SelectValue placeholder="All doctors" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">All doctors</SelectItem>
                    {doctors.map((doctor) => (
                      <SelectItem key={doctor.id} value={doctor.id.toString()}>
                        {doctor.title} {doctor.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        </div>

        {/* Doctor of the Month Banner */}
        {selectedDepartment && (
          <div className="mb-6">
            <DoctorOfTheMonthBanner 
              departmentId={selectedDepartment} 
              className="max-w-4xl"
            />
          </div>
        )}

        {selectedDepartment ? (
          <Tabs defaultValue="calendar" className="space-y-6">
            <TabsList className="grid w-full max-w-2xl grid-cols-5">
              <TabsTrigger value="calendar" className="flex items-center space-x-2">
                <CalendarDays className="h-4 w-4" />
                <span>Calendar</span>
              </TabsTrigger>
              <TabsTrigger value="statistics" className="flex items-center space-x-2">
                <TrendingUp className="h-4 w-4" />
                <span>Statistics</span>
              </TabsTrigger>
              <TabsTrigger value="performance" className="flex items-center space-x-2">
                <Users className="h-4 w-4" />
                <span>Performance</span>
              </TabsTrigger>
              <TabsTrigger value="reports" className="flex items-center space-x-2">
                <FileText className="h-4 w-4" />
                <span>Monthly Reports</span>
              </TabsTrigger>
              <TabsTrigger value="exam-schedule" className="flex items-center space-x-2">
                <Stethoscope className="h-4 w-4" />
                <span>Exam Schedule</span>
              </TabsTrigger>
            </TabsList>

            {/* Calendar View */}
            <TabsContent value="calendar">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center space-x-2">
                        <CalendarDays className="h-5 w-5" />
                        <span>Weekly Appointment Calendar</span>
                      </CardTitle>
                      <CardDescription>
                        View appointments across the department for the selected week
                      </CardDescription>
                    </div>
                    
                    {/* Week Navigation */}
                    <div className="flex items-center space-x-2">
                      <Button variant="outline" size="sm" onClick={goToPreviousWeek}>
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="sm" onClick={goToToday}>
                        Today
                      </Button>
                      <Button variant="outline" size="sm" onClick={goToNextWeek}>
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                      <span className="text-sm font-medium text-gray-600 dark:text-gray-400 ml-2">
                        {format(weekStart, 'MMM d')} - {format(weekEnd, 'MMM d, yyyy')}
                      </span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {weeklyLoading ? (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                      <p className="mt-2 text-gray-600 dark:text-gray-400">Loading appointments...</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-7 gap-2">
                      {weekDays.map((day, index) => {
                        const dayKey = format(day, 'yyyy-MM-dd');
                        const dayAppointments = appointmentsByDay[dayKey] || [];
                        const isToday = format(day, 'yyyy-MM-dd') === format(new Date(), 'yyyy-MM-dd');
                        
                        return (
                          <div
                            key={dayKey}
                            className={`p-3 border rounded-lg min-h-32 ${
                              isToday 
                                ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800' 
                                : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700'
                            }`}
                          >
                            <div className="text-center mb-2">
                              <div className={`text-xs font-medium ${isToday ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500 dark:text-gray-400'}`}>
                                {weekdayNames[index]}
                              </div>
                              <div className={`text-lg font-semibold ${isToday ? 'text-blue-900 dark:text-blue-100' : 'text-gray-900 dark:text-gray-100'}`}>
                                {format(day, 'd')}
                              </div>
                            </div>
                            
                            <div className="space-y-1">
                              {dayAppointments.map((appointment) => (
                                <div
                                  key={appointment.id}
                                  className="text-xs p-2 rounded bg-gradient-to-r from-blue-500 to-purple-600 text-white cursor-pointer hover:from-blue-600 hover:to-purple-700 transition-all"
                                  title={`${appointment.doctor?.title || ''} ${appointment.doctor?.name || 'Unknown Doctor'}: ${appointment.patient?.firstName || ''} ${appointment.patient?.lastName || ''} - ${appointment.reasonForVisit || ''}`}
                                >
                                  <div className="font-medium truncate">
                                    {appointment.startTime} - {appointment.doctor?.name || 'Unknown Doctor'}
                                  </div>
                                  <div className="truncate opacity-90">
                                    {appointment.patient?.firstName || ''} {appointment.patient?.lastName || ''}
                                  </div>
                                  <div className="truncate opacity-75">
                                    {appointment.reasonForVisit}
                                  </div>
                                </div>
                              ))}
                              {dayAppointments.length === 0 && (
                                <div className="text-xs text-gray-400 dark:text-gray-500 text-center py-2">
                                  No appointments
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Statistics View */}
            <TabsContent value="statistics">
              <div className="space-y-6">
                {/* Date Range Selector */}
                <Card>
                  <CardHeader>
                    <CardTitle>Statistics Period</CardTitle>
                    <CardDescription>Select date range for statistics</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center space-x-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Start Date
                        </label>
                        <input
                          type="date"
                          value={dateRange.start}
                          onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
                          className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          End Date
                        </label>
                        <input
                          type="date"
                          value={dateRange.end}
                          onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
                          className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Exam Schedule Slot Counts */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center space-x-2 text-base">
                      <Stethoscope className="h-4 w-4 text-violet-600" />
                      <span>Exam Schedule – Current Week</span>
                    </CardTitle>
                    <CardDescription>Booked / free / blocked slots (Sun–Thu, 08:00–14:00)</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                        <div className="text-2xl font-bold text-blue-600">{examBooked}</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">Booked</div>
                      </div>
                      <div className="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                        <div className="text-2xl font-bold text-green-600">{examFree}</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">Free</div>
                      </div>
                      <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                        <div className="text-2xl font-bold text-red-600">{examBlocked}</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">Blocked</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Overall Statistics */}
                {appointmentStats && (
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <Card>
                      <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Total Appointments</p>
                            <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{appointmentStats.totalAppointments}</p>
                          </div>
                          <CalendarDays className="h-8 w-8 text-blue-600" />
                        </div>
                      </CardContent>
                    </Card>
                    
                    <Card>
                      <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Completed</p>
                            <p className="text-2xl font-bold text-green-600">{appointmentStats.completedAppointments}</p>
                          </div>
                          <div className="h-8 w-8 bg-green-100 rounded-full flex items-center justify-center">
                            <div className="h-4 w-4 bg-green-600 rounded-full"></div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    
                    <Card>
                      <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Scheduled</p>
                            <p className="text-2xl font-bold text-blue-600">{appointmentStats.scheduledAppointments}</p>
                          </div>
                          <Clock className="h-8 w-8 text-blue-600" />
                        </div>
                      </CardContent>
                    </Card>
                    
                    <Card>
                      <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Cancelled</p>
                            <p className="text-2xl font-bold text-red-600">{appointmentStats.cancelledAppointments}</p>
                          </div>
                          <div className="h-8 w-8 bg-red-100 rounded-full flex items-center justify-center">
                            <div className="h-4 w-4 bg-red-600 rounded-full"></div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* Doctor Statistics */}
                {appointmentStats && appointmentStats.doctorStats.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Doctor Performance</CardTitle>
                      <CardDescription>Appointment statistics by doctor</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        {appointmentStats.doctorStats.map((stat) => (
                          <div key={stat.doctor.id} className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                            <div className="flex items-center space-x-3">
                              <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-full">
                                <User className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 dark:text-gray-100">
                                  {stat.doctor?.title || ''} {stat.doctor?.name || 'Unknown Doctor'}
                                </div>
                                <div className="text-sm text-gray-600 dark:text-gray-400">
                                  {stat.appointmentCount} appointments
                                </div>
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="font-medium text-gray-900 dark:text-gray-100">
                                {stat.completionRate.toFixed(1)}%
                              </div>
                              <div className="text-sm text-gray-600 dark:text-gray-400">
                                completion rate
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            </TabsContent>

            {/* Performance View */}
            <TabsContent value="performance">
              <Card>
                <CardHeader>
                  <CardTitle>Doctor Performance Metrics</CardTitle>
                  <CardDescription>Detailed performance analysis for each doctor</CardDescription>
                </CardHeader>
                <CardContent>
                  {performanceLoading ? (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                      <p className="mt-2 text-gray-600 dark:text-gray-400">Loading performance data...</p>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {performanceMetrics.map((metric) => (
                        <div key={metric.doctor.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-6">
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center space-x-3">
                              <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-full">
                                <User className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                              </div>
                              <div>
                                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                                  {metric.doctor?.title || ''} {metric.doctor?.name || 'Unknown Doctor'}
                                </h3>
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                  Doctor Performance Overview
                                </p>
                              </div>
                            </div>
                            <Badge variant={metric.completionRate >= 80 ? "default" : metric.completionRate >= 60 ? "secondary" : "destructive"}>
                              {metric.completionRate.toFixed(1)}% completion rate
                            </Badge>
                          </div>

                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                              <div className="text-2xl font-bold text-blue-600">{metric.totalAppointments}</div>
                              <div className="text-xs text-gray-600 dark:text-gray-400">Total Appointments</div>
                            </div>
                            <div className="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                              <div className="text-2xl font-bold text-green-600">{metric.completedAppointments}</div>
                              <div className="text-xs text-gray-600 dark:text-gray-400">Completed</div>
                            </div>
                            <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                              <div className="text-2xl font-bold text-red-600">{metric.cancelledAppointments}</div>
                              <div className="text-xs text-gray-600 dark:text-gray-400">Cancelled</div>
                            </div>
                            <div className="text-center p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                              <div className="text-2xl font-bold text-purple-600">{metric.avgAppointmentsPerDay.toFixed(1)}</div>
                              <div className="text-xs text-gray-600 dark:text-gray-400">Avg/Day</div>
                            </div>
                          </div>

                          <div className="mt-4 grid grid-cols-2 gap-4">
                            <div className="flex items-center justify-between p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Leave Days</span>
                              <span className="text-lg font-bold text-yellow-600">{metric.leavesDays}</span>
                            </div>
                            <div className="flex items-center justify-between p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
                              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Permissions</span>
                              <span className="text-lg font-bold text-orange-600">{metric.permissionsCount}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Monthly Reports View */}
            <TabsContent value="reports">
              <MonthlyProcedureReport 
                departmentId={selectedDepartment} 
                doctorId={selectedDoctor || undefined}
              />
            </TabsContent>

            {/* Exam Schedule View */}
            <TabsContent value="exam-schedule">
              <ExamScheduleReadOnly
                departmentId={selectedDepartment}
                departmentName={departments.find(d => d.id === selectedDepartment)?.name}
                initialWeek={currentWeek}
              />
            </TabsContent>
          </Tabs>
        ) : (
          <Card>
            <CardContent className="p-8 text-center">
              <Eye className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                Select a Department
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Choose a department from the dropdown above to start monitoring doctor appointments and performance.
              </p>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}