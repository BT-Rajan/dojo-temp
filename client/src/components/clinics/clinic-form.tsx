import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { insertClinicAssignmentSchema, type InsertClinicAssignment } from "@shared/schema";
import { getWeekdayName } from "@/lib/date-utils";
import { z } from "zod";

const formSchema = z.object({
  doctorId: z.number().min(1, "Please select a doctor"),
  clinicId: z.number().min(1, "Please select a clinic"),
  weekdays: z.array(z.number()).min(1, "Select at least one weekday"),
});

type FormData = z.infer<typeof formSchema>;

interface ClinicFormProps {
  onSuccess: () => void;
  departmentId?: number;
}

export function ClinicForm({ onSuccess, departmentId }: ClinicFormProps) {
  const { toast } = useToast();
  
  const { data: doctors } = useQuery({
    queryKey: departmentId ? ["/api/doctors", departmentId] : ["/api/doctors"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/doctors${params}`);
      if (!response.ok) throw new Error('Failed to fetch doctors');
      return response.json();
    },
  });

  const { data: clinics } = useQuery({
    queryKey: departmentId ? ["/api/clinics", departmentId] : ["/api/clinics"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/clinics${params}`);
      if (!response.ok) throw new Error('Failed to fetch clinics');
      return response.json();
    },
  });

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      doctorId: 0,
      clinicId: 0,
      weekdays: [],
    },
    mode: "onChange",
  });

  const mutation = useMutation({
    mutationFn: async (data: FormData) => {
      // Create multiple assignments for each selected weekday
      const promises = data.weekdays.map((weekday) =>
        apiRequest("/api/clinic-assignments", {
          method: "POST",
          body: JSON.stringify({
            doctorId: data.doctorId,
            clinicId: data.clinicId,
            weekday,
          }),
        })
      );
      await Promise.all(promises);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/clinic-assignments"] });
      queryClient.invalidateQueries({ queryKey: ["/api/clinics"] });
      toast({
        title: "Success",
        description: "Clinic assignments created successfully",
      });
      onSuccess();
    },
    onError: (error: any) => {
      toast({
        title: "Error",
        description: "Failed to create clinic assignments",
        variant: "destructive",
      });
    },
  });

  const onSubmit = (data: FormData) => {
    mutation.mutate(data);
  };

  const weekdays = [0, 1, 2, 3, 4]; // Sunday to Thursday

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <Label htmlFor="doctorId">Doctor</Label>
        <Select onValueChange={(value) => {
          form.setValue("doctorId", parseInt(value));
          form.trigger("doctorId");
        }}>
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
        <Label htmlFor="clinicId">Clinic</Label>
        <Select onValueChange={(value) => {
          form.setValue("clinicId", parseInt(value));
          form.trigger("clinicId");
        }}>
          <SelectTrigger>
            <SelectValue placeholder="Select Clinic" />
          </SelectTrigger>
          <SelectContent>
            {clinics?.map((clinic: any) => (
              <SelectItem key={clinic.id} value={clinic.id.toString()}>
                {clinic.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {form.formState.errors.clinicId && (
          <p className="text-sm text-red-600">{form.formState.errors.clinicId.message}</p>
        )}
      </div>

      <div>
        <Label>Weekdays</Label>
        <div className="grid grid-cols-2 gap-2 mt-2">
          {weekdays.map((weekday) => (
            <div key={weekday} className="flex items-center space-x-2">
              <Checkbox
                id={`weekday-${weekday}`}
                onCheckedChange={(checked) => {
                  const currentWeekdays = form.getValues("weekdays");
                  if (checked) {
                    form.setValue("weekdays", [...currentWeekdays, weekday]);
                  } else {
                    form.setValue("weekdays", currentWeekdays.filter((w) => w !== weekday));
                  }
                  form.trigger("weekdays");
                }}
              />
              <Label htmlFor={`weekday-${weekday}`} className="text-sm">
                {getWeekdayName(weekday)}
              </Label>
            </div>
          ))}
        </div>
        {form.formState.errors.weekdays && (
          <p className="text-sm text-red-600">{form.formState.errors.weekdays.message}</p>
        )}
      </div>

      <div className="flex space-x-3">
        <Button 
          type="submit" 
          disabled={mutation.isPending} 
          className="bg-medical-blue hover:bg-blue-700"
        >
          {mutation.isPending ? "Saving..." : "Save Assignment"}
        </Button>
        <Button type="button" variant="outline" onClick={onSuccess}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
