import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { 
  Building2, 
  Clock, 
  User, 
  Calendar,
  UserCheck,
  AlertTriangle,
  Activity,
  ArrowLeft,
  UserX
} from "lucide-react";
import { Link } from "wouter";
import { useCenterName } from "@/hooks/useCenterName";
import { format, isToday } from "date-fns";
import { useState } from "react";
import { AuthStatus } from "@/components/auth/auth-status";

interface Department {
  id: number;
  name: string;
  headUserId: string | null;
}

interface Doctor {
  id: number;
  name: string;
  title: string;
  civilId: string;
  fileNumber: string;
}

interface Clinic {
  id: number;
  name: string;
  timeSlot: string;
  departmentId: number;
}

interface ClinicAssignment {
  id: number;
  clinicId: number;
  doctorId: number;
  weekday: string;
  isActive: boolean;
  clinic: Clinic;
  doctor: Doctor;
}

interface Permission {
  id: number;
  doctorId: number;
  date: string;
  timeType: string;
  reason: string;
  doctor: Doctor & { department: Department };
}

interface Leave {
  id: number;
  doctorId: number;
  startDate: string;
  endDate: string;
  type: string;
  reason: string;
  isActive: boolean;
  doctor: Doctor & { department: Department };
}

interface DepartmentWithClinics extends Department {
  todaysClinics: (ClinicAssignment & {
    clinic: Clinic;
    doctor: Doctor;
  })[];
}

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

export default function ControlCenter() {
  const { centerName } = useCenterName();
  const today = new Date();
  const todayWeekday = WEEKDAYS[today.getDay()];
  const todayDate = format(today, 'yyyy-MM-dd');
  const [leavesModalOpen, setLeavesModalOpen] = useState(false);
  const [permissionsModalOpen, setPermissionsModalOpen] = useState(false);

  const { data: departments = [], isLoading: isDepartmentsLoading, error: departmentsError } = useQuery<DepartmentWithClinics[]>({
    queryKey: [`/api/control-center/departments/${todayWeekday}`],
    retry: false, // Don't retry on auth errors
  });

  const { data: todaysPermissions = [], isLoading: isPermissionsLoading, error: permissionsError } = useQuery<Permission[]>({
    queryKey: [`/api/control-center/permissions/${todayDate}`],
    retry: false,
  });

  const { data: activeLeaves = [], isLoading: isLeavesLoading, error: leavesError } = useQuery<Leave[]>({
    queryKey: ['/api/control-center/leaves/active'],
    retry: false,
  });

  // Helper function to get department-specific permissions
  const getDepartmentPermissions = (departmentId: number) => {
    return todaysPermissions.filter(permission => 
      departments.find(dept => 
        dept.todaysClinics.some(clinic => clinic.doctorId === permission.doctorId)
      )?.id === departmentId
    );
  };

  // Helper function to get department-specific active leaves
  const getDepartmentLeaves = (departmentId: number) => {
    return activeLeaves.filter(leave => 
      departments.find(dept => 
        dept.todaysClinics.some(clinic => clinic.doctorId === leave.doctorId)
      )?.id === departmentId
    );
  };

  // Helper function to get department statistics
  const getDepartmentStats = (department: DepartmentWithClinics) => {
    const activeClinics = department.todaysClinics.filter(clinic => 
      isClinicActive(clinic.clinic.timeSlot)
    );
    const uniqueDoctors = new Set(department.todaysClinics.map(clinic => clinic.doctorId));
    const activeDoctors = new Set(activeClinics.map(clinic => clinic.doctorId));
    const deptPermissions = getDepartmentPermissions(department.id);
    const deptLeaves = getDepartmentLeaves(department.id);
    
    return {
      totalClinics: department.todaysClinics.length,
      activeClinics: activeClinics.length,
      totalDoctors: uniqueDoctors.size,
      activeDoctors: activeDoctors.size,
      permissions: deptPermissions.length,
      onLeave: deptLeaves.length
    };
  };

  const getCurrentTimeSlot = () => {
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();
    const currentTime = currentHour * 60 + currentMinute; // Convert to minutes

    if (currentTime >= 480 && currentTime < 720) { // 8:00 AM - 12:00 PM
      return "morning";
    } else if (currentTime >= 720 && currentTime < 960) { // 12:00 PM - 4:00 PM
      return "afternoon";
    } else if (currentTime >= 960 && currentTime < 1200) { // 4:00 PM - 8:00 PM
      return "evening";
    }
    return "closed";
  };

  const currentTimeSlot = getCurrentTimeSlot();

  const isClinicActive = (timeSlot: string | null | undefined) => {
    if (!timeSlot) return false;
    const lowerTimeSlot = timeSlot.toLowerCase();
    if (lowerTimeSlot.includes('morning') || lowerTimeSlot.includes('am')) return currentTimeSlot === 'morning';
    if (lowerTimeSlot.includes('afternoon') || lowerTimeSlot.includes('pm')) return currentTimeSlot === 'afternoon';
    if (lowerTimeSlot.includes('evening') || lowerTimeSlot.includes('night')) return currentTimeSlot === 'evening';
    return false;
  };

  // Check for authentication errors
  const hasAuthError = departmentsError || permissionsError || leavesError;
  const authErrorMessage = departmentsError?.message || permissionsError?.message || leavesError?.message;

  if (hasAuthError && authErrorMessage?.includes('Unauthorized')) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-8">
          <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
          <div className="text-lg font-semibold text-red-700">Access Denied</div>
          <p className="text-gray-600 mt-2">
            The Control Center requires Center Head privileges to access.
          </p>
          <div className="flex justify-center mt-6">
            <AuthStatus />
          </div>
          <Link href="/">
            <Button variant="outline" className="mt-4">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Home
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  if (hasAuthError) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-8">
          <AlertTriangle className="mx-auto h-12 w-12 text-orange-500 mb-4" />
          <div className="text-lg font-semibold text-orange-700">Error Loading Control Center</div>
          <p className="text-gray-600 mt-2">
            {authErrorMessage || 'Failed to load control center data'}
          </p>
          <Link href="/">
            <Button variant="outline" className="mt-4">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Home
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  if (isDepartmentsLoading || isPermissionsLoading || isLeavesLoading) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-8">
          <div className="text-lg">Loading control center...</div>
          {process.env.NODE_ENV === 'development' && (
            <div className="text-sm text-gray-500 mt-2">
              Departments: {isDepartmentsLoading ? 'Loading...' : 'Loaded'}, 
              Permissions: {isPermissionsLoading ? 'Loading...' : 'Loaded'}, 
              Leaves: {isLeavesLoading ? 'Loading...' : 'Loaded'}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link href="/">
            <Button variant="outline" size="sm">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Home
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold flex items-center">
              <Activity className="mr-3 h-8 w-8 text-blue-600" />
              Daily Control Center
            </h1>
            <p className="text-gray-600 mt-1">{centerName}</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-lg font-semibold">{format(today, 'EEEE, MMMM d, yyyy')}</div>
          <Badge variant={currentTimeSlot === 'closed' ? 'secondary' : 'default'} className="mt-1">
            {currentTimeSlot === 'morning' && 'Morning Shift (8:00 AM - 12:00 PM)'}
            {currentTimeSlot === 'afternoon' && 'Afternoon Shift (12:00 PM - 4:00 PM)'}
            {currentTimeSlot === 'evening' && 'Evening Shift (4:00 PM - 8:00 PM)'}
            {currentTimeSlot === 'closed' && 'Outside Operating Hours'}
          </Badge>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <Building2 className="h-8 w-8 text-blue-600 mr-3" />
              <div>
                <p className="text-sm font-medium text-gray-600">Active Departments</p>
                <p className="text-2xl font-bold">{departments.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <Clock className="h-8 w-8 text-green-600 mr-3" />
              <div>
                <p className="text-sm font-medium text-gray-600">Open Clinics</p>
                <p className="text-2xl font-bold">
                  {departments.reduce((total, dept) => 
                    total + dept.todaysClinics.filter(clinic => 
                      isClinicActive(clinic.clinic.timeSlot)
                    ).length, 0
                  )}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center">
              <UserCheck className="h-8 w-8 text-orange-600 mr-3" />
              <div>
                <p className="text-sm font-medium text-gray-600">Doctors on Duty</p>
                <p className="text-2xl font-bold">
                  {departments.reduce((total, dept) => 
                    total + new Set(dept.todaysClinics.filter(clinic => 
                      isClinicActive(clinic.clinic.timeSlot)
                    ).map(clinic => clinic.doctorId)).size, 0
                  )}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Dialog open={permissionsModalOpen} onOpenChange={setPermissionsModalOpen}>
          <DialogTrigger asChild>
            <Card className="cursor-pointer hover:shadow-lg transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-center">
                  <AlertTriangle className="h-8 w-8 text-orange-600 mr-3" />
                  <div>
                    <p className="text-sm font-medium text-gray-600">Permissions Today</p>
                    <p className="text-2xl font-bold">{todaysPermissions.length}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </DialogTrigger>
          <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center text-xl">
                <AlertTriangle className="mr-3 h-6 w-6 text-orange-600" />
                All Permissions for Today ({format(today, 'MMMM d, yyyy')})
              </DialogTitle>
            </DialogHeader>
            
            <div className="space-y-4 mt-4">
              {todaysPermissions.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No permissions scheduled for today
                </div>
              ) : (
                <div className="grid gap-4">
                  {todaysPermissions.map((permission) => {
                    return (
                      <div key={permission.id} className="p-4 border rounded-lg bg-orange-50 border-orange-200">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-3">
                            <div>
                              <h4 className="font-semibold text-gray-900">{permission.doctor.name}</h4>
                              <p className="text-sm text-gray-600">{permission.doctor.title}</p>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Badge variant="outline" className="bg-white border-orange-300 text-orange-700">
                              {permission.timeType.replace('_', ' ').toUpperCase()}
                            </Badge>
                            <Badge variant="outline" className="bg-white border-blue-300 text-blue-700">
                              {permission.doctor.department.name}
                            </Badge>
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                          <div className="flex items-center text-gray-700">
                            <Calendar className="h-4 w-4 mr-2 text-orange-600" />
                            <span>
                              <strong>Date:</strong> {format(new Date(permission.date), 'MMM d, yyyy')}
                            </span>
                          </div>
                          <div className="flex items-center text-gray-700">
                            <User className="h-4 w-4 mr-2 text-blue-600" />
                            <span>
                              <strong>File Number:</strong> {permission.doctor.fileNumber}
                            </span>
                          </div>
                        </div>
                        
                        {permission.reason && (
                          <div className="mt-3 p-3 bg-white rounded border">
                            <p className="text-sm">
                              <strong>Reason:</strong> {permission.reason}
                            </p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={leavesModalOpen} onOpenChange={setLeavesModalOpen}>
          <DialogTrigger asChild>
            <Card className="cursor-pointer hover:shadow-lg transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-center">
                  <UserX className="h-8 w-8 text-red-600 mr-3" />
                  <div>
                    <p className="text-sm font-medium text-gray-600">Doctors on Leave</p>
                    <p className="text-2xl font-bold">{activeLeaves.length}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </DialogTrigger>
          <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center text-xl">
                <UserX className="mr-3 h-6 w-6 text-red-600" />
                All Doctors Currently on Leave
              </DialogTitle>
            </DialogHeader>
            
            <div className="space-y-4 mt-4">
              {activeLeaves.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No doctors are currently on leave
                </div>
              ) : (
                <div className="grid gap-4">
                  {activeLeaves.map((leave) => {
                    return (
                      <div key={leave.id} className="p-4 border rounded-lg bg-red-50 border-red-200">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-3">
                            <div>
                              <h4 className="font-semibold text-gray-900">{leave.doctor.name}</h4>
                              <p className="text-sm text-gray-600">{leave.doctor.title}</p>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Badge variant="outline" className="bg-white border-red-300 text-red-700">
                              {leave.type.toUpperCase()} LEAVE
                            </Badge>
                            <Badge variant="outline" className="bg-white border-blue-300 text-blue-700">
                              {leave.doctor.department.name}
                            </Badge>
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                          <div className="flex items-center text-gray-700">
                            <Calendar className="h-4 w-4 mr-2 text-red-600" />
                            <span>
                              <strong>Duration:</strong> {format(new Date(leave.startDate), 'MMM d')} - {format(new Date(leave.endDate), 'MMM d, yyyy')}
                            </span>
                          </div>
                          <div className="flex items-center text-gray-700">
                            <User className="h-4 w-4 mr-2 text-blue-600" />
                            <span>
                              <strong>File Number:</strong> {leave.doctor.fileNumber}
                            </span>
                          </div>
                        </div>
                        
                        {leave.reason && (
                          <div className="mt-3 p-3 bg-white rounded border">
                            <p className="text-sm">
                              <strong>Reason:</strong> {leave.reason}
                            </p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Department-by-Department Breakdown */}
      <div className="space-y-8">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center">
          <Building2 className="mr-3 h-6 w-6 text-blue-600" />
          Department Breakdown
        </h2>
        
        {departments.map((department) => {
          const stats = getDepartmentStats(department);
          const deptPermissions = getDepartmentPermissions(department.id);
          const deptLeaves = getDepartmentLeaves(department.id);
          
          return (
            <Card key={department.id} className="overflow-hidden">
              <CardHeader className="bg-gradient-to-r from-blue-50 to-indigo-50 border-b">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center text-xl">
                    <Building2 className="mr-3 h-6 w-6 text-blue-600" />
                    {department.name}
                  </CardTitle>
                  <div className="flex space-x-2">
                    <Badge variant="outline" className="bg-white">
                      {stats.activeClinics}/{stats.totalClinics} Active Clinics
                    </Badge>
                    <Badge variant="outline" className="bg-white">
                      {stats.activeDoctors}/{stats.totalDoctors} Doctors on Duty
                    </Badge>
                    {stats.permissions > 0 && (
                      <Badge variant="destructive" className="bg-orange-100 text-orange-800 border-orange-300">
                        {stats.permissions} Permission{stats.permissions > 1 ? 's' : ''}
                      </Badge>
                    )}
                    {stats.onLeave > 0 && (
                      <Badge variant="destructive" className="bg-red-100 text-red-800 border-red-300">
                        {stats.onLeave} On Leave
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              
              <CardContent className="p-6">
                {/* Department Statistics */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
                  <div className="text-center p-3 bg-blue-50 rounded-lg">
                    <div className="text-2xl font-bold text-blue-600">{stats.totalClinics}</div>
                    <div className="text-sm text-gray-600">Total Clinics</div>
                  </div>
                  <div className="text-center p-3 bg-green-50 rounded-lg">
                    <div className="text-2xl font-bold text-green-600">{stats.activeClinics}</div>
                    <div className="text-sm text-gray-600">Active Now</div>
                  </div>
                  <div className="text-center p-3 bg-purple-50 rounded-lg">
                    <div className="text-2xl font-bold text-purple-600">{stats.totalDoctors}</div>
                    <div className="text-sm text-gray-600">Assigned Doctors</div>
                  </div>
                  <div className="text-center p-3 bg-orange-50 rounded-lg">
                    <div className="text-2xl font-bold text-orange-600">{stats.permissions}</div>
                    <div className="text-sm text-gray-600">Permissions</div>
                  </div>
                  <div className="text-center p-3 bg-red-50 rounded-lg">
                    <div className="text-2xl font-bold text-red-600">{stats.onLeave}</div>
                    <div className="text-sm text-gray-600">On Leave</div>
                  </div>
                </div>

                {/* Today's Clinics */}
                <div className="space-y-4">
                  <h4 className="font-semibold text-gray-900 flex items-center">
                    <Clock className="mr-2 h-5 w-5" />
                    Today's Clinic Schedule
                  </h4>
                  {department.todaysClinics.length === 0 ? (
                    <div className="text-center py-6 text-gray-500 bg-gray-50 rounded-lg">
                      No clinics scheduled for today
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {department.todaysClinics.map((assignment) => (
                        <div 
                          key={assignment.id} 
                          className={`p-4 rounded-lg border-2 transition-all ${
                            isClinicActive(assignment.clinic.timeSlot) 
                              ? 'bg-green-50 border-green-300 shadow-md' 
                              : 'bg-gray-50 border-gray-200'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-3">
                            <h5 className="font-semibold text-gray-900">{assignment.clinic.name}</h5>
                            <Badge 
                              variant={isClinicActive(assignment.clinic.timeSlot) ? 'default' : 'secondary'}
                              className={`text-xs font-medium ${
                                isClinicActive(assignment.clinic.timeSlot) ? 'bg-green-600' : ''
                              }`}
                            >
                              {isClinicActive(assignment.clinic.timeSlot) ? 'ACTIVE NOW' : 'SCHEDULED'}
                            </Badge>
                          </div>
                          <div className="flex items-center text-sm text-gray-600 mb-2">
                            <User className="h-4 w-4 mr-2 text-blue-600" />
                            <div>
                              <div className="font-medium text-gray-900">{assignment.doctor.name}</div>
                              <div className="text-xs text-gray-500">{assignment.doctor.title}</div>
                            </div>
                          </div>
                          <div className="flex items-center text-sm text-gray-600">
                            <Clock className="h-4 w-4 mr-2 text-green-600" />
                            <span className="font-medium">{assignment.clinic.timeSlot}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Department Permissions */}
                {deptPermissions.length > 0 && (
                  <div className="mt-6 space-y-4">
                    <h4 className="font-semibold text-gray-900 flex items-center">
                      <AlertTriangle className="mr-2 h-5 w-5 text-orange-600" />
                      Today's Permissions in {department.name}
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {deptPermissions.map((permission) => (
                        <div key={permission.id} className="p-4 bg-orange-50 rounded-lg border border-orange-200">
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-semibold text-gray-900">{permission.doctor.name}</span>
                            <Badge variant="outline" className="text-xs bg-white border-orange-300">
                              {permission.timeType}
                            </Badge>
                          </div>
                          <p className="text-sm text-gray-700">{permission.reason}</p>
                          <p className="text-xs text-gray-500 mt-1">
                            {permission.doctor.title} • File: {permission.doctor.fileNumber}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Department Active Leaves */}
                {deptLeaves.length > 0 && (
                  <div className="mt-6 space-y-4">
                    <h4 className="font-semibold text-gray-900 flex items-center">
                      <UserX className="mr-2 h-5 w-5 text-red-600" />
                      Doctors Currently on Leave in {department.name}
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {deptLeaves.map((leave) => (
                        <div key={leave.id} className="p-4 bg-red-50 rounded-lg border border-red-200">
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-semibold text-gray-900">{leave.doctor.name}</span>
                            <Badge variant="outline" className="text-xs bg-white border-red-300 text-red-700">
                              {leave.type.toUpperCase()} LEAVE
                            </Badge>
                          </div>
                          <div className="flex items-center text-sm text-gray-700 mb-2">
                            <Calendar className="h-4 w-4 mr-2 text-red-600" />
                            <span>{format(new Date(leave.startDate), 'MMM d')} - {format(new Date(leave.endDate), 'MMM d, yyyy')}</span>
                          </div>
                          {leave.reason && (
                            <p className="text-sm text-gray-700 mb-2">{leave.reason}</p>
                          )}
                          <p className="text-xs text-gray-500">
                            {leave.doctor.title} • File: {leave.doctor.fileNumber}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}