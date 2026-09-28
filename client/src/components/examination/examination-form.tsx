import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { queryClient } from "@/lib/queryClient";
import { apiRequest } from "@/lib/queryClient";
import { insertExaminationSlotSchema, type InsertExaminationSlot, type ExaminationSlot } from "@shared/schema";
import { getWeekdayName } from "@/lib/date-utils";
import { z } from "zod";

const formSchema = insertExaminationSlotSchema.extend({
  assignedDoctors: z.array(z.number()).optional(),
});

type FormData = z.infer<typeof formSchema>;

interface ExaminationFormProps {
  slot?: (ExaminationSlot & { assignments?: any[] }) | null;
  onSuccess: () => void;
  departmentId?: number;
}

export function ExaminationForm({ slot, onSuccess, departmentId }: ExaminationFormProps) {
  const { toast } = useToast();
  const [selectedDoctors, setSelectedDoctors] = useState<number[]>(slot?.assignments?.map((a: any) => a.doctorId) || []);
  
  const { data: doctors } = useQuery({
    queryKey: departmentId ? ["/api/doctors", departmentId] : ["/api/doctors"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/doctors${params}`);
      if (!response.ok) throw new Error('Failed to fetch doctors');
      return response.json();
    },
  });

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      weekday: slot?.weekday || 0,
      startTime: slot?.startTime || "",
      endTime: slot?.endTime || "",
      maxDoctors: slot?.maxDoctors || 1,
      departmentId: slot?.departmentId || departmentId,
      assignedDoctors: selectedDoctors,
    },
  });

  const handleDoctorChange = (doctorId: number, checked: boolean) => {
    const maxDocs = form.getValues("maxDoctors") || 1;
    
    if (checked) {
      if (selectedDoctors.length >= maxDocs) {
        toast({
          title: "Maximum Capacity Reached",
          description: `You can only assign ${maxDocs} doctor${maxDocs !== 1 ? 's' : ''} to this slot.`,
          variant: "destructive",
        });
        return;
      }
      const newSelection = [...selectedDoctors, doctorId];
      setSelectedDoctors(newSelection);
      form.setValue("assignedDoctors", newSelection);
    } else {
      const newSelection = selectedDoctors.filter(id => id !== doctorId);
      setSelectedDoctors(newSelection);
      form.setValue("assignedDoctors", newSelection);
    }
  };

  const mutation = useMutation({
    mutationFn: async (data: FormData) => {
      let slotResult;
      
      if (slot) {
        // Update existing slot
        const slotResponse = await apiRequest(`/api/examination-slots/${slot.id}`, {
          method: "PUT",
          body: JSON.stringify({
            weekday: data.weekday,
            startTime: data.startTime,
            endTime: data.endTime,
            maxDoctors: data.maxDoctors,
          }),
        });
        slotResult = await slotResponse.json();
      } else {
        // Create new slot
        const slotResponse = await apiRequest("/api/examination-slots", {
          method: "POST",
          body: JSON.stringify({
            weekday: data.weekday,
            startTime: data.startTime,
            endTime: data.endTime,
            maxDoctors: data.maxDoctors,
            departmentId: data.departmentId,
          }),
        });
        slotResult = await slotResponse.json();
      }

      // Handle assignments for both new and existing slots
      if (data.assignedDoctors) {
        if (slot) {
          // For existing slots, first remove all current assignments
          if (slot.assignments && slot.assignments.length > 0) {
            const deletePromises = slot.assignments.map((assignment: any) =>
              apiRequest(`/api/examination-assignments/${assignment.id}`, { method: "DELETE" })
            );
            await Promise.all(deletePromises);
          }
        }
        
        // Add new assignments
        if (data.assignedDoctors.length > 0) {
          const assignmentPromises = data.assignedDoctors.map((doctorId) =>
            apiRequest("/api/examination-assignments", {
              method: "POST",
              body: JSON.stringify({
                slotId: slotResult.id,
                doctorId,
              }),
            })
          );
          await Promise.all(assignmentPromises);
        }
      }

      return slotResult;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/examination-slots"] });
      queryClient.invalidateQueries({ queryKey: ["/api/examination-assignments"] });
      toast({
        title: "Success",
        description: slot ? "Examination slot updated successfully" : "Examination slot created successfully",
      });
      onSuccess();
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to create examination slot",
        variant: "destructive",
      });
    },
  });

  return (
    <form onSubmit={form.handleSubmit(mutation.mutate)} className="space-y-4">
      <div>
        <Label htmlFor="weekday">Day of Week</Label>
        <Select
          value={form.watch("weekday")?.toString()}
          onValueChange={(value) => form.setValue("weekday", parseInt(value))}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select day" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0">Sunday</SelectItem>
            <SelectItem value="1">Monday</SelectItem>
            <SelectItem value="2">Tuesday</SelectItem>
            <SelectItem value="3">Wednesday</SelectItem>
            <SelectItem value="4">Thursday</SelectItem>
          </SelectContent>
        </Select>
        {form.formState.errors.weekday && (
          <p className="text-sm text-red-600">{form.formState.errors.weekday.message}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="startTime">Start Time</Label>
          <Input
            id="startTime"
            type="time"
            {...form.register("startTime")}
          />
          {form.formState.errors.startTime && (
            <p className="text-sm text-red-600">{form.formState.errors.startTime.message}</p>
          )}
        </div>
        <div>
          <Label htmlFor="endTime">End Time</Label>
          <Input
            id="endTime"
            type="time"
            {...form.register("endTime")}
          />
          {form.formState.errors.endTime && (
            <p className="text-sm text-red-600">{form.formState.errors.endTime.message}</p>
          )}
        </div>
      </div>

      <div>
        <Label htmlFor="maxDoctors">Maximum Doctors</Label>
        <Input
          id="maxDoctors"
          type="number"
          min="1"
          max="10"
          {...form.register("maxDoctors", { valueAsNumber: true })}
        />
        {form.formState.errors.maxDoctors && (
          <p className="text-sm text-red-600">{form.formState.errors.maxDoctors.message}</p>
        )}
      </div>

      <div>
        <Label>Assigned Doctors (Optional)</Label>
        <div className="space-y-2 mt-2 max-h-48 overflow-y-auto">
          {doctors?.map((doctor: any) => (
            <div key={doctor.id} className="flex items-center space-x-2">
              <Checkbox
                id={`doctor-${doctor.id}`}
                checked={selectedDoctors.includes(doctor.id)}
                onCheckedChange={(checked) => handleDoctorChange(doctor.id, checked as boolean)}
              />
              <Label htmlFor={`doctor-${doctor.id}`} className="text-sm font-normal">
                {doctor.name} - {doctor.title}
              </Label>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-1">
          You can assign doctors later if needed. Maximum capacity: {form.watch("maxDoctors") || 1} doctor{(form.watch("maxDoctors") || 1) !== 1 ? 's' : ''}
        </p>
      </div>

      <div className="flex space-x-3">
        <Button type="submit" disabled={mutation.isPending} className="bg-medical-blue hover:bg-blue-700">
          {mutation.isPending ? (slot ? "Updating..." : "Creating...") : (slot ? "Update Time Slot" : "Create Time Slot")}
        </Button>
        <Button type="button" variant="outline" onClick={onSuccess}>
          Cancel
        </Button>
      </div>
    </form>
  );
}