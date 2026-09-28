import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { ExaminationForm } from "./examination-form";
import { DoctorAssignmentForm } from "./doctor-assignment-form";
import { useToast } from "@/hooks/use-toast";
import { queryClient } from "@/lib/queryClient";
import { apiRequest } from "@/lib/queryClient";
import { Plus, Edit, Trash2, Users, AlertCircle } from "lucide-react";
import { getWeekdayName } from "@/lib/date-utils";
import type { ExaminationSlot } from "@shared/schema";

interface ExaminationClinicsProps {
  departmentId?: number;
}

export function ExaminationClinics({ departmentId }: ExaminationClinicsProps) {
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showAssignDialog, setShowAssignDialog] = useState(false);
  const [editingSlot, setEditingSlot] = useState<ExaminationSlot | null>(null);
  const [assigningSlot, setAssigningSlot] = useState<any>(null);
  const [selectedWeekday, setSelectedWeekday] = useState(0);
  const { toast } = useToast();

  const { data: examinationSlots, isLoading } = useQuery({
    queryKey: departmentId ? ["/api/examination-slots", departmentId] : ["/api/examination-slots"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/examination-slots${params}`);
      if (!response.ok) throw new Error('Failed to fetch examination slots');
      return response.json();
    },
  });

  const deleteSlotMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiRequest(`/api/examination-slots/${id}`, { method: "DELETE" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/examination-slots"] });
      queryClient.invalidateQueries({ queryKey: ["/api/examination-assignments"] });
      toast({
        title: "Success",
        description: "Time slot deleted successfully",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to delete time slot",
        variant: "destructive",
      });
    },
  });

  const handleFormSuccess = () => {
    setShowAddDialog(false);
    setShowEditDialog(false);
    setEditingSlot(null);
  };

  const handleAssignSuccess = () => {
    setShowAssignDialog(false);
    setAssigningSlot(null);
  };

  const handleEditSlot = (slot: ExaminationSlot) => {
    setEditingSlot(slot);
    setShowEditDialog(true);
  };

  const handleAssignSlot = (slot: any) => {
    setAssigningSlot(slot);
    setShowAssignDialog(true);
  };

  const handleDeleteSlot = (id: number) => {
    deleteSlotMutation.mutate(id);
  };

  // Group slots by weekday
  const slotsByWeekday = examinationSlots?.reduce((acc: any, slot: any) => {
    const weekday = slot.weekday;
    if (!acc[weekday]) {
      acc[weekday] = [];
    }
    acc[weekday].push(slot);
    return acc;
  }, {}) || {};

  const weekdays = [0, 1, 2, 3, 4]; // Sunday to Thursday

  if (isLoading) {
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
    <Card>
      <div className="p-6 border-b">
        <h3 className="text-lg font-semibold text-gray-900">Examination Clinic Scheduling</h3>
        <p className="text-sm text-gray-600 mt-1">Assign doctors to specific time slots for examination clinics</p>
      </div>
      <CardContent className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Time Slot Configuration */}
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h4 className="font-medium text-gray-900">Time Slot Configuration</h4>
              <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
                <DialogTrigger asChild>
                  <Button className="bg-medical-blue hover:bg-blue-700">
                    <Plus className="mr-2 h-4 w-4" />
                    Add Time Slot
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>New Time Slot Assignment</DialogTitle>
                  </DialogHeader>
                  <ExaminationForm onSuccess={handleFormSuccess} departmentId={departmentId} />
                </DialogContent>
              </Dialog>
            </div>

            {/* Edit Dialog */}
            <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Edit Time Slot</DialogTitle>
                </DialogHeader>
                <ExaminationForm slot={editingSlot} onSuccess={handleFormSuccess} departmentId={departmentId} />
              </DialogContent>
            </Dialog>

            {/* Doctor Assignment Dialog */}
            <Dialog open={showAssignDialog} onOpenChange={setShowAssignDialog}>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Manage Doctor Assignments</DialogTitle>
                </DialogHeader>
                {assigningSlot && (
                  <DoctorAssignmentForm slot={assigningSlot} onSuccess={handleAssignSuccess} />
                )}
              </DialogContent>
            </Dialog>

            {weekdays.map((weekday) => (
              <div key={weekday} className="border border-gray-200 rounded-lg p-4">
                <h5 className="font-medium text-gray-900 mb-3">{getWeekdayName(weekday)}</h5>
                <div className="space-y-2">
                  {slotsByWeekday[weekday]?.map((slot: any) => (
                    <div key={slot.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-900">
                          {slot.startTime} - {slot.endTime}
                        </p>
                        <p className="text-xs text-gray-500">
                          Max {slot.maxDoctors} doctor{slot.maxDoctors !== 1 ? 's' : ''}
                        </p>
                        {slot.assignments && slot.assignments.length > 0 && (
                          <div className="mt-2 space-y-1">
                            <p className="text-xs text-gray-600 font-medium">Assigned Doctors:</p>
                            {slot.assignments.map((assignment: any) => (
                              <div key={assignment.id} className="flex items-center">
                                <div className="w-2 h-2 bg-medical-blue rounded-full mr-2"></div>
                                <span className="text-xs text-gray-700">{assignment.doctor.name}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center space-x-2">
                        <Badge variant="outline" className={
                          slot.assignments && slot.assignments.length > 0 
                            ? "bg-healthcare-green/10 text-healthcare-green" 
                            : "bg-yellow-100 text-yellow-600"
                        }>
                          {slot.assignments && slot.assignments.length > 0 
                            ? `${slot.assignments.length} assigned` 
                            : 'No doctors'
                          }
                        </Badge>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="text-medical-blue hover:text-blue-700"
                          onClick={() => handleAssignSlot(slot)}
                          title="Manage Doctor Assignments"
                        >
                          <Users className="h-3 w-3" />
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="text-medical-blue hover:text-blue-700"
                          onClick={() => handleEditSlot(slot)}
                        >
                          <Edit className="h-3 w-3" />
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700">
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This action cannot be undone. This will permanently delete the time slot and all related assignments.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDeleteSlot(slot.id)}>
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </div>
                  )) || (
                    <div className="flex items-center justify-between p-3 bg-red-50 rounded-lg border border-red-200">
                      <div className="flex items-center">
                        <AlertCircle className="w-4 h-4 text-red-500 mr-2" />
                        <div>
                          <p className="text-sm font-medium text-red-900">No time slots configured</p>
                          <p className="text-xs text-red-600">Add time slots for this day</p>
                        </div>
                      </div>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="text-red-600 hover:text-red-700"
                        onClick={() => setShowAddDialog(true)}
                      >
                        <Plus className="h-3 w-3" />
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Summary Statistics */}
          <div className="space-y-6">
            <h4 className="font-medium text-gray-900">Schedule Summary</h4>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-2xl font-semibold text-gray-900">
                  {examinationSlots?.length || 0}
                </p>
                <p className="text-sm text-gray-500">Total Time Slots</p>
              </div>
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-2xl font-semibold text-gray-900">
                  {weekdays.reduce((total, weekday) => total + (slotsByWeekday[weekday]?.length || 0), 0)}
                </p>
                <p className="text-sm text-gray-500">Weekly Slots</p>
              </div>
            </div>

            <div className="space-y-4">
              <h5 className="font-medium text-gray-900">Coverage by Day</h5>
              {weekdays.map((weekday) => (
                <div key={weekday} className="flex justify-between items-center p-3 border border-gray-200 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{getWeekdayName(weekday)}</p>
                    <p className="text-xs text-gray-500">
                      {slotsByWeekday[weekday]?.length || 0} time slots
                    </p>
                  </div>
                  <div className="text-right">
                    {slotsByWeekday[weekday]?.length > 0 ? (
                      <Badge variant="outline" className="bg-healthcare-green/10 text-healthcare-green">
                        Covered
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="bg-red-100 text-red-600">
                        No Coverage
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h5 className="font-medium text-blue-900 mb-2">Quick Instructions</h5>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>• Create time slots for each examination period</li>
                <li>• Assign multiple doctors to each slot if needed</li>
                <li>• Schedules repeat weekly automatically</li>
                <li>• Doctors on leave are excluded automatically</li>
              </ul>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
