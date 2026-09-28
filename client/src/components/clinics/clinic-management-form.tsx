import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { queryClient } from "@/lib/queryClient";
import { apiRequest } from "@/lib/queryClient";
import { insertClinicSchema, type InsertClinic, type Clinic } from "@shared/schema";

interface ClinicManagementFormProps {
  clinic?: Clinic | null;
  onSuccess: () => void;
  departmentId?: number;
}

export function ClinicManagementForm({ clinic, onSuccess, departmentId }: ClinicManagementFormProps) {
  const { toast } = useToast();
  
  const form = useForm<InsertClinic>({
    resolver: zodResolver(insertClinicSchema),
    defaultValues: {
      name: clinic?.name || "",
      description: clinic?.description || "",
      startTime: clinic?.startTime || "",
      endTime: clinic?.endTime || "",
      departmentId: clinic?.departmentId || departmentId,
    },
  });

  const mutation = useMutation({
    mutationFn: async (data: InsertClinic) => {
      if (clinic) {
        return await apiRequest(`/api/clinics/${clinic.id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        });
      } else {
        return await apiRequest("/api/clinics", {
          method: "POST", 
          body: JSON.stringify(data),
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/clinics"] });
      queryClient.invalidateQueries({ queryKey: ["/api/clinic-assignments"] });
      toast({
        title: "Success",
        description: clinic ? "Clinic updated successfully" : "Clinic created successfully",
      });
      onSuccess();
    },
    onError: () => {
      toast({
        title: "Error",
        description: clinic ? "Failed to update clinic" : "Failed to create clinic",
        variant: "destructive",
      });
    },
  });

  const onSubmit = (data: InsertClinic) => {
    mutation.mutate(data);
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <Label htmlFor="name">Clinic Name</Label>
        <Input
          id="name"
          {...form.register("name")}
          placeholder="General Prosthodontics Clinic"
        />
        {form.formState.errors.name && (
          <p className="text-sm text-red-600">{form.formState.errors.name.message}</p>
        )}
      </div>

      <div>
        <Label htmlFor="description">Description (Optional)</Label>
        <Textarea
          id="description"
          {...form.register("description")}
          placeholder="Brief description of the clinic..."
        />
        {form.formState.errors.description && (
          <p className="text-sm text-red-600">{form.formState.errors.description.message}</p>
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

      <div className="flex space-x-3">
        <Button type="submit" disabled={mutation.isPending} className="bg-medical-blue hover:bg-blue-700">
          {mutation.isPending ? "Saving..." : clinic ? "Update Clinic" : "Add Clinic"}
        </Button>
        <Button type="button" variant="outline" onClick={onSuccess}>
          Cancel
        </Button>
      </div>
    </form>
  );
}