import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { Navigation } from "@/components/layout/navigation";
import { DoctorManagement } from "@/components/doctors/doctor-management";
import { ClinicAssignment } from "@/components/clinics/clinic-assignment";
import { EmergencyManagement } from "@/components/emergency/emergency-management";
import { LeavePermissions } from "@/components/leave/leave-permissions";
import { ExaminationClinics } from "@/components/examination/examination-clinics";
import { PrintReports } from "@/components/reports/print-reports";
import { useQuery } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { 
  Users, 
  CheckCircle, 
  Plane, 
  Ambulance, 
  ChartLine, 
  Clock,
  AlertCircle,
  SkipForward,
  RotateCcw
} from "lucide-react";
import { formatDate, getTodayWeekday } from "@/lib/date-utils";

type Tab = "dashboard" | "doctors" | "clinics" | "appointments" | "emergency" | "leave" | "examination" | "reports";

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [departmentId, setDepartmentId] = useState<number | null>(null);
  const [skippedDoctorIds, setSkippedDoctorIds] = useState<number[]>([]);
  const [showEmergencyDialog, setShowEmergencyDialog] = useState(false);
  const [emergencyPatientName, setEmergencyPatientName] = useState("");
  const [emergencyType, setEmergencyType] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { toast } = useToast();

  // Get department ID from URL parameters or localStorage
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const deptParam = urlParams.get('dept');
    const storedDeptId = localStorage.getItem("selectedDepartmentId");
    
    if (deptParam) {
      const deptId = parseInt(deptParam);
      setDepartmentId(deptId);
      localStorage.setItem("selectedDepartmentId", deptParam);
    } else if (storedDeptId) {
      setDepartmentId(parseInt(storedDeptId));
    }
  }, []);

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: departmentId ? ["/api/dashboard/stats", departmentId] : ["/api/dashboard/stats"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/dashboard/stats${params}`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      return response.json();
    },
  });

  const { data: todayClinicAssignments, isLoading: clinicAssignmentsLoading } = useQuery({
    queryKey: departmentId ? ["/api/clinic-assignments/weekday", getTodayWeekday(), departmentId] : ["/api/clinic-assignments/weekday", getTodayWeekday()],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/clinic-assignments/weekday/${getTodayWeekday()}${params}`);
      if (!response.ok) throw new Error('Failed to fetch clinic assignments');
      return response.json();
    },
  });

  const { data: activeLeaves, isLoading: leavesLoading } = useQuery({
    queryKey: departmentId ? ["/api/leaves/active", departmentId] : ["/api/leaves/active"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/leaves/active${params}`);
      if (!response.ok) throw new Error('Failed to fetch active leaves');
      return response.json();
    },
  });

  const { data: todayPermissions, isLoading: permissionsLoading } = useQuery({
    queryKey: departmentId ? ["/api/permissions/month", new Date().getFullYear(), new Date().getMonth() + 1, departmentId] : ["/api/permissions/month", new Date().getFullYear(), new Date().getMonth() + 1],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/permissions/month/${new Date().getFullYear()}/${new Date().getMonth() + 1}${params}`);
      if (!response.ok) throw new Error('Failed to fetch permissions');
      return response.json();
    },
  });

  const { data: nextEmergencyDoctor, isLoading: emergencyDoctorLoading } = useQuery({
    queryKey: departmentId ? 
      ["/api/emergency-assignments/next-doctor", departmentId, skippedDoctorIds.join(',')] : 
      ["/api/emergency-assignments/next-doctor", skippedDoctorIds.join(',')],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (departmentId) params.append('departmentId', departmentId.toString());
      if (skippedDoctorIds.length > 0) params.append('skipDoctorIds', skippedDoctorIds.join(','));
      
      const response = await fetch(`/api/emergency-assignments/next-doctor?${params}`);
      if (!response.ok) throw new Error('Failed to fetch next emergency doctor');
      return response.json();
    },
  });

  const { data: todayExaminationSlots, isLoading: examinationSlotsLoading } = useQuery({
    queryKey: departmentId ? ["/api/examination-slots/weekday", getTodayWeekday(), departmentId] : ["/api/examination-slots/weekday", getTodayWeekday()],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/examination-slots/weekday/${getTodayWeekday()}${params}`);
      if (!response.ok) throw new Error('Failed to fetch examination slots');
      return response.json();
    },
  });

  const handleOpenEmergencyDialog = () => {
    if (!nextEmergencyDoctor) {
      toast({
        title: "No Available Doctor",
        description: "No doctor is available for emergency assignment right now.",
        variant: "destructive",
      });
      return;
    }
    setShowEmergencyDialog(true);
  };

  const handleAssignEmergency = async () => {
    if (!emergencyPatientName.trim() || !emergencyType) {
      toast({
        title: "Missing Information",
        description: "Please enter patient name and select emergency type.",
        variant: "destructive",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch("/api/emergency-assignments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doctorId: nextEmergencyDoctor?.id,
          assignedDate: new Date().toISOString().split('T')[0],
          assignedTime: new Date().toTimeString().split(' ')[0],
          emergencyNumber: Math.floor(Math.random() * 1000) + 1,
          patientName: emergencyPatientName.trim(),
          emergencyType: emergencyType,
          notes: "",
        }),
      });

      if (response.ok) {
        // Clear skipped doctors after successful assignment
        setSkippedDoctorIds([]);
        setShowEmergencyDialog(false);
        setEmergencyPatientName("");
        setEmergencyType("");
        
        // Invalidate queries with proper department context
        if (departmentId) {
          queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/next-doctor", departmentId] });
          queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/stats", departmentId] });
        } else {
          queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/next-doctor"] });
          queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/stats"] });
        }
        queryClient.invalidateQueries({ queryKey: ["/api/dashboard/stats"] });
        
        toast({
          title: "Emergency Assigned",
          description: `Dr. ${nextEmergencyDoctor?.name} has been assigned to the emergency.`,
        });
      } else {
        const errorData = await response.json();
        throw new Error(errorData.message || "Failed to assign emergency");
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to assign emergency doctor.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkipEmergencyDoctor = () => {
    if (nextEmergencyDoctor && !skippedDoctorIds.includes(nextEmergencyDoctor.id)) {
      setSkippedDoctorIds(prev => [...prev, nextEmergencyDoctor.id]);
      toast({
        title: "Doctor Skipped",
        description: `Dr. ${nextEmergencyDoctor.name} has been skipped. Getting next available doctor.`,
      });
    }
  };

  const handleResetEmergencySkips = () => {
    setSkippedDoctorIds([]);
    toast({
      title: "Reset Complete",
      description: "All skipped doctors are now available again.",
    });
  };

  const renderDashboardContent = () => {
    if (statsLoading) return <Skeleton className="h-32" />;

    const todayDate = new Date().toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });

    // Calculate examination coverage stats
    const totalExamSlots = todayExaminationSlots?.length || 0;
    const coveredExamSlots = todayExaminationSlots?.filter((slot: any) => 
      slot.assignments && slot.assignments.length > 0
    ).length || 0;

    return (
      <div className="space-y-8">
        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Doctors</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats?.totalDoctors || 0}</p>
                </div>
                <div className="w-12 h-12 bg-medical-blue/10 rounded-lg flex items-center justify-center">
                  <Users className="text-medical-blue" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Available Today</p>
                  <p className="text-2xl font-semibold text-healthcare-green">{stats?.availableToday || 0}</p>
                </div>
                <div className="w-12 h-12 bg-healthcare-green/10 rounded-lg flex items-center justify-center">
                  <CheckCircle className="text-healthcare-green" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">On Leave</p>
                  <p className="text-2xl font-semibold text-warning-orange">{stats?.onLeave || 0}</p>
                </div>
                <div className="w-12 h-12 bg-warning-orange/10 rounded-lg flex items-center justify-center">
                  <Plane className="text-warning-orange" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Emergency Calls</p>
                  <p className="text-2xl font-semibold text-red-600">{stats?.emergencyCalls || 0}</p>
                </div>
                <div className="w-12 h-12 bg-red-50 rounded-lg flex items-center justify-center">
                  <Ambulance className="text-red-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Exam Coverage</p>
                  <p className="text-2xl font-semibold text-purple-600">{coveredExamSlots}/{totalExamSlots}</p>
                </div>
                <div className="w-12 h-12 bg-purple-50 rounded-lg flex items-center justify-center">
                  <Clock className="text-purple-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Today's Clinic Coverage */}
          <Card>
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold text-gray-900">Today's Clinic Coverage</h3>
              <p className="text-sm text-gray-600 mt-1">{todayDate}</p>
            </div>
            <CardContent className="p-6">
              {clinicAssignmentsLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-16" />
                  <Skeleton className="h-16" />
                  <Skeleton className="h-16" />
                </div>
              ) : (
                <div className="space-y-4">
                  {todayClinicAssignments?.length ? (
                    todayClinicAssignments.map((assignment: any) => (
                      <div key={assignment.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                        <div className="flex items-center">
                          <div className="w-3 h-3 bg-healthcare-green rounded-full mr-3"></div>
                          <div>
                            <h4 className="text-sm font-medium text-gray-900">{assignment.clinic.name}</h4>
                            <p className="text-sm text-gray-600">{assignment.clinic.startTime} - {assignment.clinic.endTime}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-medium text-gray-900">{assignment.doctor.name}</p>
                          <p className="text-xs text-gray-500">{assignment.doctor.title}</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8">
                      <AlertCircle className="mx-auto h-12 w-12 text-gray-400" />
                      <p className="mt-2 text-sm text-gray-500">No clinic assignments for today</p>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Doctor Status */}
          <Card>
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold text-gray-900">Doctor Status Today</h3>
              <p className="text-sm text-gray-600 mt-1">Real-time availability</p>
            </div>
            <CardContent className="p-6">
              {leavesLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-16" />
                  <Skeleton className="h-16" />
                  <Skeleton className="h-16" />
                </div>
              ) : (
                <div className="space-y-3">
                  {activeLeaves?.map((leave: any) => (
                    <div key={leave.id} className="flex items-center justify-between">
                      <div className="flex items-center">
                        <div className="w-10 h-10 bg-medical-blue/10 rounded-full flex items-center justify-center mr-3">
                          <Users className="text-medical-blue text-sm" />
                        </div>
                        <div>
                          <h4 className="text-sm font-medium text-gray-900">{leave.doctor.name}</h4>
                          <p className="text-xs text-gray-500">{leave.doctor.title}</p>
                        </div>
                      </div>
                      <Badge variant="destructive">On Leave</Badge>
                    </div>
                  ))}
                  {(!activeLeaves || activeLeaves.length === 0) && (
                    <div className="text-center py-8">
                      <CheckCircle className="mx-auto h-12 w-12 text-healthcare-green" />
                      <p className="mt-2 text-sm text-gray-500">All doctors are available today</p>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Examination Clinic Coverage */}
          <Card>
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold text-gray-900">Examination Clinic Coverage</h3>
              <p className="text-sm text-gray-600 mt-1">Today's examination slots and assignments</p>
            </div>
            <CardContent className="p-6">
              {examinationSlotsLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-16" />
                  <Skeleton className="h-16" />
                  <Skeleton className="h-16" />
                </div>
              ) : (
                <div className="space-y-3">
                  {todayExaminationSlots?.map((slot: any) => (
                    <div key={slot.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center">
                          <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center mr-3">
                            <Clock className="text-purple-600 text-sm" />
                          </div>
                          <div>
                            <h4 className="text-sm font-medium text-gray-900">
                              {slot.startTime} - {slot.endTime}
                            </h4>
                            <p className="text-xs text-gray-500">
                              Max {slot.maxDoctors} doctor{slot.maxDoctors !== 1 ? 's' : ''}
                            </p>
                          </div>
                        </div>
                        <Badge variant="outline" className={
                          slot.assignments && slot.assignments.length > 0 
                            ? "bg-healthcare-green/10 text-healthcare-green" 
                            : "bg-yellow-100 text-yellow-600"
                        }>
                          {slot.assignments && slot.assignments.length > 0 
                            ? `${slot.assignments.length}/${slot.maxDoctors} assigned` 
                            : 'No coverage'
                          }
                        </Badge>
                      </div>
                      {slot.assignments && slot.assignments.length > 0 && (
                        <div className="mt-3 space-y-2">
                          {slot.assignments.map((assignment: any) => (
                            <div key={assignment.id} className="flex items-center">
                              <div className="w-2 h-2 bg-healthcare-green rounded-full mr-2"></div>
                              <span className="text-sm text-gray-700">{assignment.doctor.name}</span>
                              <span className="text-xs text-gray-500 ml-2">({assignment.doctor.title})</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )) || (
                    <div className="text-center py-8">
                      <AlertCircle className="mx-auto h-12 w-12 text-gray-400" />
                      <p className="mt-2 text-sm text-gray-500">No examination slots scheduled for today</p>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Emergency Assignment */}
        <Card>
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold text-gray-900">Emergency Assignment</h3>
            <p className="text-sm text-gray-600 mt-1">Quick assignment for walk-in emergencies</p>
          </div>
          <CardContent className="p-6">
            {emergencyDoctorLoading ? (
              <Skeleton className="h-16" />
            ) : (
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <div className="w-12 h-12 bg-red-50 rounded-lg flex items-center justify-center mr-4">
                    <Ambulance className="text-red-600" />
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-gray-900">Next Available Doctor</h4>
                    <p className="text-sm text-gray-600">
                      {nextEmergencyDoctor ? `Dr. ${nextEmergencyDoctor.name}` : "No available doctor"}
                    </p>
                  </div>
                </div>
                <div className="flex space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleSkipEmergencyDoctor}
                    disabled={!nextEmergencyDoctor}
                    className="text-orange-600 border-orange-600 hover:bg-orange-50"
                  >
                    <SkipForward className="mr-2 h-4 w-4" />
                    Skip
                  </Button>
                  <Button 
                    onClick={handleOpenEmergencyDialog}
                    disabled={!nextEmergencyDoctor}
                    className="bg-red-600 hover:bg-red-700"
                    data-testid="button-assign-emergency"
                  >
                    <Ambulance className="mr-2 h-4 w-4" />
                    Assign Emergency
                  </Button>
                </div>
              </div>
            )}
            
            {/* Skipped Doctors Section */}
            {skippedDoctorIds.length > 0 && (
              <div className="mt-4 bg-orange-50 rounded-lg p-4 border border-orange-200">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-orange-900">Skipped Doctors ({skippedDoctorIds.length})</h4>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleResetEmergencySkips}
                    className="text-orange-700 border-orange-300 hover:bg-orange-100"
                  >
                    <RotateCcw className="mr-2 h-4 w-4" />
                    Reset All
                  </Button>
                </div>
                <p className="text-sm text-orange-700">
                  These doctors have been temporarily skipped. Click "Reset All" to make them available again.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  };

  const centerId = localStorage.getItem("selectedCenterId") || "";

  // Get department info for header — scoped to the selected center
  const { data: userDepartments = [] } = useQuery<any[]>({
    queryKey: ["/api/user/departments", centerId],
    queryFn: async () => {
      const url = centerId ? `/api/user/departments?centerId=${centerId}` : "/api/user/departments";
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch departments");
      return res.json();
    },
  });
  
  const currentDepartment = userDepartments.find((dept: any) => dept.id === departmentId);

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentDepartment && (
          <div className="mb-6 p-4 bg-white rounded-lg shadow-sm border-l-4 border-medical-blue">
            <h2 className="text-lg font-semibold text-gray-900">{currentDepartment.name} - Dashboard</h2>
            <p className="text-sm text-gray-600 mt-1">Department management and operations</p>
          </div>
        )}
        <Navigation activeTab={activeTab} onTabChange={setActiveTab} />
        
        <div className="mt-8">
          {activeTab === "dashboard" && renderDashboardContent()}
          {activeTab === "doctors" && <DoctorManagement departmentId={departmentId || undefined} />}
          {activeTab === "clinics" && <ClinicAssignment departmentId={departmentId || undefined} />}
          {activeTab === "appointments" && <div className="space-y-6"><h2 className="text-2xl font-bold">Appointment Management</h2><p className="text-gray-600">Manage patient appointments, available time slots, and doctor schedules.</p><div className="bg-blue-50 p-4 rounded-lg"><p className="text-blue-800">This feature allows you to schedule patient appointments, manage doctor availability, and track appointment status.</p></div></div>}
          {activeTab === "emergency" && <EmergencyManagement departmentId={departmentId || undefined} />}
          {activeTab === "leave" && <LeavePermissions departmentId={departmentId || undefined} />}
          {activeTab === "examination" && <ExaminationClinics departmentId={departmentId || undefined} />}
          {activeTab === "reports" && <PrintReports />}
        </div>
      </div>

      {/* Emergency Assignment Dialog */}
      <Dialog open={showEmergencyDialog} onOpenChange={setShowEmergencyDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Ambulance className="h-5 w-5 text-red-600" />
              Assign Emergency to Dr. {nextEmergencyDoctor?.name}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="patientName">Patient Name *</Label>
              <Input
                id="patientName"
                placeholder="Enter patient name"
                value={emergencyPatientName}
                onChange={(e) => setEmergencyPatientName(e.target.value)}
                data-testid="input-emergency-patient-name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="emergencyType">Emergency Type *</Label>
              <Select value={emergencyType} onValueChange={setEmergencyType}>
                <SelectTrigger data-testid="select-emergency-type">
                  <SelectValue placeholder="Select emergency type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Pain">Pain</SelectItem>
                  <SelectItem value="Swelling">Swelling</SelectItem>
                  <SelectItem value="Trauma">Trauma</SelectItem>
                  <SelectItem value="Bleeding">Bleeding</SelectItem>
                  <SelectItem value="Broken Restoration">Broken Restoration</SelectItem>
                  <SelectItem value="Lost Crown/Bridge">Lost Crown/Bridge</SelectItem>
                  <SelectItem value="Denture Issue">Denture Issue</SelectItem>
                  <SelectItem value="Other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {(nextEmergencyDoctor as any)?.currentClinic && (
              <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
                <p className="text-sm text-blue-800">
                  <strong>Location:</strong> {(nextEmergencyDoctor as any).currentClinic.name}
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowEmergencyDialog(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAssignEmergency}
              disabled={isSubmitting || !emergencyPatientName.trim() || !emergencyType}
              className="bg-red-600 hover:bg-red-700"
              data-testid="button-confirm-emergency"
            >
              {isSubmitting ? "Assigning..." : "Confirm Assignment"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
