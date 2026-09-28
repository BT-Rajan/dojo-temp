import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { DoctorForm } from "./doctor-form";
import { CreateDoctorAccountDialog } from "./create-doctor-account-dialog";
import { useToast } from "@/hooks/use-toast";
import { queryClient } from "@/lib/queryClient";
import { apiRequest } from "@/lib/queryClient";
import { Plus, Edit, Trash2, Users } from "lucide-react";
import type { Doctor } from "@shared/schema";

interface DoctorManagementProps {
  departmentId?: number;
}

export function DoctorManagement({ departmentId }: DoctorManagementProps) {
  const [editingDoctor, setEditingDoctor] = useState<Doctor | null>(null);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const { toast } = useToast();

  const { data: doctors, isLoading } = useQuery({
    queryKey: departmentId ? ["/api/doctors", departmentId] : ["/api/doctors"],
    queryFn: async () => {
      const params = departmentId ? `?departmentId=${departmentId}` : '';
      const response = await fetch(`/api/doctors${params}`);
      if (!response.ok) throw new Error('Failed to fetch doctors');
      return response.json();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiRequest(`/api/doctors/${id}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/doctors"] });
      if (departmentId) {
        queryClient.invalidateQueries({ queryKey: ["/api/doctors", departmentId] });
      }
      toast({
        title: "Success",
        description: "Doctor deleted successfully",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to delete doctor",
        variant: "destructive",
      });
    },
  });

  const handleDelete = (id: number) => {
    deleteMutation.mutate(id);
  };

  const handleFormSuccess = () => {
    setEditingDoctor(null);
    setShowAddDialog(false);
    setShowEditDialog(false);
    queryClient.invalidateQueries({ queryKey: ["/api/doctors"] });
    if (departmentId) {
      queryClient.invalidateQueries({ queryKey: ["/api/doctors", departmentId] });
    }
  };

  const handleEditClick = (doctor: Doctor) => {
    setEditingDoctor(doctor);
    setShowEditDialog(true);
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <Card>
      <div className="p-6 border-b">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">Doctor Management</h3>
          <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
            <DialogTrigger asChild>
              <Button className="bg-medical-blue hover:bg-blue-700">
                <Plus className="mr-2 h-4 w-4" />
                Add New Doctor
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add New Doctor</DialogTitle>
              </DialogHeader>
              <DoctorForm onSuccess={handleFormSuccess} departmentId={departmentId} />
            </DialogContent>
          </Dialog>
        </div>
      </div>
      <CardContent className="p-6">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-medium text-gray-900">Doctor</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Title</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Civil ID</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">File Number</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Phone</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Status</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {doctors?.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center">
                    <div className="flex flex-col items-center justify-center">
                      <Users className="h-12 w-12 text-gray-400 mb-4" />
                      <h3 className="text-lg font-medium text-gray-900 mb-2">No doctors in this department</h3>
                      <p className="text-gray-500 mb-4">Get started by adding your first doctor to this department.</p>
                      <Button 
                        onClick={() => setShowAddDialog(true)}
                        className="bg-medical-blue hover:bg-blue-700"
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Add First Doctor
                      </Button>
                    </div>
                  </td>
                </tr>
              ) : (
                doctors?.map((doctor: Doctor) => (
                <tr key={doctor.id} className="hover:bg-gray-50">
                  <td className="py-4 px-4">
                    <div className="flex items-center">
                      <div className="w-10 h-10 bg-medical-blue/10 rounded-full flex items-center justify-center mr-3">
                        <Users className="text-medical-blue text-sm" />
                      </div>
                      <div>
                        <h4 className="text-sm font-medium text-gray-900">{doctor.name}</h4>
                        <p className="text-xs text-gray-500">{doctor.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-sm text-gray-900">{doctor.title}</td>
                  <td className="py-4 px-4 text-sm text-gray-900">{doctor.civilId}</td>
                  <td className="py-4 px-4 text-sm text-gray-900">{doctor.fileNumber}</td>
                  <td className="py-4 px-4 text-sm text-gray-900">{doctor.phone}</td>
                  <td className="py-4 px-4">
                    <Badge variant="secondary" className="bg-healthcare-green/10 text-healthcare-green">
                      Available
                    </Badge>
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center space-x-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditClick(doctor)}
                        className="text-medical-blue hover:text-blue-700"
                        data-testid={`button-edit-doctor-${doctor.id}`}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <CreateDoctorAccountDialog doctor={doctor}>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-green-600 hover:text-green-700"
                          data-testid={`button-create-account-${doctor.id}`}
                        >
                          <Plus className="h-4 w-4" />
                        </Button>
                      </CreateDoctorAccountDialog>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-600 hover:text-red-700"
                            data-testid={`button-delete-doctor-${doctor.id}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This action cannot be undone. This will permanently delete the doctor's record.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction onClick={() => handleDelete(doctor.id)}>
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </td>
                </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </CardContent>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Doctor</DialogTitle>
          </DialogHeader>
          <DoctorForm doctor={editingDoctor} onSuccess={handleFormSuccess} departmentId={departmentId} />
        </DialogContent>
      </Dialog>
    </Card>
  );
}
