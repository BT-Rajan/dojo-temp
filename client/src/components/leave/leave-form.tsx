import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { queryClient } from "@/lib/queryClient";
import { apiRequest } from "@/lib/queryClient";
import { insertLeaveSchema, type InsertLeave } from "@shared/schema";

interface LeaveFormProps {
  onSuccess: () => void;
  editData?: any;
  departmentId?: number;
}

export function LeaveForm({ onSuccess, editData, departmentId }: LeaveFormProps) {
  const { toast } = useToast();
  
  const { data: doctors = [] } = useQuery({
    queryKey: departmentId ? ["/api/doctors", departmentId] : ["/api/doctors"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/doctors${params}`);
      if (!response.ok) throw new Error('Failed to fetch doctors');
      return response.json();
    },
  });

  const form = useForm<InsertLeave>({
    resolver: zodResolver(insertLeaveSchema),
    defaultValues: editData ? {
      doctorId: editData.doctorId,
      startDate: editData.startDate,
      endDate: editData.endDate,
      type: editData.type,
      reason: editData.reason || "",
    } : {
      doctorId: 0,
      startDate: "",
      endDate: "",
      type: "annual",
      reason: "",
    },
  });

  const mutation = useMutation({
    mutationFn: async (data: InsertLeave) => {
      if (editData) {
        return await apiRequest(`/api/leaves/${editData.id}`, {
          method: "PATCH",
          body: JSON.stringify(data),
        });
      } else {
        return await apiRequest("/api/leaves", {
          method: "POST", 
          body: JSON.stringify(data),
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/leaves"] });
      queryClient.invalidateQueries({ queryKey: ["/api/leaves/active"] });
      queryClient.invalidateQueries({ queryKey: ["/api/dashboard/stats"] });
      toast({
        title: "Success",
        description: editData ? "Leave updated successfully" : "Leave created successfully",
      });
      onSuccess();
    },
    onError: () => {
      toast({
        title: "Error",
        description: editData ? "Failed to update leave" : "Failed to create leave",
        variant: "destructive",
      });
    },
  });

  const onSubmit = (data: InsertLeave) => {
    mutation.mutate(data);
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <Label htmlFor="doctorId">Doctor</Label>
        <Select onValueChange={(value) => form.setValue("doctorId", parseInt(value))}>
          <SelectTrigger>
            <SelectValue placeholder="Select Doctor" />
          </SelectTrigger>
          <SelectContent>
            {doctors?.map((doctor: any) => (
              <SelectItem key={doctor.id} value={doctor.id.toString()}>
                {doctor.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {form.formState.errors.doctorId && (
          <p className="text-sm text-red-600">{form.formState.errors.doctorId.message}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="startDate">Start Date</Label>
          <Input
            id="startDate"
            type="date"
            {...form.register("startDate")}
          />
          {form.formState.errors.startDate && (
            <p className="text-sm text-red-600">{form.formState.errors.startDate.message}</p>
          )}
        </div>
        <div>
          <Label htmlFor="endDate">End Date</Label>
          <Input
            id="endDate"
            type="date"
            {...form.register("endDate")}
          />
          {form.formState.errors.endDate && (
            <p className="text-sm text-red-600">{form.formState.errors.endDate.message}</p>
          )}
        </div>
      </div>

      <div>
        <Label htmlFor="type">Leave Type</Label>
        <Select onValueChange={(value) => form.setValue("type", value)}>
          <SelectTrigger>
            <SelectValue placeholder="Select Leave Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="annual">Annual Leave</SelectItem>
            <SelectItem value="sick">Sick Leave</SelectItem>
            <SelectItem value="emergency">Emergency Leave</SelectItem>
            <SelectItem value="personal">Personal Leave</SelectItem>
          </SelectContent>
        </Select>
        {form.formState.errors.type && (
          <p className="text-sm text-red-600">{form.formState.errors.type.message}</p>
        )}
      </div>

      <div>
        <Label htmlFor="reason">Reason (Optional)</Label>
        <Textarea
          id="reason"
          {...form.register("reason")}
          placeholder="Enter reason for leave..."
        />
        {form.formState.errors.reason && (
          <p className="text-sm text-red-600">{form.formState.errors.reason.message}</p>
        )}
      </div>

      <div className="flex space-x-3">
        <Button type="submit" disabled={mutation.isPending} className="bg-medical-blue hover:bg-blue-700">
          {mutation.isPending ? "Creating..." : "Create Leave"}
        </Button>
        <Button type="button" variant="outline" onClick={onSuccess}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
