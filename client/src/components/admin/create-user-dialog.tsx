import { useState } from "react";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { apiRequest } from "@/lib/queryClient";
import { createLocalUserSchema } from "@shared/schema";
import type { Department } from "@shared/schema";

interface CreateUserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const createUserWithRoleSchema = createLocalUserSchema.extend({
  departmentId: z.number().optional(),
  role: z.enum(["head", "member", "viewer", "reception", "secretary"]).optional(),
  canAssignEmergencies: z.boolean().optional(),
  canManageLeaves: z.boolean().optional(),
  canViewReports: z.boolean().optional(),
});

export function CreateUserDialog({ open, onOpenChange }: CreateUserDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Fetch departments for role assignment
  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ["/api/departments"],
  });

  const form = useForm<z.infer<typeof createUserWithRoleSchema>>({
    resolver: zodResolver(createUserWithRoleSchema),
    defaultValues: {
      username: "",
      password: "",
      firstName: "",
      lastName: "",
      email: "",
      isCenterHead: false,
      departmentId: undefined,
      role: undefined,
      canAssignEmergencies: false,
      canManageLeaves: false,
      canViewReports: false,
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: z.infer<typeof createUserWithRoleSchema>) => {
      // First create the user
      const userData = {
        username: data.username,
        password: data.password,
        firstName: data.firstName,
        lastName: data.lastName,
        email: data.email,
        isCenterHead: data.isCenterHead,
      };
      
      const userResponse = await apiRequest("/api/admin/users", {
        method: "POST",
        body: JSON.stringify(userData),
      });
      
      const user = await userResponse.json();

      // If department and role are specified, add them to the department
      if (data.departmentId && data.role) {
        await apiRequest(`/api/departments/${data.departmentId}/members`, {
          method: "POST",
          body: JSON.stringify({
            userId: user.id,
            departmentId: data.departmentId,
            role: data.role,
            canEdit: data.role === "head",
            canViewOthers: data.role === "head" || data.role === "viewer",
            canAssignEmergencies: data.canAssignEmergencies || data.role === "head" || data.role === "reception",
            canManageLeaves: data.canManageLeaves || data.role === "head" || data.role === "secretary",
            canViewReports: data.canViewReports || data.role === "head" || data.role === "reception" || data.role === "secretary",
          }),
        });
      }

      return user;
    },
    onSuccess: () => {
      toast({
        title: "Success",
        description: "User created and assigned to department successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["/api/admin/users"] });
      queryClient.invalidateQueries({ queryKey: ["/api/departments"] });
      form.reset();
      onOpenChange(false);
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: error.message || "Failed to create user",
        variant: "destructive",
      });
    },
  });

  const onSubmit = (data: z.infer<typeof createUserWithRoleSchema>) => {
    createMutation.mutate(data);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Create New User</DialogTitle>
          <DialogDescription>
            Create a new local user account for the medical center system.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="firstName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>First Name</FormLabel>
                    <FormControl>
                      <Input placeholder="John" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="lastName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Last Name</FormLabel>
                    <FormControl>
                      <Input placeholder="Doe" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="username"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Username</FormLabel>
                  <FormControl>
                    <Input placeholder="johndoe" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Password</FormLabel>
                  <FormControl>
                    <Input type="password" placeholder="Minimum 6 characters" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email (Optional)</FormLabel>
                  <FormControl>
                    <Input type="email" placeholder="john@example.com" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Department and Role Assignment Section */}
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium mb-3">Department Assignment</h4>
              <div className="space-y-4">
                <FormField
                  control={form.control}
                  name="departmentId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Department (Optional)</FormLabel>
                      <Select
                        value={field.value?.toString() || ""}
                        onValueChange={(value) => field.onChange(value ? parseInt(value) : undefined)}
                      >
                        <FormControl>
                          <SelectTrigger data-testid="select-department">
                            <SelectValue placeholder="Select a department" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {departments.map((dept) => (
                            <SelectItem key={dept.id} value={dept.id.toString()}>
                              {dept.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {form.watch("departmentId") && (
                  <FormField
                    control={form.control}
                    name="role"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Role</FormLabel>
                        <Select value={field.value || ""} onValueChange={field.onChange}>
                          <FormControl>
                            <SelectTrigger data-testid="select-user-role">
                              <SelectValue placeholder="Select a role" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="head">Department Head</SelectItem>
                            <SelectItem value="member">Staff Member</SelectItem>
                            <SelectItem value="reception">Reception</SelectItem>
                            <SelectItem value="secretary">Secretary</SelectItem>
                            <SelectItem value="viewer">View Only</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}

                {form.watch("role") === "reception" && (
                  <div className="text-xs text-gray-600 bg-green-50 p-2 rounded">
                    Reception role automatically includes emergency assignment permissions
                  </div>
                )}

                {form.watch("role") === "secretary" && (
                  <div className="text-xs text-gray-600 bg-blue-50 p-2 rounded">
                    Secretary role automatically includes leave management permissions
                  </div>
                )}
              </div>
            </div>
            <FormField
              control={form.control}
              name="isCenterHead"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <div className="space-y-1 leading-none">
                    <FormLabel>
                      Center Head
                    </FormLabel>
                    <p className="text-sm text-muted-foreground">
                      Grant full administrative access to all departments
                    </p>
                  </div>
                </FormItem>
              )}
            />
            <div className="flex justify-end space-x-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={createMutation.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create User"}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}