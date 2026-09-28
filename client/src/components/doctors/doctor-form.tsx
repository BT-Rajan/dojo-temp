import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import { insertDoctorSchema, type Doctor, type InsertDoctor } from "@shared/schema";

interface DoctorFormProps {
  doctor?: Doctor | null;
  onSuccess: () => void;
  departmentId?: number;
}

export function DoctorForm({ doctor, onSuccess, departmentId }: DoctorFormProps) {
  const { toast } = useToast();
  
  const form = useForm<InsertDoctor>({
    resolver: zodResolver(insertDoctorSchema),
    defaultValues: {
      name: doctor?.name || "",
      title: doctor?.title || "",
      civilId: doctor?.civilId || "",
      fileNumber: doctor?.fileNumber || "",
      phone: doctor?.phone || "",
      email: doctor?.email || "",
      departmentId: doctor?.departmentId || departmentId,
    },
  });

  const mutation = useMutation({
    mutationFn: async (data: InsertDoctor) => {
      if (doctor) {
        return await apiRequest(`/api/doctors/${doctor.id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        });
      } else {
        return await apiRequest("/api/doctors", {
          method: "POST",
          body: JSON.stringify(data),
        });
      }
    },
    onSuccess: () => {
      toast({
        title: "Success",
        description: doctor ? "Doctor updated successfully" : "Doctor created successfully",
      });
      onSuccess();
    },
    onError: () => {
      toast({
        title: "Error",
        description: doctor ? "Failed to update doctor" : "Failed to create doctor",
        variant: "destructive",
      });
    },
  });

  const onSubmit = (data: InsertDoctor) => {
    mutation.mutate(data);
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          {...form.register("name")}
          placeholder="Dr. John Doe"
        />
        {form.formState.errors.name && (
          <p className="text-sm text-red-600">{form.formState.errors.name.message}</p>
        )}
      </div>

      <div>
        <Label htmlFor="title">Title</Label>
        <Input
          id="title"
          {...form.register("title")}
          placeholder="Senior Prosthodontist"
        />
        {form.formState.errors.title && (
          <p className="text-sm text-red-600">{form.formState.errors.title.message}</p>
        )}
      </div>

      <div>
        <Label htmlFor="civilId">Civil ID</Label>
        <Input
          id="civilId"
          {...form.register("civilId")}
          placeholder="12345678901"
        />
        {form.formState.errors.civilId && (
          <p className="text-sm text-red-600">{form.formState.errors.civilId.message}</p>
        )}
      </div>

      <div>
        <Label htmlFor="fileNumber">File Number</Label>
        <Input
          id="fileNumber"
          {...form.register("fileNumber")}
          placeholder="DOC-2024-001"
        />
        {form.formState.errors.fileNumber && (
          <p className="text-sm text-red-600">{form.formState.errors.fileNumber.message}</p>
        )}
      </div>

      <div>
        <Label htmlFor="phone">Phone</Label>
        <Input
          id="phone"
          {...form.register("phone")}
          placeholder="+965 1234 5678"
        />
        {form.formState.errors.phone && (
          <p className="text-sm text-red-600">{form.formState.errors.phone.message}</p>
        )}
      </div>

      <div>
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          {...form.register("email")}
          placeholder="john.doe@hospital.com"
        />
        {form.formState.errors.email && (
          <p className="text-sm text-red-600">{form.formState.errors.email.message}</p>
        )}
      </div>

      <div className="flex space-x-3">
        <Button type="submit" disabled={mutation.isPending} className="bg-medical-blue hover:bg-blue-700">
          {mutation.isPending ? "Saving..." : doctor ? "Update Doctor" : "Add Doctor"}
        </Button>
        <Button type="button" variant="outline" onClick={onSuccess}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
