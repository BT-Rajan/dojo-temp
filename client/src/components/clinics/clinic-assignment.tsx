import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { ClinicForm } from "./clinic-form";
import { ClinicManagementForm } from "./clinic-management-form";
import { useToast } from "@/hooks/use-toast";
import { queryClient } from "@/lib/queryClient";
import { apiRequest } from "@/lib/queryClient";
import { Plus, Edit, Trash2, Building, Users } from "lucide-react";
import { getWeekdayName } from "@/lib/date-utils";
import type { Clinic } from "@shared/schema";

interface ClinicAssignmentProps {
  departmentId?: number;
}

export function ClinicAssignment({ departmentId }: ClinicAssignmentProps) {
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showClinicDialog, setShowClinicDialog] = useState(false);
  const [editingClinic, setEditingClinic] = useState<Clinic | null>(null);
  const [selectedWeekday, setSelectedWeekday] = useState(0); // 0 = Sunday
  const { toast } = useToast();

  const { data: clinicAssignments, isLoading } = useQuery({
    queryKey: departmentId ? ["/api/clinic-assignments", departmentId] : ["/api/clinic-assignments"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/clinic-assignments${params}`);
      if (!response.ok) throw new Error('Failed to fetch clinic assignments');
      return response.json();
    },
  });

  const { data: clinics, isLoading: clinicsLoading } = useQuery({
    queryKey: departmentId ? ["/api/clinics", departmentId] : ["/api/clinics"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/clinics${params}`);
      if (!response.ok) throw new Error('Failed to fetch clinics');
      return response.json();
    },
  });

  const deleteClinicMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiRequest(`/api/clinics/${id}`, { method: "DELETE" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/clinics"] });
      queryClient.invalidateQueries({ queryKey: ["/api/clinic-assignments"] });
      toast({
        title: "Success",
        description: "Clinic deleted successfully",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to delete clinic",
        variant: "destructive",
      });
    },
  });

  const deleteAssignmentMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiRequest(`/api/clinic-assignments/${id}`, { method: "DELETE" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/clinic-assignments"] });
      toast({
        title: "Success",
        description: "Assignment deleted successfully",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to delete assignment",
        variant: "destructive",
      });
    },
  });

  const handleFormSuccess = () => {
    setShowAddDialog(false);
  };

  const handleClinicFormSuccess = () => {
    setShowClinicDialog(false);
    setEditingClinic(null);
  };

  const handleDeleteClinic = (id: number) => {
    deleteClinicMutation.mutate(id);
  };

  const handleDeleteAssignment = (id: number) => {
    deleteAssignmentMutation.mutate(id);
  };

  // Group assignments by weekday
  const assignmentsByWeekday = clinicAssignments?.reduce((acc: any, assignment: any) => {
    const weekday = assignment.weekday;
    if (!acc[weekday]) {
      acc[weekday] = [];
    }
    acc[weekday].push(assignment);
    return acc;
  }, {}) || {};

  const weekdays = [0, 1, 2, 3, 4]; // Sunday to Thursday

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Clinic Management Section */}
      <Card>
        <div className="p-6 border-b">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Clinic Management</h3>
            <Dialog open={showClinicDialog} onOpenChange={setShowClinicDialog}>
              <DialogTrigger asChild>
                <Button className="bg-medical-blue hover:bg-blue-700">
                  <Building className="mr-2 h-4 w-4" />
                  Add New Clinic
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add New Clinic</DialogTitle>
                </DialogHeader>
                <ClinicManagementForm clinic={null} onSuccess={handleClinicFormSuccess} departmentId={departmentId} />
              </DialogContent>
            </Dialog>
          </div>
        </div>
        <CardContent className="p-6">
          {clinicsLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-medium text-gray-900">Clinic Name</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-900">Time</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-900">Description</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-900">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {clinics?.map((clinic: Clinic) => (
                    <tr key={clinic.id} className="hover:bg-gray-50">
                      <td className="py-4 px-4">
                        <div className="flex items-center">
                          <div className="w-10 h-10 bg-medical-blue/10 rounded-full flex items-center justify-center mr-3">
                            <Building className="text-medical-blue text-sm" />
                          </div>
                          <div>
                            <h4 className="text-sm font-medium text-gray-900">{clinic.name}</h4>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 px-4 text-sm text-gray-900">
                        {clinic.startTime} - {clinic.endTime}
                      </td>
                      <td className="py-4 px-4 text-sm text-gray-900">
                        {clinic.description || "No description"}
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex items-center space-x-2">
                          <Dialog>
                            <DialogTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setEditingClinic(clinic)}
                                className="text-medical-blue hover:text-blue-700"
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Edit Clinic</DialogTitle>
                              </DialogHeader>
                              <ClinicManagementForm clinic={editingClinic} onSuccess={handleClinicFormSuccess} departmentId={departmentId} />
                            </DialogContent>
                          </Dialog>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-red-600 hover:text-red-700"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  This action cannot be undone. This will permanently delete the clinic and all its assignments.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction onClick={() => handleDeleteClinic(clinic.id)}>
                                  Delete
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(!clinics || clinics.length === 0) && (
                <div className="text-center py-8">
                  <Building className="mx-auto h-12 w-12 text-gray-400" />
                  <p className="mt-2 text-sm text-gray-500">No clinics added yet</p>
                  <p className="text-xs text-gray-400">Add your first clinic to get started</p>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Weekly Schedule */}
        <Card>
          <div className="p-6 border-b">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Weekly Clinic Schedule</h3>
              <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
                <DialogTrigger asChild>
                  <Button className="bg-medical-blue hover:bg-blue-700">
                    <Plus className="mr-2 h-4 w-4" />
                    Add Assignment
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>New Clinic Assignment</DialogTitle>
                  </DialogHeader>
                  <ClinicForm onSuccess={handleFormSuccess} departmentId={departmentId} />
                </DialogContent>
              </Dialog>
            </div>
          </div>
        <CardContent className="p-6">
          <div className="space-y-4">
            {weekdays.map((weekday) => (
              <div key={weekday} className="border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-900 mb-3">{getWeekdayName(weekday)}</h4>
                <div className="space-y-2">
                  {assignmentsByWeekday[weekday]?.map((assignment: any) => (
                    <div key={assignment.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{assignment.clinic.name}</p>
                        <p className="text-xs text-gray-500">
                          {assignment.clinic.startTime} - {assignment.clinic.endTime}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium text-gray-900">{assignment.doctor.name}</p>
                        <div className="flex items-center space-x-2 mt-1">
                          <Button variant="ghost" size="sm" className="text-medical-blue hover:text-blue-700">
                            <Edit className="h-3 w-3" />
                          </Button>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                className="text-red-600 hover:text-red-700"
                                data-testid={`button-delete-assignment-${assignment.id}`}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Delete Assignment?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  This will remove {assignment.doctor.name} from {assignment.clinic.name} on {getWeekdayName(weekday)}. This action cannot be undone.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel data-testid="button-cancel-delete">Cancel</AlertDialogCancel>
                                <AlertDialogAction 
                                  onClick={() => handleDeleteAssignment(assignment.id)}
                                  data-testid={`button-confirm-delete-assignment-${assignment.id}`}
                                >
                                  Delete Assignment
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </div>
                    </div>
                  )) || (
                    <p className="text-sm text-gray-500 italic">No assignments</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Assignment Summary */}
      <Card>
        <div className="p-6 border-b">
          <h3 className="text-lg font-semibold text-gray-900">Assignment Summary</h3>
        </div>
        <CardContent className="p-6">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-2xl font-semibold text-gray-900">
                  {clinicAssignments?.length || 0}
                </p>
                <p className="text-sm text-gray-500">Total Assignments</p>
              </div>
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-2xl font-semibold text-gray-900">
                  {weekdays.reduce((total, weekday) => total + (assignmentsByWeekday[weekday]?.length || 0), 0)}
                </p>
                <p className="text-sm text-gray-500">Weekly Slots</p>
              </div>
            </div>
            <div className="space-y-2">
              <h4 className="font-medium text-gray-900">Coverage by Day</h4>
              {weekdays.map((weekday) => (
                <div key={weekday} className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">{getWeekdayName(weekday)}</span>
                  <Badge variant="outline">
                    {assignmentsByWeekday[weekday]?.length || 0} assignments
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
      </div>
    </div>
  );
}
