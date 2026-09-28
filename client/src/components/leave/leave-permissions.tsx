import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { LeaveForm } from "./leave-form";
import { PermissionForm } from "./permission-form";
import { useToast } from "@/hooks/use-toast";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { Plus, Calendar, Clock, Edit, Trash2 } from "lucide-react";
import { formatDate } from "@/lib/date-utils";

interface LeavePermissionsProps {
  departmentId?: number;
}

export function LeavePermissions({ departmentId }: LeavePermissionsProps) {
  const { toast } = useToast();
  const [showLeaveDialog, setShowLeaveDialog] = useState(false);
  const [showPermissionDialog, setShowPermissionDialog] = useState(false);
  const [editingLeave, setEditingLeave] = useState<any>(null);
  const [editingPermission, setEditingPermission] = useState<any>(null);

  const { data: leaves, isLoading: leavesLoading } = useQuery({
    queryKey: departmentId ? ["/api/leaves", departmentId] : ["/api/leaves"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/leaves${params}`);
      if (!response.ok) throw new Error('Failed to fetch leaves');
      return response.json();
    },
  });

  const { data: permissions, isLoading: permissionsLoading } = useQuery({
    queryKey: departmentId ? ["/api/permissions", departmentId] : ["/api/permissions"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/permissions${params}`);
      if (!response.ok) throw new Error('Failed to fetch permissions');
      return response.json();
    },
  });

  const handleLeaveFormSuccess = () => {
    setShowLeaveDialog(false);
    setEditingLeave(null);
  };

  const handlePermissionFormSuccess = () => {
    setShowPermissionDialog(false);
    setEditingPermission(null);
  };

  const clearPermissionsMutation = useMutation({
    mutationFn: async () => {
      return await apiRequest("/api/permissions/clear", {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/permissions"] });
      queryClient.invalidateQueries({ queryKey: ["/api/dashboard/stats"] });
      toast({
        title: "Permissions Cleared",
        description: "All permission records have been cleared.",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to clear permissions.",
        variant: "destructive",
      });
    },
  });

  const handleClearPermissions = () => {
    if (window.confirm("Are you sure you want to clear all permission records? This action cannot be undone.")) {
      clearPermissionsMutation.mutate();
    }
  };

  const deleteLeave = useMutation({
    mutationFn: async (id: number) => {
      return await apiRequest(`/api/leaves/${id}`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/leaves"] });
      queryClient.invalidateQueries({ queryKey: ["/api/leaves/active"] });
      queryClient.invalidateQueries({ queryKey: ["/api/dashboard/stats"] });
      toast({
        title: "Leave Deleted",
        description: "Leave record has been deleted successfully.",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to delete leave record.",
        variant: "destructive",
      });
    },
  });

  const deletePermission = useMutation({
    mutationFn: async (id: number) => {
      return await apiRequest(`/api/permissions/${id}`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/permissions"] });
      queryClient.invalidateQueries({ queryKey: ["/api/dashboard/stats"] });
      toast({
        title: "Permission Deleted",
        description: "Permission record has been deleted successfully.",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to delete permission record.",
        variant: "destructive",
      });
    },
  });

  const handleDeleteLeave = (id: number) => {
    if (window.confirm("Are you sure you want to delete this leave record? This action cannot be undone.")) {
      deleteLeave.mutate(id);
    }
  };

  const handleEditLeave = (leave: any) => {
    setEditingLeave(leave);
    setShowLeaveDialog(true);
  };

  const handleDeletePermission = (id: number) => {
    if (window.confirm("Are you sure you want to delete this permission record? This action cannot be undone.")) {
      deletePermission.mutate(id);
    }
  };

  const handleEditPermission = (permission: any) => {
    setEditingPermission(permission);
    setShowPermissionDialog(true);
  };

  if (leavesLoading || permissionsLoading) {
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
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      {/* Leave Management */}
      <Card>
        <div className="p-6 border-b">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Leave Management</h3>
            <Dialog open={showLeaveDialog} onOpenChange={(open) => {
              setShowLeaveDialog(open);
              if (!open) setEditingLeave(null);
            }}>
              <DialogTrigger asChild>
                <Button className="bg-medical-blue hover:bg-blue-700">
                  <Plus className="mr-2 h-4 w-4" />
                  Add Leave
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{editingLeave ? "Edit Leave" : "Add Leave"}</DialogTitle>
                </DialogHeader>
                <LeaveForm 
                  onSuccess={handleLeaveFormSuccess} 
                  editData={editingLeave}
                  departmentId={departmentId}
                />
              </DialogContent>
            </Dialog>
          </div>
        </div>
        <CardContent className="p-6">
          <div className="space-y-4">
            {leaves?.map((leave: any) => (
              <div key={leave.id} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-900">{leave.doctor.name}</h4>
                  <Badge 
                    variant={leave.isActive ? "destructive" : "outline"}
                    className={leave.isActive ? "bg-red-100 text-red-600" : ""}
                  >
                    {leave.isActive ? "On Leave" : "Ended"}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-600">Start Date</p>
                    <p className="font-medium">{formatDate(leave.startDate)}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">End Date</p>
                    <p className="font-medium">{formatDate(leave.endDate)}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Type</p>
                    <p className="font-medium capitalize">{leave.type}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Days</p>
                    <p className="font-medium">
                      {Math.ceil((new Date(leave.endDate).getTime() - new Date(leave.startDate).getTime()) / (1000 * 60 * 60 * 24)) + 1} days
                    </p>
                  </div>
                </div>
                {leave.reason && (
                  <div className="mt-3">
                    <p className="text-gray-600 text-sm">Reason</p>
                    <p className="text-sm">{leave.reason}</p>
                  </div>
                )}
                <div className="flex items-center justify-end space-x-2 mt-3">
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="text-medical-blue hover:text-blue-700"
                    onClick={() => handleEditLeave(leave)}
                  >
                    <Edit className="mr-1 h-3 w-3" />
                    Edit
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="text-red-600 hover:text-red-700"
                    onClick={() => handleDeleteLeave(leave.id)}
                    disabled={deleteLeave.isPending}
                  >
                    <Trash2 className="mr-1 h-3 w-3" />
                    {deleteLeave.isPending ? "Deleting..." : "Delete"}
                  </Button>
                </div>
              </div>
            )) || (
              <p className="text-sm text-gray-500 italic">No leaves recorded</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Permission Management */}
      <Card>
        <div className="p-6 border-b">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Permission Tracking</h3>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleClearPermissions}
                disabled={clearPermissionsMutation.isPending}
                className="text-red-600 border-red-600 hover:bg-red-50"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {clearPermissionsMutation.isPending ? "Clearing..." : "Clear All"}
              </Button>
              <Dialog open={showPermissionDialog} onOpenChange={(open) => {
                setShowPermissionDialog(open);
                if (!open) setEditingPermission(null);
              }}>
                <DialogTrigger asChild>
                  <Button className="bg-medical-blue hover:bg-blue-700">
                    <Clock className="mr-2 h-4 w-4" />
                    Add Permission
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{editingPermission ? "Edit Permission" : "Add Permission"}</DialogTitle>
                  </DialogHeader>
                  <PermissionForm 
                    onSuccess={handlePermissionFormSuccess} 
                    editData={editingPermission}
                    departmentId={departmentId}
                  />
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </div>
        <CardContent className="p-6">
          <div className="space-y-4">
            {permissions?.slice(0, 10).map((permission: any) => (
              <div key={permission.id} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium text-gray-900">{permission.doctor.name}</h4>
                  <Badge 
                    variant="outline"
                    className="bg-yellow-100 text-yellow-600"
                  >
                    {permission.type === "start_of_day" ? "Start-of-Day" : "End-of-Day"}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-600">Date</p>
                    <p className="font-medium">{formatDate(permission.date)}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Time</p>
                    <p className="font-medium">{permission.startTime} - {permission.endTime}</p>
                  </div>
                </div>
                {permission.reason && (
                  <div className="mt-3">
                    <p className="text-gray-600 text-sm">Reason</p>
                    <p className="text-sm">{permission.reason}</p>
                  </div>
                )}
                <div className="flex items-center justify-end space-x-2 mt-3">
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="text-medical-blue hover:text-blue-700"
                    onClick={() => handleEditPermission(permission)}
                  >
                    <Edit className="mr-1 h-3 w-3" />
                    Edit
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="text-red-600 hover:text-red-700"
                    onClick={() => handleDeletePermission(permission.id)}
                    disabled={deletePermission.isPending}
                  >
                    <Trash2 className="mr-1 h-3 w-3" />
                    {deletePermission.isPending ? "Deleting..." : "Delete"}
                  </Button>
                </div>
              </div>
            )) || (
              <p className="text-sm text-gray-500 italic">No permissions recorded</p>
            )}
          </div>

          <div className="mt-6 pt-4 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <h4 className="font-medium text-gray-900">Monthly Summary</h4>
              <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                Clear All Permissions
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-4 mt-3">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-semibold text-gray-900">{permissions?.length || 0}</p>
                <p className="text-xs text-gray-500">Total Permissions</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-semibold text-gray-900">
                  {permissions?.length ? (permissions.length / 12).toFixed(1) : "0"}
                </p>
                <p className="text-xs text-gray-500">Avg per Doctor</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
