import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Building, Plus, Users, Calendar, Settings, Activity, BarChart3, Trophy, Hospital, Clock, PhoneCall } from "lucide-react";
import { Link } from "wouter";
import { useAuth } from "@/hooks/useAuth";
import type { Department, Center } from "@shared/schema";
import { CreateDepartmentDialog } from "@/components/departments/create-department-dialog";
import { CreateUserDialog } from "@/components/admin/create-user-dialog";
import { CreateCenterDialog } from "@/components/centers/create-center-dialog";
import DoctorOfTheMonthManager from "@/components/doctor-of-month/DoctorOfTheMonthManager";
import CallCenterCodeCard from "@/components/callcenter/CallCenterCodeCard";

export default function Home() {
  const { user } = useAuth();
  const [selectedCenterId, setSelectedCenterId] = useState<string>("");
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string>("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showCreateUserDialog, setShowCreateUserDialog] = useState(false);
  const [showCreateCenterDialog, setShowCreateCenterDialog] = useState(false);

  const { data: userCenters = [], isLoading: isCentersLoading } = useQuery<Center[]>({
    queryKey: ["/api/user/centers"],
  });

  const { data: userDepartments = [], isLoading: isDepartmentsLoading } = useQuery<Department[]>({
    queryKey: ["/api/user/departments", selectedCenterId],
    queryFn: async () => {
      const url = selectedCenterId 
        ? `/api/user/departments?centerId=${selectedCenterId}`
        : "/api/user/departments";
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch departments");
      return res.json();
    },
    enabled: !!selectedCenterId,
  });

  const selectedCenter = userCenters.find(c => c.id.toString() === selectedCenterId);
  const selectedDepartment = userDepartments.find(dept => dept.id.toString() === selectedDepartmentId);

  useEffect(() => {
    const stored = localStorage.getItem("selectedCenterId");
    if (stored && userCenters.some(c => c.id.toString() === stored)) {
      setSelectedCenterId(stored);
    } else if (userCenters.length > 0 && !selectedCenterId) {
      setSelectedCenterId(userCenters[0].id.toString());
      localStorage.setItem("selectedCenterId", userCenters[0].id.toString());
    }
  }, [userCenters]);

  useEffect(() => {
    if (!selectedCenterId) return;
    const stored = localStorage.getItem("selectedDepartmentId");
    if (stored && userDepartments.some(d => d.id.toString() === stored)) {
      setSelectedDepartmentId(stored);
    } else if (userDepartments.length > 0) {
      setSelectedDepartmentId(userDepartments[0].id.toString());
    } else {
      setSelectedDepartmentId("");
    }
  }, [userDepartments, selectedCenterId]);

  const handleCenterSelect = (centerId: string) => {
    setSelectedCenterId(centerId);
    setSelectedDepartmentId("");
    localStorage.setItem("selectedCenterId", centerId);
  };

  const handleDepartmentSelect = (departmentId: string) => {
    setSelectedDepartmentId(departmentId);
    localStorage.setItem("selectedDepartmentId", departmentId);
  };

  if (isCentersLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-300">Loading your centers...</p>
        </div>
      </div>
    );
  }

  if (userCenters.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="text-center py-16">
            <Hospital className="mx-auto h-16 w-16 text-gray-400 mb-6" />
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">
              Welcome to the Management System
            </h1>
            <p className="text-xl text-gray-600 dark:text-gray-300 mb-8 max-w-2xl mx-auto">
              You're not a member of any centers yet. 
              {(user as any)?.isCenterHead 
                ? " Create your first center to get started."
                : " Please contact your administrator to be added to a center."
              }
            </p>
            {(user as any)?.isCenterHead && (
              <Button 
                size="lg" 
                onClick={() => setShowCreateCenterDialog(true)}
                className="px-8 py-4"
              >
                <Plus className="mr-2 h-5 w-5" />
                Create Your First Center
              </Button>
            )}
          </div>
        </div>
        <CreateCenterDialog 
          open={showCreateCenterDialog} 
          onOpenChange={setShowCreateCenterDialog} 
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="glass-effect shadow-lg border-b border-white/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-20">
            <div className="flex items-center space-x-4">
              <div className="p-2 medical-gradient rounded-xl">
                <Hospital className="h-8 w-8 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-teal-600 bg-clip-text text-transparent">
                  {selectedCenter?.name || "Select a Center"}
                </h1>
                {userCenters.length > 1 && (
                  <p className="text-xs text-gray-500">{userCenters.length} centers available</p>
                )}
              </div>
            </div>
            
            <div className="flex items-center space-x-3">
              {userCenters.length > 1 && (
                <Select value={selectedCenterId} onValueChange={handleCenterSelect}>
                  <SelectTrigger className="w-56">
                    <Hospital className="h-4 w-4 mr-2 text-blue-600" />
                    <SelectValue placeholder="Select center" />
                  </SelectTrigger>
                  <SelectContent>
                    {userCenters.map((center) => (
                      <SelectItem key={center.id} value={center.id.toString()}>
                        {center.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}

              {selectedCenterId && userDepartments.length > 0 && (
                <Select value={selectedDepartmentId} onValueChange={handleDepartmentSelect}>
                  <SelectTrigger className="w-64">
                    <SelectValue placeholder="Select a department" />
                  </SelectTrigger>
                  <SelectContent>
                    {userDepartments.map((dept) => (
                      <SelectItem key={dept.id} value={dept.id.toString()}>
                        <div className="flex items-center space-x-2">
                          <span>{dept.name}</span>
                          {dept.headUserId === (user as any)?.id && (
                            <Badge variant="secondary" className="text-xs">Head</Badge>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              
              <div className="flex items-center space-x-2">
                {selectedCenterId && (
                  <Button variant="outline" onClick={() => setShowCreateDialog(true)} className="border-medical-blue/20 hover:bg-medical-blue/10">
                    <Plus className="mr-2 h-4 w-4 text-medical-blue" />
                    New Dept
                  </Button>
                )}
                
                {(user as any)?.isCenterHead && (
                  <>
                    <Button variant="outline" onClick={() => setShowCreateCenterDialog(true)} className="border-teal-200 hover:bg-teal-50 text-teal-600">
                      <Hospital className="mr-2 h-4 w-4" />
                      New Center
                    </Button>
                    <Button variant="outline" onClick={() => setShowCreateUserDialog(true)} className="border-healthcare-green/20 hover:bg-healthcare-green/10">
                      <Users className="mr-2 h-4 w-4 text-healthcare-green" />
                      Create User
                    </Button>
                    <Link href="/control-center">
                      <Button className="btn-gradient">
                        <Activity className="mr-2 h-4 w-4" />
                        Control Center
                      </Button>
                    </Link>
                    <Link href="/admin">
                      <Button variant="outline" className="border-medical-purple/20 hover:bg-medical-purple/10">
                        <Settings className="mr-2 h-4 w-4 text-medical-purple" />
                        Admin Panel
                      </Button>
                    </Link>
                  </>
                )}
                
                <Button variant="outline" onClick={() => window.location.href = "/api/logout"}>
                  Sign Out
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {isDepartmentsLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : selectedDepartment ? (
          <div className="space-y-10">
            <div className="glass-effect rounded-2xl shadow-xl p-8">
              <h2 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-teal-600 bg-clip-text text-transparent mb-3">
                {selectedDepartment.name}
              </h2>
              {selectedDepartment.description && (
                <p className="text-gray-600 text-lg mb-6">
                  {selectedDepartment.description}
                </p>
              )}
              {selectedDepartment.headUserId === (user as any)?.id && (
                <Badge className="bg-medical-blue text-white px-4 py-2 text-sm">
                  Department Head
                </Badge>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              <Card className="card-hover glass-effect rounded-2xl overflow-hidden">
                <CardHeader className="pb-4">
                  <div className="p-3 bg-medical-blue/10 rounded-xl w-fit mb-4">
                    <Users className="h-8 w-8 text-medical-blue" />
                  </div>
                  <CardTitle className="text-xl">Doctor Management</CardTitle>
                  <CardDescription className="text-gray-600">
                    Manage doctor profiles, assignments, and availability
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button 
                    className="w-full btn-gradient" 
                    onClick={() => {
                      localStorage.setItem("selectedDepartmentId", selectedDepartmentId);
                      window.location.href = `/dashboard?dept=${selectedDepartmentId}`;
                    }}
                  >
                    Open Dashboard
                  </Button>
                </CardContent>
              </Card>

              <Card className="card-hover glass-effect rounded-2xl overflow-hidden">
                <CardHeader className="pb-4">
                  <div className="p-3 bg-healthcare-green/10 rounded-xl w-fit mb-4">
                    <Calendar className="h-8 w-8 text-healthcare-green" />
                  </div>
                  <CardTitle className="text-xl">Clinic Scheduling</CardTitle>
                  <CardDescription className="text-gray-600">
                    Weekly assignments and examination scheduling
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button 
                    variant="outline" 
                    className="w-full border-healthcare-green/20 hover:bg-healthcare-green/10 text-healthcare-green"
                    onClick={() => {
                      localStorage.setItem("selectedDepartmentId", selectedDepartmentId);
                      window.location.href = `/dashboard?dept=${selectedDepartmentId}`;
                    }}
                  >
                    View Schedules
                  </Button>
                </CardContent>
              </Card>

              <Card className="card-hover glass-effect rounded-2xl overflow-hidden">
                <CardHeader className="pb-4">
                  <div className="p-3 bg-indigo-100 rounded-xl w-fit mb-4">
                    <Building className="h-8 w-8 text-indigo-600" />
                  </div>
                  <CardTitle className="text-xl">Clinic Overview</CardTitle>
                  <CardDescription className="text-gray-600">
                    Visual display of all clinics with doctor assignments
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Link href={`/clinic-overview?dept=${selectedDepartmentId}`}>
                    <Button 
                      variant="outline" 
                      className="w-full border-indigo-200 hover:bg-indigo-50 text-indigo-600"
                    >
                      View Clinics
                    </Button>
                  </Link>
                </CardContent>
              </Card>

              <Card className="card-hover glass-effect rounded-2xl overflow-hidden">
                <CardHeader className="pb-4">
                  <div className="p-3 bg-blue-100 rounded-xl w-fit mb-4">
                    <Building className="h-8 w-8 text-blue-700" />
                  </div>
                  <CardTitle className="text-xl">Clinic Day Schedule</CardTitle>
                  <CardDescription className="text-gray-600">
                    Live view of all clinics for any day — patients, free slots, and the ability to add patients
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Link href="/clinic-day">
                    <Button className="w-full bg-blue-600 hover:bg-blue-700 text-white">
                      Open Day Schedule
                    </Button>
                  </Link>
                </CardContent>
              </Card>

              <Card className="card-hover glass-effect rounded-2xl overflow-hidden">
                <CardHeader className="pb-4">
                  <div className="p-3 bg-orange-100 rounded-xl w-fit mb-4">
                    <Clock className="h-8 w-8 text-orange-600" />
                  </div>
                  <CardTitle className="text-xl">Overtime Portal</CardTitle>
                  <CardDescription className="text-gray-600">
                    Schedule patients for overtime clinics and manage overtime sessions
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Link href="/overtime">
                    <Button variant="outline" className="w-full border-orange-200 hover:bg-orange-50 text-orange-600">
                      Open Overtime Portal
                    </Button>
                  </Link>
                </CardContent>
              </Card>

              <Card className="card-hover glass-effect rounded-2xl overflow-hidden">
                <CardHeader className="pb-4">
                  <div className="p-3 bg-violet-100 rounded-xl w-fit mb-4">
                    <PhoneCall className="h-8 w-8 text-violet-600" />
                  </div>
                  <CardTitle className="text-xl">Exam Schedule</CardTitle>
                  <CardDescription className="text-gray-600">
                    View the weekly examination appointment schedule managed by the call center
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Link href={selectedDepartment ? `/exam-schedule?dept=${selectedDepartment.id}&deptName=${encodeURIComponent(selectedDepartment.name)}` : "/exam-schedule"}>
                    <Button variant="outline" className="w-full border-violet-200 hover:bg-violet-50 text-violet-600">
                      View Exam Schedule
                    </Button>
                  </Link>
                </CardContent>
              </Card>

              {(selectedDepartment.headUserId === (user as any)?.id || (user as any)?.isCenterHead) && (
                <Card className="card-hover glass-effect rounded-2xl overflow-hidden">
                  <CardHeader className="pb-4">
                    <div className="p-3 bg-medical-purple/10 rounded-xl w-fit mb-4">
                      <BarChart3 className="h-8 w-8 text-medical-purple" />
                    </div>
                    <CardTitle className="text-xl">Department Monitoring</CardTitle>
                    <CardDescription className="text-gray-600">
                      Monitor doctor appointments, schedules, and performance metrics
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Link href="/department-monitoring">
                      <Button 
                        className="w-full btn-gradient"
                      >
                        View Monitoring Dashboard
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              )}

              {(selectedDepartment.headUserId === (user as any)?.id || (user as any)?.isCenterHead) && (
                <Card className="card-hover glass-effect rounded-2xl overflow-hidden">
                  <CardHeader className="pb-4">
                    <div className="p-3 bg-teal-500/10 rounded-xl w-fit mb-4">
                      <Activity className="h-8 w-8 text-teal-600" />
                    </div>
                    <CardTitle className="text-xl">Department Statistics</CardTitle>
                    <CardDescription className="text-gray-600">
                      Procedure reports, doctor comparisons, and department insights
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Link href="/department-statistics">
                      <Button className="w-full btn-gradient">
                        View Statistics
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              )}

              {(selectedDepartment.headUserId === (user as any)?.id || (user as any)?.isCenterHead) && (
                <CallCenterCodeCard departmentId={selectedDepartment.id} />
              )}

              <Card className="card-hover glass-effect rounded-2xl overflow-hidden">
                <CardHeader className="pb-4">
                  <div className="p-3 bg-medical-purple/10 rounded-xl w-fit mb-4">
                    <Building className="h-8 w-8 text-medical-purple" />
                  </div>
                  <CardTitle className="text-xl">Department Settings</CardTitle>
                  <CardDescription className="text-gray-600">
                    Manage members, permissions, and department configuration
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button variant="outline" className="w-full border-gray-300 text-gray-500" disabled>
                    Coming Soon
                  </Button>
                </CardContent>
              </Card>

              {(user as any)?.isCenterHead && (
                <Card className="card-hover glass-effect rounded-2xl overflow-hidden">
                  <CardHeader className="pb-4">
                    <div className="p-3 bg-warning-orange/10 rounded-xl w-fit mb-4">
                      <Settings className="h-8 w-8 text-warning-orange" />
                    </div>
                    <CardTitle className="text-xl">Center Administration</CardTitle>
                    <CardDescription className="text-gray-600">
                      Manage users, assign department heads, and system settings
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Button 
                      variant="outline" 
                      className="w-full border-warning-orange/20 hover:bg-warning-orange/10 text-warning-orange"
                      onClick={() => window.location.href = "/admin"}
                    >
                      Open Admin Panel
                    </Button>
                  </CardContent>
                </Card>
              )}

              {selectedDepartment.headUserId === (user as any)?.id && (
                <Card className="card-hover glass-effect rounded-2xl overflow-hidden md:col-span-2 lg:col-span-3">
                  <CardHeader className="pb-4">
                    <div className="flex items-center gap-3">
                      <div className="p-3 bg-yellow-100 rounded-xl w-fit">
                        <Trophy className="h-8 w-8 text-yellow-600" />
                      </div>
                      <div>
                        <CardTitle className="text-xl">Doctor of the Month</CardTitle>
                        <CardDescription className="text-gray-600">
                          Recognize outstanding performance and motivate excellence
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <DoctorOfTheMonthManager departmentId={selectedDepartment.id} />
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        ) : userDepartments.length === 0 && selectedCenterId ? (
          <div className="text-center py-16">
            <Building className="mx-auto h-16 w-16 text-gray-400 mb-6" />
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
              No Departments Yet
            </h2>
            <p className="text-gray-600 dark:text-gray-300 mb-6">
              This center doesn't have any departments yet. Create one to get started.
            </p>
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Department
            </Button>
          </div>
        ) : (
          <div className="text-center py-16">
            <p className="text-gray-600 dark:text-gray-300">Please select a department to continue.</p>
          </div>
        )}
      </div>

      <CreateDepartmentDialog 
        open={showCreateDialog} 
        onOpenChange={setShowCreateDialog}
        centerId={selectedCenterId ? parseInt(selectedCenterId) : undefined}
      />
      <CreateUserDialog 
        open={showCreateUserDialog} 
        onOpenChange={setShowCreateUserDialog} 
      />
      <CreateCenterDialog 
        open={showCreateCenterDialog} 
        onOpenChange={setShowCreateCenterDialog} 
      />
    </div>
  );
}
