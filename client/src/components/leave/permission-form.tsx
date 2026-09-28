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
import { insertPermissionSchema, type InsertPermission } from "@shared/schema";

interface PermissionFormProps {
  onSuccess: () => void;
  editData?: any;
  departmentId?: number;
}

export function PermissionForm({ onSuccess, editData, departmentId }: PermissionFormProps) {
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

  const form = useForm<InsertPermission>({
    resolver: zodResolver(insertPermissionSchema),
    defaultValues: editData ? {
      doctorId: editData.doctorId,
      date: editData.date,
      type: editData.type,
      startTime: editData.startTime,
      endTime: editData.endTime,
      reason: editData.reason || "",
    } : {
      doctorId: 0,
      date: "",
      type: "start_of_day",
      startTime: "",
      endTime: "",
      reason: "",
    },
  });

  const mutation = useMutation({
    mutationFn: async (data: InsertPermission) => {
      if (editData) {
        return await apiRequest(`/api/permissions/${editData.id}`, {
          method: "PATCH",
          body: JSON.stringify(data),
        });
      } else {
        return await apiRequest("/api/permissions", {
          method: "POST",
          body: JSON.stringify(data),
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/permissions"] });
      queryClient.invalidateQueries({ queryKey: ["/api/dashboard/stats"] });
      toast({
        title: "Success",
        description: editData ? "Permission updated successfully" : "Permission created successfully",
      });
      onSuccess();
    },
    onError: () => {
      toast({
        title: "Error",
        description: editData ? "Failed to update permission" : "Failed to create permission",
        variant: "destructive",
      });
    },
  });

  const onSubmit = (data: InsertPermission) => {
    mutation.mutate(data);
  };

  const handleTypeChange = (value: string) => {
    form.setValue("type", value);
    // Set default times based on permission type
    if (value === "start_of_day") {
      form.setValue("startTime", "07:30");
      form.setValue("endTime", "09:30");
    } else if (value === "end_of_day") {
      form.setValue("startTime", "12:30");
      form.setValue("endTime", "14:30");
    }
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

      <div>
        <Label htmlFor="date">Date</Label>
        <Input
          id="date"
          type="date"
          {...form.register("date")}
        />
        {form.formState.errors.date && (
          <p className="text-sm text-red-600">{form.formState.errors.date.message}</p>
        )}
      </div>

      <div>
        <Label htmlFor="type">Permission Type</Label>
        <Select onValueChange={handleTypeChange}>
          <SelectTrigger>
            <SelectValue placeholder="Select Permission Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="start_of_day">Start-of-Day (7:30 - 9:30 AM)</SelectItem>
            <SelectItem value="end_of_day">End-of-Day (12:30 - 2:30 PM)</SelectItem>
          </SelectContent>
        </Select>
        {form.formState.errors.type && (
          <p className="text-sm text-red-600">{form.formState.errors.type.message}</p>
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
        <Label htmlFor="reason">Reason (Optional)</Label>
        <Textarea
          id="reason"
          {...form.register("reason")}
          placeholder="Enter reason for permission..."
        />
        {form.formState.errors.reason && (
          <p className="text-sm text-red-600">{form.formState.errors.reason.message}</p>
        )}
      </div>

      <div className="flex space-x-3">
        <Button type="submit" disabled={mutation.isPending} className="bg-medical-blue hover:bg-blue-700">
          {mutation.isPending ? "Creating..." : "Create Permission"}
        </Button>
        <Button type="button" variant="outline" onClick={onSuccess}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
