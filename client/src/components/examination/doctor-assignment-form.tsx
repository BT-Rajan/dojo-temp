import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { queryClient } from "@/lib/queryClient";
import { apiRequest } from "@/lib/queryClient";
import { Users, Plus, X } from "lucide-react";
import type { ExaminationSlot, Doctor } from "@shared/schema";

interface DoctorAssignmentFormProps {
  slot: ExaminationSlot & { assignments: any[] };
  onSuccess: () => void;
}

export function DoctorAssignmentForm({ slot, onSuccess }: DoctorAssignmentFormProps) {
  const { toast } = useToast();
  const [selectedDoctors, setSelectedDoctors] = useState<number[]>([]);
  
  const { data: doctors } = useQuery({
    queryKey: ["/api/doctors"],
  });

  const assignDoctorMutation = useMutation({
    mutationFn: async (doctorId: number) => {
      await apiRequest("/api/examination-assignments", {
        method: "POST",
        body: JSON.stringify({
          slotId: slot.id,
          doctorId,
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/examination-slots"] });
      queryClient.invalidateQueries({ queryKey: ["/api/examination-assignments"] });
      toast({
        title: "Success",
        description: "Doctor assigned successfully",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to assign doctor",
        variant: "destructive",
      });
    },
  });

  const unassignDoctorMutation = useMutation({
    mutationFn: async (assignmentId: number) => {
      await apiRequest(`/api/examination-assignments/${assignmentId}`, { method: "DELETE" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/examination-slots"] });
      queryClient.invalidateQueries({ queryKey: ["/api/examination-assignments"] });
      toast({
        title: "Success",
        description: "Doctor unassigned successfully",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to unassign doctor",
        variant: "destructive",
      });
    },
  });

  const handleAssignDoctors = () => {
    selectedDoctors.forEach(doctorId => {
      assignDoctorMutation.mutate(doctorId);
    });
    setSelectedDoctors([]);
  };

  const handleUnassignDoctor = (assignmentId: number) => {
    unassignDoctorMutation.mutate(assignmentId);
  };

  const assignedDoctorIds = (slot.assignments || []).map(a => a.doctorId);
  const availableDoctors = (doctors || []).filter((doctor: any) => 
    !assignedDoctorIds.includes(doctor.id)
  );

  return (
    <div className="space-y-6">
      <div>
        <h4 className="font-medium text-gray-900 mb-2">Time Slot Details</h4>
        <div className="p-3 bg-gray-50 rounded-lg">
          <p className="text-sm font-medium text-gray-900">
            {slot.startTime} - {slot.endTime}
          </p>
          <p className="text-xs text-gray-500">
            Maximum {slot.maxDoctors || 1} doctor{(slot.maxDoctors || 1) !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      {/* Currently Assigned Doctors */}
      {slot.assignments && slot.assignments.length > 0 && (
        <div>
          <h4 className="font-medium text-gray-900 mb-2">Currently Assigned Doctors</h4>
          <div className="space-y-2">
            {slot.assignments.map((assignment: any) => (
              <div key={assignment.id} className="flex items-center justify-between p-3 bg-healthcare-green/10 rounded-lg">
                <div className="flex items-center">
                  <div className="w-8 h-8 bg-healthcare-green rounded-full flex items-center justify-center mr-3">
                    <Users className="text-white text-xs" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{assignment.doctor.name}</p>
                    <p className="text-xs text-gray-500">{assignment.doctor.title}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleUnassignDoctor(assignment.id)}
                  className="text-red-600 hover:text-red-700"
                  disabled={unassignDoctorMutation.isPending}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Available Doctors to Assign */}
      {availableDoctors.length > 0 && (slot.assignments || []).length < (slot.maxDoctors || 1) && (
        <div>
          <h4 className="font-medium text-gray-900 mb-2">Available Doctors</h4>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {availableDoctors.map((doctor: Doctor) => (
              <div key={doctor.id} className="flex items-center space-x-2 p-2 rounded-lg hover:bg-gray-50">
                <Checkbox
                  id={`doctor-${doctor.id}`}
                  checked={selectedDoctors.includes(doctor.id)}
                  onCheckedChange={(checked) => {
                    if (checked) {
                      setSelectedDoctors([...selectedDoctors, doctor.id]);
                    } else {
                      setSelectedDoctors(selectedDoctors.filter(id => id !== doctor.id));
                    }
                  }}
                />
                <Label htmlFor={`doctor-${doctor.id}`} className="text-sm font-normal cursor-pointer">
                  {doctor.name} - {doctor.title}
                </Label>
              </div>
            ))}
          </div>
          
          {selectedDoctors.length > 0 && (
            <Button
              onClick={handleAssignDoctors}
              disabled={assignDoctorMutation.isPending}
              className="mt-3 bg-medical-blue hover:bg-blue-700"
            >
              <Plus className="mr-2 h-4 w-4" />
              Assign {selectedDoctors.length} Doctor{selectedDoctors.length !== 1 ? 's' : ''}
            </Button>
          )}
        </div>
      )}

      {/* Full capacity message */}
      {(slot.assignments || []).length >= (slot.maxDoctors || 1) && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-sm text-yellow-800">
            This time slot is at maximum capacity ({slot.maxDoctors || 1} doctor{(slot.maxDoctors || 1) !== 1 ? 's' : ''}).
          </p>
        </div>
      )}

      <div className="flex justify-end">
        <Button variant="outline" onClick={onSuccess}>
          Close
        </Button>
      </div>
    </div>
  );
}