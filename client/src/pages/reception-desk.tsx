import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { CheckCircle, Clock, Search, UserCheck, Calendar, Phone, FileText, AlertTriangle, Plus, User, SkipForward, RotateCcw, Ban, ShieldAlert } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { format, parseISO, isWithinInterval, parseISO as parseDateISO } from "date-fns";
import { apiRequest } from "@/lib/queryClient";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import type { Appointment, Patient, Doctor, EmergencyAssignment, InsertEmergencyAssignment, Leave, Permission } from "@shared/schema";

// Emergency assignment form schema
const emergencyFormSchema = z.object({
  patientName: z.string().min(1, "Patient name is required"),
  emergencyType: z.string().min(1, "Emergency type is required"),
  notes: z.string().optional(),
});

type EmergencyFormData = z.infer<typeof emergencyFormSchema>;

export default function ReceptionDesk() {
  const [selectedDepartment, setSelectedDepartment] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState("");
  const [showEmergencyForm, setShowEmergencyForm] = useState(false);
  const [skippedDoctorIds, setSkippedDoctorIds] = useState<number[]>([]);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Get today's date for filtering appointments
  const today = format(new Date(), 'yyyy-MM-dd');

  const centerId = localStorage.getItem("selectedCenterId") || "";

  // Fetch user's departments — scoped to the selected center
  const { data: userDepartments = [] } = useQuery<Array<{id: number; name: string}>>({
    queryKey: ["/api/user/departments", centerId],
    queryFn: async () => {
      const url = centerId ? `/api/user/departments?centerId=${centerId}` : "/api/user/departments";
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch departments");
      return res.json();
    },
  });

  // Fetch today's appointments for selected department
  const { data: todaysAppointments = [], isLoading: appointmentsLoading } = useQuery<(Appointment & { patient: Patient; doctor: Doctor })[]>({
    queryKey: ["/api/department/appointments", selectedDepartment, { startDate: today, endDate: today }],
    queryFn: async () => {
      const params = new URLSearchParams({
        startDate: today,
        endDate: today, // Same day for today's appointments
      });
      const response = await apiRequest(`/api/department/${selectedDepartment}/appointments?${params}`);
      return response.json();
    },
    enabled: !!selectedDepartment,
  });

  // Fetch next available doctor for emergency assignments
  const { data: nextEmergencyDoctor, isLoading: nextDoctorLoading } = useQuery<Doctor & { currentClinic?: { id: number; name: string } }>({
    queryKey: ["/api/emergency-assignments/next-doctor", selectedDepartment, skippedDoctorIds],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (selectedDepartment) {
        params.append('departmentId', selectedDepartment);
      }
      if (skippedDoctorIds.length > 0) {
        params.append('skipDoctorIds', skippedDoctorIds.join(','));
      }
      const response = await apiRequest(`/api/emergency-assignments/next-doctor?${params}`);
      return response.json();
    },
    enabled: !!selectedDepartment,
  });

  // Fetch recent emergency assignments for the department
  const { data: recentEmergencies = [], isLoading: emergenciesLoading } = useQuery<(EmergencyAssignment & { doctor: Doctor })[]>({
    queryKey: ["/api/emergency-assignments", selectedDepartment],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (selectedDepartment) {
        params.append('departmentId', selectedDepartment);
      }
      const response = await apiRequest(`/api/emergency-assignments?${params}`);
      return response.json();
    },
    enabled: !!selectedDepartment,
  });

  // Fetch active leaves for the selected department
  const { data: activeLeaves = [] } = useQuery<(Leave & { doctor: Doctor })[]>({
    queryKey: ["/api/leaves/active", selectedDepartment],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (selectedDepartment) params.append('departmentId', selectedDepartment);
      const response = await apiRequest(`/api/leaves/active?${params}`);
      return response.json();
    },
    enabled: !!selectedDepartment,
  });

  // Fetch today's permissions for the selected department
  const { data: allPermissions = [] } = useQuery<(Permission & { doctor: Doctor })[]>({
    queryKey: ["/api/permissions", selectedDepartment],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (selectedDepartment) params.append('departmentId', selectedDepartment);
      const response = await apiRequest(`/api/permissions?${params}`);
      return response.json();
    },
    enabled: !!selectedDepartment,
  });

  // Filter to only today's leaves and permissions
  const todayLeaves = activeLeaves.filter(leave => {
    try {
      return isWithinInterval(parseDateISO(today), {
        start: parseDateISO(leave.startDate),
        end: parseDateISO(leave.endDate),
      });
    } catch { return false; }
  });

  const todayPermissions = allPermissions.filter(p => p.date === today);

  // Filter appointments by search term and only show scheduled or confirmed appointments
  const filteredAppointments = todaysAppointments.filter(appointment => {
    const matchesSearch = !searchTerm || 
      appointment.patient.firstName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      appointment.patient.lastName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (appointment.patient.phone && appointment.patient.phone.toLowerCase().includes(searchTerm.toLowerCase())) ||
      appointment.doctor.name.toLowerCase().includes(searchTerm.toLowerCase());
    
    // Only show appointments that patients can check in for
    const canCheckIn = appointment.status && ['scheduled', 'confirmed'].includes(appointment.status);
    
    return matchesSearch && canCheckIn;
  });

  // Group appointments by status for better organization
  const waitingAppointments = filteredAppointments.filter(apt => apt.status && ['scheduled', 'confirmed'].includes(apt.status));
  const arrivedAppointments = todaysAppointments.filter(apt => apt.status === 'arrived');

  // Mark patient as arrived mutation
  const markArrivedMutation = useMutation({
    mutationFn: async (appointmentId: number) => {
      return apiRequest(`/api/appointments/${appointmentId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'arrived' }),
        headers: {
          'Content-Type': 'application/json',
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ 
        queryKey: ["/api/department/appointments"]
      });
      toast({
        title: "Patient Checked In",
        description: "Patient has been marked as arrived successfully.",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to check in patient. Please try again.",
        variant: "destructive",
      });
    },
  });

  // Emergency assignment form
  const emergencyForm = useForm<EmergencyFormData>({
    resolver: zodResolver(emergencyFormSchema),
    defaultValues: {
      patientName: "",
      emergencyType: "",
      notes: "",
    },
  });

  // Mutation for creating emergency assignment
  const assignEmergencyMutation = useMutation({
    mutationFn: async (data: EmergencyFormData) => {
      if (!nextEmergencyDoctor) {
        throw new Error("No available doctor for emergency assignment");
      }
      
      const emergencyAssignment: InsertEmergencyAssignment = {
        doctorId: nextEmergencyDoctor.id,
        assignedDate: today,
        assignedTime: format(new Date(), 'HH:mm:ss'),
        emergencyNumber: recentEmergencies.length + 1, // Simple numbering
        patientName: data.patientName,
        emergencyType: data.emergencyType,
        notes: data.notes || "",
      };
      
      const response = await apiRequest('/api/emergency-assignments', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(emergencyAssignment),
      });
      
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ 
        queryKey: ["/api/emergency-assignments"]
      });
      queryClient.invalidateQueries({ 
        queryKey: ["/api/emergency-assignments/next-doctor"]
      });
      setSkippedDoctorIds([]);
      emergencyForm.reset();
      setShowEmergencyForm(false);
      toast({
        title: "Emergency Assigned",
        description: `Emergency case assigned to Dr. ${nextEmergencyDoctor?.name}`,
      });
    },
    onError: (error: Error) => {
      console.error("[Emergency Assignment Error]", error);
      toast({
        title: "Error",
        description: error.message || "Failed to assign emergency. Please try again.",
        variant: "destructive",
      });
    },
  });

  // Skip doctor functionality
  const handleSkipDoctor = () => {
    if (nextEmergencyDoctor && !skippedDoctorIds.includes(nextEmergencyDoctor.id)) {
      setSkippedDoctorIds(prev => [...prev, nextEmergencyDoctor.id]);
      toast({
        title: "Doctor Skipped",
        description: `Dr. ${nextEmergencyDoctor.name} has been skipped. Getting next available doctor.`,
      });
    }
  };

  const handleResetSkips = () => {
    setSkippedDoctorIds([]);
    toast({
      title: "Reset Complete", 
      description: "All skipped doctors are now available again.",
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'scheduled': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'confirmed': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'arrived': return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200';
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Reception Desk</h1>
          <p className="text-muted-foreground">
            Check in patients for appointments and manage emergency walk-ins
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Calendar className="h-4 w-4" />
          {format(new Date(), 'EEEE, MMMM d, yyyy')}
        </div>
      </div>

      {/* Department and Search Filters */}
      <div className="flex gap-4 items-end">
        <div className="flex-1">
          <label className="text-sm font-medium mb-2 block">Select Department</label>
          <Select 
            value={selectedDepartment} 
            onValueChange={setSelectedDepartment}
            data-testid="department-select"
          >
            <SelectTrigger>
              <SelectValue placeholder="Choose a department" />
            </SelectTrigger>
            <SelectContent>
              {userDepartments.map((dept) => (
                <SelectItem key={dept.id} value={dept.id.toString()}>
                  {dept.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex-1">
          <label className="text-sm font-medium mb-2 block">Search Patients</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
            <Input
              placeholder="Search by patient name, phone, or doctor..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
              data-testid="search-input"
            />
          </div>
        </div>
      </div>

      {!selectedDepartment ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Please select a department to view today's appointments
          </CardContent>
        </Card>
      ) : appointmentsLoading ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Loading appointments...
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Waiting for Check-in */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-blue-500" />
                Waiting for Check-in ({waitingAppointments.length})
              </CardTitle>
              <CardDescription>
                Patients scheduled for today who haven't arrived yet
              </CardDescription>
            </CardHeader>
            <CardContent>
              {waitingAppointments.length === 0 ? (
                <p className="text-center text-muted-foreground py-4">
                  No patients waiting for check-in
                </p>
              ) : (
                <div className="space-y-3">
                  {waitingAppointments.map((appointment) => (
                    <div
                      key={appointment.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors"
                      data-testid={`appointment-${appointment.id}`}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold">
                            {appointment.patient.firstName} {appointment.patient.lastName}
                          </h3>
                          <Badge className={getStatusColor(appointment.status || 'unknown')}>
                            {appointment.status || 'Unknown'}
                          </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground space-y-1">
                          <div className="flex items-center gap-4">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {appointment.startTime}
                            </span>
                            <span className="flex items-center gap-1">
                              <UserCheck className="h-3 w-3" />
                              Dr. {appointment.doctor.name}
                            </span>
                            {appointment.patient.phone && (
                              <span className="flex items-center gap-1">
                                <Phone className="h-3 w-3" />
                                {appointment.patient.phone}
                              </span>
                            )}
                          </div>
                          {appointment.reasonForVisit && (
                            <div className="flex items-center gap-1">
                              <FileText className="h-3 w-3" />
                              {appointment.reasonForVisit}
                            </div>
                          )}
                        </div>
                      </div>
                      <Button
                        onClick={() => markArrivedMutation.mutate(appointment.id)}
                        disabled={markArrivedMutation.isPending}
                        className="ml-4"
                        data-testid={`checkin-${appointment.id}`}
                      >
                        <CheckCircle className="h-4 w-4 mr-2" />
                        {markArrivedMutation.isPending ? "Checking In..." : "Check In"}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Doctor Availability Today */}
          {(todayLeaves.length > 0 || todayPermissions.length > 0) && (
            <Card className="border-amber-200 bg-amber-50 dark:bg-amber-900/10 dark:border-amber-800">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-amber-800 dark:text-amber-300 text-base">
                  <ShieldAlert className="h-5 w-5" />
                  Doctor Availability — Today
                </CardTitle>
                <CardDescription>
                  Doctors who are unavailable or partially absent today
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {todayLeaves.length > 0 && (
                  <div>
                    <p className="text-sm font-semibold text-red-700 dark:text-red-400 mb-2 flex items-center gap-1">
                      <Ban className="h-4 w-4" /> On Leave Today
                    </p>
                    <div className="space-y-2">
                      {todayLeaves.map(leave => (
                        <div
                          key={leave.id}
                          className="flex items-center justify-between p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg text-sm"
                        >
                          <div>
                            <p className="font-medium text-red-800 dark:text-red-300">Dr. {leave.doctor.name}</p>
                            {leave.reason && (
                              <p className="text-xs text-red-600 dark:text-red-400">{leave.reason}</p>
                            )}
                          </div>
                          <Badge className="bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-700 text-xs">
                            {leave.type.charAt(0).toUpperCase() + leave.type.slice(1)} Leave
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {todayPermissions.length > 0 && (
                  <div>
                    <p className="text-sm font-semibold text-amber-700 dark:text-amber-400 mb-2 flex items-center gap-1">
                      <Clock className="h-4 w-4" /> Partial Absence Today
                    </p>
                    <div className="space-y-2">
                      {todayPermissions.map(perm => (
                        <div
                          key={perm.id}
                          className="flex items-center justify-between p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg text-sm"
                        >
                          <div>
                            <p className="font-medium text-amber-800 dark:text-amber-300">Dr. {perm.doctor.name}</p>
                            <p className="text-xs text-amber-600 dark:text-amber-400">
                              {perm.type === 'start_of_day' ? 'Late Arrival' : 'Early Departure'}: {perm.startTime} – {perm.endTime}
                            </p>
                            {perm.reason && (
                              <p className="text-xs text-amber-500 dark:text-amber-500">{perm.reason}</p>
                            )}
                          </div>
                          <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 border-amber-200 dark:border-amber-700 text-xs">
                            Permission
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Emergency Assignments Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Emergency Assignment Card */}
            <Card className="border-orange-200 bg-orange-50/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-orange-500" />
                  Emergency Walk-ins
                </CardTitle>
                <CardDescription>
                  Assign emergency patients to available doctors
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {nextDoctorLoading ? (
                  <p className="text-center text-muted-foreground">Loading available doctors...</p>
                ) : nextEmergencyDoctor ? (
                  <div className="space-y-4">
                    <div className="p-3 bg-white border rounded-lg">
                      <p className="text-sm text-muted-foreground mb-1">Next Available Doctor:</p>
                      <p className="font-semibold text-orange-600">
                        Dr. {nextEmergencyDoctor.name}
                      </p>
                      <p className="text-xs text-muted-foreground">{nextEmergencyDoctor.title}</p>
                      {nextEmergencyDoctor.currentClinic && (
                        <p className="text-sm font-medium text-blue-600 mt-1 flex items-center gap-1">
                          <span className="inline-block w-2 h-2 bg-blue-500 rounded-full"></span>
                          Located in: {nextEmergencyDoctor.currentClinic.name}
                        </p>
                      )}
                      {skippedDoctorIds.length > 0 && (
                        <p className="text-xs text-orange-600 mt-1">
                          ({skippedDoctorIds.length} doctor{skippedDoctorIds.length > 1 ? 's' : ''} skipped)
                        </p>
                      )}
                    </div>
                    
                    <div className="flex gap-2">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={handleSkipDoctor}
                        className="flex-1"
                        data-testid="skip-doctor-btn"
                      >
                        <SkipForward className="h-4 w-4 mr-2" />
                        Skip Doctor
                      </Button>
                      {skippedDoctorIds.length > 0 && (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={handleResetSkips}
                          className="flex-1"
                          data-testid="reset-skips-btn"
                        >
                          <RotateCcw className="h-4 w-4 mr-2" />
                          Reset Skips
                        </Button>
                      )}
                    </div>
                    
                    {!showEmergencyForm ? (
                      <Button 
                        onClick={() => setShowEmergencyForm(true)} 
                        className="w-full bg-orange-600 hover:bg-orange-700"
                        data-testid="emergency-assign-btn"
                      >
                        <Plus className="h-4 w-4 mr-2" />
                        Assign Emergency Patient
                      </Button>
                    ) : (
                      <Form {...emergencyForm}>
                        <form 
                          onSubmit={emergencyForm.handleSubmit((data) => assignEmergencyMutation.mutate(data))}
                          className="space-y-3"
                        >
                          <FormField
                            control={emergencyForm.control}
                            name="patientName"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Patient Name</FormLabel>
                                <FormControl>
                                  <Input 
                                    placeholder="Enter patient name" 
                                    {...field} 
                                    data-testid="emergency-patient-name"
                                  />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={emergencyForm.control}
                            name="emergencyType"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Emergency Type</FormLabel>
                                <FormControl>
                                  <Select onValueChange={field.onChange} value={field.value}>
                                    <SelectTrigger data-testid="emergency-type-select">
                                      <SelectValue placeholder="Select emergency type" />
                                    </SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="pain">Severe Pain</SelectItem>
                                      <SelectItem value="trauma">Dental Trauma</SelectItem>
                                      <SelectItem value="infection">Infection</SelectItem>
                                      <SelectItem value="bleeding">Bleeding</SelectItem>
                                      <SelectItem value="swelling">Severe Swelling</SelectItem>
                                      <SelectItem value="other">Other Emergency</SelectItem>
                                    </SelectContent>
                                  </Select>
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={emergencyForm.control}
                            name="notes"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Notes (Optional)</FormLabel>
                                <FormControl>
                                  <Input 
                                    placeholder="Additional notes..." 
                                    {...field} 
                                    data-testid="emergency-notes"
                                  />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <div className="flex gap-2">
                            <Button 
                              type="submit" 
                              disabled={assignEmergencyMutation.isPending}
                              className="flex-1 bg-orange-600 hover:bg-orange-700"
                              data-testid="emergency-submit-btn"
                            >
                              {assignEmergencyMutation.isPending ? "Assigning..." : "Assign Emergency"}
                            </Button>
                            <Button 
                              type="button" 
                              variant="outline" 
                              onClick={() => {
                                setShowEmergencyForm(false);
                                emergencyForm.reset();
                              }}
                              data-testid="emergency-cancel-btn"
                            >
                              Cancel
                            </Button>
                          </div>
                        </form>
                      </Form>
                    )}
                  </div>
                ) : (
                  <p className="text-center text-muted-foreground py-4">
                    No doctors available for emergency assignment
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Recent Emergency Assignments */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <User className="h-5 w-5 text-blue-500" />
                  Recent Emergencies ({recentEmergencies.length})
                </CardTitle>
                <CardDescription>
                  Today's emergency assignments
                </CardDescription>
              </CardHeader>
              <CardContent>
                {emergenciesLoading ? (
                  <p className="text-center text-muted-foreground">Loading emergencies...</p>
                ) : recentEmergencies.length === 0 ? (
                  <p className="text-center text-muted-foreground py-4">
                    No emergency assignments today
                  </p>
                ) : (
                  <div className="space-y-3 max-h-64 overflow-y-auto">
                    {recentEmergencies
                      .filter(emergency => emergency.assignedDate === today)
                      .sort((a, b) => b.emergencyNumber - a.emergencyNumber)
                      .map((emergency) => (
                        <div
                          key={emergency.id}
                          className="flex items-center justify-between p-3 border rounded-lg"
                          data-testid={`emergency-${emergency.id}`}
                        >
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <Badge variant="outline" className="text-orange-600 border-orange-600">
                                Emergency #{emergency.emergencyNumber}
                              </Badge>
                            </div>
                            <p className="font-medium">Dr. {emergency.doctor.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {emergency.assignedTime}
                            </p>
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Already Arrived */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-purple-500" />
                Already Arrived ({arrivedAppointments.length})
              </CardTitle>
              <CardDescription>
                Patients who have checked in and are waiting to be seen
              </CardDescription>
            </CardHeader>
            <CardContent>
              {arrivedAppointments.length === 0 ? (
                <p className="text-center text-muted-foreground py-4">
                  No patients have checked in yet
                </p>
              ) : (
                <div className="space-y-3">
                  {arrivedAppointments.map((appointment) => (
                    <div
                      key={appointment.id}
                      className="flex items-center justify-between p-4 border rounded-lg bg-purple-50 dark:bg-purple-900/20"
                      data-testid={`arrived-${appointment.id}`}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold">
                            {appointment.patient.firstName} {appointment.patient.lastName}
                          </h3>
                          <Badge className={getStatusColor(appointment.status || 'unknown')}>
                            {appointment.status || 'Unknown'}
                          </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground space-y-1">
                          <div className="flex items-center gap-4">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {appointment.startTime}
                            </span>
                            <span className="flex items-center gap-1">
                              <UserCheck className="h-3 w-3" />
                              Dr. {appointment.doctor.name}
                            </span>
                            {appointment.patient.phone && (
                              <span className="flex items-center gap-1">
                                <Phone className="h-3 w-3" />
                                {appointment.patient.phone}
                              </span>
                            )}
                          </div>
                          {appointment.reasonForVisit && (
                            <div className="flex items-center gap-1">
                              <FileText className="h-3 w-3" />
                              {appointment.reasonForVisit}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="ml-4 text-green-600 dark:text-green-400 text-sm font-medium">
                        ✓ Checked In
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}