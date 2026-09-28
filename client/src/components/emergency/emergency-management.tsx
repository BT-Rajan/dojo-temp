import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { queryClient } from "@/lib/queryClient";
import { apiRequest } from "@/lib/queryClient";
import { Ambulance, Users, Clock, Trash2, SkipForward, RotateCcw, BarChart3, Calendar } from "lucide-react";
import { formatDate } from "@/lib/date-utils";

interface EmergencyManagementProps {
  departmentId?: number;
}

export function EmergencyManagement({ departmentId }: EmergencyManagementProps) {
  const { toast } = useToast();
  const [assigningEmergency, setAssigningEmergency] = useState(false);
  const [skippedDoctorIds, setSkippedDoctorIds] = useState<number[]>([]);
  const [showEmergencyDialog, setShowEmergencyDialog] = useState(false);
  const [emergencyPatientName, setEmergencyPatientName] = useState("");
  const [emergencyType, setEmergencyType] = useState("");

  const { data: nextDoctor, isLoading: nextDoctorLoading } = useQuery({
    queryKey: departmentId ? 
      ["/api/emergency-assignments/next-doctor", departmentId, skippedDoctorIds.join(',')] : 
      ["/api/emergency-assignments/next-doctor", skippedDoctorIds.join(',')],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (departmentId) params.append('departmentId', departmentId.toString());
      if (skippedDoctorIds.length > 0) params.append('skipDoctorIds', skippedDoctorIds.join(','));
      
      const response = await fetch(`/api/emergency-assignments/next-doctor?${params}`);
      if (!response.ok) throw new Error('Failed to fetch next doctor');
      return response.json();
    },
  });

  const { data: emergencyHistory, isLoading: historyLoading } = useQuery({
    queryKey: departmentId ? ["/api/emergency-assignments", departmentId] : ["/api/emergency-assignments"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/emergency-assignments${params}`);
      if (!response.ok) throw new Error('Failed to fetch emergency history');
      return response.json();
    },
  });

  const { data: monthlyStats, isLoading: statsLoading } = useQuery({
    queryKey: departmentId ? ["/api/emergency-assignments/month", new Date().getFullYear(), new Date().getMonth() + 1, departmentId] : ["/api/emergency-assignments/month", new Date().getFullYear(), new Date().getMonth() + 1],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/emergency-assignments/month/${new Date().getFullYear()}/${new Date().getMonth() + 1}${params}`);
      if (!response.ok) throw new Error('Failed to fetch monthly stats');
      return response.json();
    },
  });

  const { data: emergencyStats, isLoading: emergencyStatsLoading } = useQuery({
    queryKey: departmentId ? ["/api/emergency-assignments/stats", departmentId] : ["/api/emergency-assignments/stats"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/emergency-assignments/stats${params}`);
      if (!response.ok) throw new Error('Failed to fetch emergency stats');
      return response.json();
    },
  });

  const assignEmergencyMutation = useMutation({
    mutationFn: async (data: { patientName: string; emergencyType: string }) => {
      if (!nextDoctor) throw new Error("No available doctor");
      
      const emergencyNumber = Math.floor(Math.random() * 1000) + 1;
      const today = new Date();
      
      return await apiRequest("/api/emergency-assignments", {
        method: "POST",
        body: JSON.stringify({
          doctorId: nextDoctor.id,
          assignedDate: today.toISOString().split('T')[0],
          assignedTime: today.toTimeString().split(' ')[0],
          emergencyNumber,
          patientName: data.patientName,
          emergencyType: data.emergencyType,
          notes: "",
        }),
      });
    },
    onSuccess: () => {
      // Clear skipped doctors after successful assignment
      setSkippedDoctorIds([]);
      setShowEmergencyDialog(false);
      setEmergencyPatientName("");
      setEmergencyType("");
      
      // Invalidate all emergency-related queries with proper department context
      if (departmentId) {
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments", departmentId] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/next-doctor", departmentId] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/stats", departmentId] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/month", new Date().getFullYear(), new Date().getMonth() + 1, departmentId] });
      } else {
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments"] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/next-doctor"] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/stats"] });
      }
      queryClient.invalidateQueries({ queryKey: ["/api/dashboard/stats"] });
      toast({
        title: "Emergency Assigned",
        description: `Dr. ${nextDoctor?.name} has been assigned to the emergency.`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message || "Failed to assign emergency doctor.",
        variant: "destructive",
      });
    },
  });

  const handleSkipDoctor = () => {
    if (nextDoctor && !skippedDoctorIds.includes(nextDoctor.id)) {
      setSkippedDoctorIds(prev => [...prev, nextDoctor.id]);
      toast({
        title: "Doctor Skipped",
        description: `Dr. ${nextDoctor.name} has been skipped. Getting next available doctor.`,
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

  const clearEmergencyHistoryMutation = useMutation({
    mutationFn: async () => {
      return await apiRequest("/api/emergency-assignments/clear", {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      // Invalidate all emergency-related queries with proper department context
      if (departmentId) {
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments", departmentId] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/next-doctor", departmentId] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/stats", departmentId] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/month", new Date().getFullYear(), new Date().getMonth() + 1, departmentId] });
      } else {
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments"] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/next-doctor"] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/stats"] });
        queryClient.invalidateQueries({ queryKey: ["/api/emergency-assignments/month"] });
      }
      queryClient.invalidateQueries({ queryKey: ["/api/dashboard/stats"] });
      toast({
        title: "History Cleared",
        description: "All emergency assignment history has been cleared.",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to clear emergency history.",
        variant: "destructive",
      });
    },
  });

  const handleOpenEmergencyDialog = () => {
    if (!nextDoctor) {
      toast({
        title: "No Available Doctor",
        description: "No doctor is available for emergency assignment right now.",
        variant: "destructive",
      });
      return;
    }
    setShowEmergencyDialog(true);
  };

  const handleAssignEmergency = () => {
    if (!emergencyPatientName.trim() || !emergencyType) {
      toast({
        title: "Missing Information",
        description: "Please enter patient name and select emergency type.",
        variant: "destructive",
      });
      return;
    }

    setAssigningEmergency(true);
    assignEmergencyMutation.mutate({
      patientName: emergencyPatientName.trim(),
      emergencyType: emergencyType,
    });
    setTimeout(() => setAssigningEmergency(false), 1000);
  };

  const handleClearHistory = () => {
    if (window.confirm("Are you sure you want to clear all emergency assignment history? This action cannot be undone.")) {
      clearEmergencyHistoryMutation.mutate();
    }
  };

  if (nextDoctorLoading || historyLoading || statsLoading || emergencyStatsLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Emergency Counter Statistics */}
      <Card>
        <div className="p-6 border-b">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Emergency Counter</h3>
              <p className="text-sm text-gray-600 mt-1">Total number of emergencies handled by each doctor</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearHistory}
              disabled={clearEmergencyHistoryMutation.isPending}
              className="text-red-600 border-red-600 hover:bg-red-50"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {clearEmergencyHistoryMutation.isPending ? "Clearing..." : "Clear History"}
            </Button>
          </div>
        </div>
        <CardContent className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {emergencyStats?.map((stat: any) => (
              <div key={stat.doctor.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg bg-gray-50">
                <div className="flex items-center">
                  <div className="w-10 h-10 bg-red-50 rounded-full flex items-center justify-center mr-3">
                    <Ambulance className="text-red-600 text-sm" />
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-gray-900">{stat.doctor.name}</h4>
                    <p className="text-xs text-gray-500">{stat.doctor.title}</p>
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-red-600">{stat.totalEmergencies}</p>
                  <p className="text-xs text-gray-500">Total</p>
                </div>
              </div>
            )) || (
              <p className="text-sm text-gray-500 italic col-span-full">No emergency statistics available</p>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      {/* Emergency Assignment */}
      <Card>
        <div className="p-6 border-b">
          <h3 className="text-lg font-semibold text-gray-900">Emergency Assignment</h3>
          <p className="text-sm text-gray-600 mt-1">Fair rotation system for walk-in emergencies</p>
        </div>
        <CardContent className="p-6">
          <div className="bg-gray-50 rounded-lg p-4 mb-6">
            <h4 className="font-medium text-gray-900 mb-3">Next Available Doctor</h4>
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <div className="w-12 h-12 bg-medical-blue/10 rounded-full flex items-center justify-center mr-4">
                  <Users className="text-medical-blue" />
                </div>
                <div>
                  <h5 className="font-medium text-gray-900">
                    {nextDoctor ? `Dr. ${nextDoctor.name}` : "No available doctor"}
                  </h5>
                  <p className="text-sm text-gray-600">
                    {nextDoctor ? `${nextDoctor.title}` : "All doctors may be on leave"}
                  </p>
                </div>
              </div>
              <div className="flex space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSkipDoctor}
                  disabled={!nextDoctor}
                  className="text-orange-600 border-orange-600 hover:bg-orange-50"
                >
                  <SkipForward className="mr-2 h-4 w-4" />
                  Skip
                </Button>
                <Button
                  onClick={handleOpenEmergencyDialog}
                  disabled={!nextDoctor || assigningEmergency || assignEmergencyMutation.isPending}
                  className="bg-red-600 hover:bg-red-700"
                  data-testid="button-assign-emergency-mgmt"
                >
                  <Ambulance className="mr-2 h-4 w-4" />
                  Assign Emergency
                </Button>
              </div>
            </div>
          </div>

          {/* Skipped Doctors Section */}
          {skippedDoctorIds.length > 0 && (
            <div className="bg-orange-50 rounded-lg p-4 mb-6 border border-orange-200">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium text-orange-900">Skipped Doctors ({skippedDoctorIds.length})</h4>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleResetSkips}
                  className="text-orange-700 border-orange-300 hover:bg-orange-100"
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Reset All
                </Button>
              </div>
              <p className="text-sm text-orange-700">
                These doctors have been temporarily skipped. Click "Reset All" to make them available for assignments again.
              </p>
            </div>
          )}

          <div className="space-y-4">
            <h4 className="font-medium text-gray-900">Recent Emergency Queue</h4>
            {emergencyHistory?.slice(0, 5).map((assignment: any, index: number) => (
              <div key={assignment.id} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                <div className="flex items-center">
                  <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center mr-3">
                    <span className="text-sm font-medium text-gray-600">{index + 1}</span>
                  </div>
                  <div>
                    <h5 className="text-sm font-medium text-gray-900">{assignment.doctor.name}</h5>
                    <p className="text-xs text-gray-500">
                      {formatDate(assignment.assignedDate)} at {assignment.assignedTime}
                    </p>
                  </div>
                </div>
                <Badge variant="outline">#{assignment.emergencyNumber}</Badge>
              </div>
            )) || (
              <p className="text-sm text-gray-500 italic">No recent assignments</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Emergency History */}
      <Card>
        <div className="p-6 border-b">
          <h3 className="text-lg font-semibold text-gray-900">Emergency Assignment History</h3>
          <p className="text-sm text-gray-600 mt-1">Monthly tracking and statistics</p>
        </div>
        <CardContent className="p-6">
          <div className="space-y-4">
            {emergencyHistory?.slice(0, 10).map((assignment: any) => (
              <div key={assignment.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center">
                  <div className="w-10 h-10 bg-red-50 rounded-full flex items-center justify-center mr-3">
                    <Ambulance className="text-red-600 text-sm" />
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-gray-900">{assignment.doctor.name}</h4>
                    <p className="text-xs text-gray-500">
                      {formatDate(assignment.assignedDate)} - {assignment.assignedTime}
                    </p>
                  </div>
                </div>
                <span className="text-xs text-gray-500">Emergency #{assignment.emergencyNumber}</span>
              </div>
            )) || (
              <p className="text-sm text-gray-500 italic">No assignment history</p>
            )}
          </div>

          <div className="mt-6 pt-4 border-t border-gray-200">
            <h4 className="font-medium text-gray-900 mb-3">Monthly Statistics</h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center">
                <p className="text-2xl font-semibold text-gray-900">{monthlyStats?.length || 0}</p>
                <p className="text-xs text-gray-500">Total Emergencies</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-semibold text-gray-900">
                  {monthlyStats?.length ? (monthlyStats.length / 12).toFixed(1) : "0"}
                </p>
                <p className="text-xs text-gray-500">Avg per Doctor</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      </div>

      {/* Emergency Assignment Dialog */}
      <Dialog open={showEmergencyDialog} onOpenChange={setShowEmergencyDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Ambulance className="h-5 w-5 text-red-600" />
              Assign Emergency to Dr. {nextDoctor?.name}
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
                data-testid="input-emergency-patient-name-mgmt"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="emergencyType">Emergency Type *</Label>
              <Select value={emergencyType} onValueChange={setEmergencyType}>
                <SelectTrigger data-testid="select-emergency-type-mgmt">
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
            {(nextDoctor as any)?.currentClinic && (
              <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
                <p className="text-sm text-blue-800">
                  <strong>Location:</strong> {(nextDoctor as any).currentClinic.name}
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowEmergencyDialog(false)}
              disabled={assignEmergencyMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAssignEmergency}
              disabled={assignEmergencyMutation.isPending || !emergencyPatientName.trim() || !emergencyType}
              className="bg-red-600 hover:bg-red-700"
              data-testid="button-confirm-emergency-mgmt"
            >
              {assignEmergencyMutation.isPending ? "Assigning..." : "Confirm Assignment"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
