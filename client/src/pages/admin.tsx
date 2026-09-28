import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { 
  Users, 
  Shield, 
  Building, 
  UserCheck, 
  ArrowLeft,
  Plus,
  Settings,
  Trash2,
  Edit,
  Key,
  User as UserIcon,
  Stethoscope,
  Check,
  X,
  UserCog,
  Hospital
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { apiRequest, queryClient } from "@/lib/queryClient";
import type { User, Department, Doctor, Center } from "@shared/schema";
import { CreateCenterDialog } from "@/components/centers/create-center-dialog";

const updateCenterNameSchema = z.object({
  centerName: z.string().min(1).max(100),
});

const createUserSchema = z.object({
  username: z.string().min(3, "Username must be at least 3 characters"),
  password: z.string().min(6, "Password must be at least 6 characters"),
  firstName: z.string().min(1, "First name is required"),
  lastName: z.string().min(1, "Last name is required"),
  email: z.string().email().optional().or(z.literal("")),
  isCenterHead: z.boolean().default(false),
});

const createDepartmentSchema = z.object({
  name: z.string().min(1, "Department name is required"),
  description: z.string().optional(),
});

const createDoctorCredentialsSchema = z.object({
  doctorId: z.number(),
  username: z.string().min(3, "Username must be at least 3 characters"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});

const changePasswordSchema = z.object({
  newPassword: z.string().min(6, "Password must be at least 6 characters"),
  confirmPassword: z.string().min(6, "Password must be at least 6 characters"),
}).refine((data) => data.newPassword === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

const assignRoleSchema = z.object({
  userId: z.string().min(1, "User is required"),
  departmentId: z.number().optional(),
  role: z.enum(["head", "member", "reception", "secretary", "viewer"]),
  canAssignEmergencies: z.boolean().default(false),
  canManageLeaves: z.boolean().default(false),
  canViewReports: z.boolean().default(false),
});

interface DepartmentMember {
  id: number;
  userId: string;
  departmentId: number;
  role: string;
  canEdit: boolean;
  canViewOthers: boolean;
  canAssignEmergencies: boolean;
  canManageLeaves: boolean;
  canViewReports: boolean;
  user?: {
    id: string;
    firstName: string;
    lastName: string;
    email: string;
  };
}

const roleLabels: Record<string, string> = {
  head: "Department Head",
  member: "Staff Member", 
  viewer: "View Only",
  reception: "Reception",
  secretary: "Secretary"
};

const roleColors: Record<string, string> = {
  head: "bg-purple-100 text-purple-800",
  member: "bg-blue-100 text-blue-800",
  viewer: "bg-gray-100 text-gray-800",
  reception: "bg-green-100 text-green-800",
  secretary: "bg-yellow-100 text-yellow-800"
};

export default function Admin() {
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("departments");
  const [selectedAdminCenterId, setSelectedAdminCenterId] = useState<string>("");
  
  const [showCreateUserDialog, setShowCreateUserDialog] = useState(false);
  const [showCreateCenterDialog, setShowCreateCenterDialog] = useState(false);
  const [editingCenterId, setEditingCenterId] = useState<number | null>(null);
  const [editingCenterName, setEditingCenterName] = useState("");
  const [showCreateDepartmentDialog, setShowCreateDepartmentDialog] = useState(false);
  const [showDoctorCredentialsDialog, setShowDoctorCredentialsDialog] = useState(false);
  const [showChangePasswordDialog, setShowChangePasswordDialog] = useState(false);
  const [showAssignRoleDialog, setShowAssignRoleDialog] = useState(false);
  const [showEditPermissionsDialog, setShowEditPermissionsDialog] = useState(false);
  const [selectedDoctor, setSelectedDoctor] = useState<Doctor | null>(null);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [userToEdit, setUserToEdit] = useState<User | null>(null);
  const [userToChangePassword, setUserToChangePassword] = useState<User | null>(null);
  const [departmentToDelete, setDepartmentToDelete] = useState<Department | null>(null);
  const [selectedDepartmentForRoles, setSelectedDepartmentForRoles] = useState<number | null>(null);
  const [memberToEdit, setMemberToEdit] = useState<DepartmentMember | null>(null);
  const [memberToRemove, setMemberToRemove] = useState<DepartmentMember | null>(null);

  const { data: centerNameData } = useQuery<{ centerName: string }>({
    queryKey: ["/api/settings/center-name"],
  });

  const centerNameForm = useForm<z.infer<typeof updateCenterNameSchema>>({
    resolver: zodResolver(updateCenterNameSchema),
    defaultValues: {
      centerName: centerNameData?.centerName || "Medical Center",
    },
  });

  useEffect(() => {
    if (centerNameData?.centerName) {
      centerNameForm.reset({ centerName: centerNameData.centerName });
    }
  }, [centerNameData, centerNameForm]);

  const { data: allCenters = [] } = useQuery<Center[]>({ queryKey: ["/api/centers"] });

  useEffect(() => {
    if (allCenters.length > 0 && !selectedAdminCenterId) {
      setSelectedAdminCenterId(allCenters[0].id.toString());
    }
  }, [allCenters]);

  const handleAdminCenterChange = (centerId: string) => {
    setSelectedAdminCenterId(centerId);
    setSelectedDepartmentForRoles(null);
  };

  const { data: users = [], isLoading: isUsersLoading } = useQuery<User[]>({
    queryKey: ["/api/admin/users", selectedAdminCenterId],
    queryFn: async () => {
      const url = selectedAdminCenterId
        ? `/api/admin/users?centerId=${selectedAdminCenterId}`
        : "/api/admin/users";
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch users");
      return res.json();
    },
    enabled: !!selectedAdminCenterId,
  });

  const { data: departments = [], isLoading: isDepartmentsLoading } = useQuery<Department[]>({
    queryKey: ["/api/user/departments", selectedAdminCenterId],
    queryFn: async () => {
      const url = selectedAdminCenterId
        ? `/api/user/departments?centerId=${selectedAdminCenterId}`
        : "/api/departments";
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch departments");
      return res.json();
    },
    enabled: !!selectedAdminCenterId,
  });

  const { data: doctors = [], isLoading: isDoctorsLoading } = useQuery<Doctor[]>({
    queryKey: ["/api/doctors", selectedAdminCenterId],
    queryFn: async () => {
      const url = selectedAdminCenterId
        ? `/api/doctors?centerId=${selectedAdminCenterId}`
        : "/api/doctors";
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch doctors");
      return res.json();
    },
    enabled: !!selectedAdminCenterId,
  });

  const createUserForm = useForm<z.infer<typeof createUserSchema>>({
    resolver: zodResolver(createUserSchema),
    defaultValues: {
      username: "",
      password: "",
      firstName: "",
      lastName: "",
      email: "",
      isCenterHead: false,
    },
  });

  const createDepartmentForm = useForm<z.infer<typeof createDepartmentSchema>>({
    resolver: zodResolver(createDepartmentSchema),
    defaultValues: {
      name: "",
      description: "",
    },
  });

  const doctorCredentialsForm = useForm<z.infer<typeof createDoctorCredentialsSchema>>({
    resolver: zodResolver(createDoctorCredentialsSchema),
    defaultValues: {
      doctorId: 0,
      username: "",
      password: "",
    },
  });

  const changePasswordForm = useForm<z.infer<typeof changePasswordSchema>>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      newPassword: "",
      confirmPassword: "",
    },
  });

  const assignRoleForm = useForm<z.infer<typeof assignRoleSchema>>({
    resolver: zodResolver(assignRoleSchema),
    defaultValues: {
      userId: "",
      departmentId: 0,
      role: "member",
      canAssignEmergencies: false,
      canManageLeaves: false,
      canViewReports: false,
    },
  });

  const { data: departmentMembers = [], isLoading: isMembersLoading } = useQuery<DepartmentMember[]>({
    queryKey: ["/api/departments", selectedDepartmentForRoles, "members"],
    queryFn: async () => {
      if (!selectedDepartmentForRoles) return [];
      const response = await fetch(`/api/departments/${selectedDepartmentForRoles}/members`);
      if (!response.ok) return [];
      return response.json();
    },
    enabled: !!selectedDepartmentForRoles,
  });

  const createUserMutation = useMutation({
    mutationFn: async (data: z.infer<typeof createUserSchema>) => {
      return await apiRequest("/api/admin/users", {
        method: "POST",
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "User created successfully" });
      queryClient.invalidateQueries({ predicate: (query) => (query.queryKey[0] as string)?.startsWith("/api/admin/users") || query.queryKey[0] === "/api/admin/users" });
      setShowCreateUserDialog(false);
      createUserForm.reset();
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to create user", variant: "destructive" });
    },
  });

  const createDepartmentMutation = useMutation({
    mutationFn: async (data: z.infer<typeof createDepartmentSchema>) => {
      return await apiRequest("/api/departments", {
        method: "POST",
        body: JSON.stringify({ ...data, centerId: selectedAdminCenterId ? parseInt(selectedAdminCenterId) : undefined }),
      });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Department created successfully" });
      queryClient.invalidateQueries({ predicate: (query) => {
        const key = query.queryKey[0] as string;
        return key === "/api/departments" || key === "/api/user/departments";
      }});
      setShowCreateDepartmentDialog(false);
      createDepartmentForm.reset();
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to create department", variant: "destructive" });
    },
  });

  const createDoctorCredentialsMutation = useMutation({
    mutationFn: async (data: z.infer<typeof createDoctorCredentialsSchema>) => {
      return await apiRequest("/api/doctor/create-account", {
        method: "POST",
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Doctor portal credentials created successfully" });
      queryClient.invalidateQueries({ predicate: (query) => (query.queryKey[0] as string) === "/api/doctors" });
      setShowDoctorCredentialsDialog(false);
      setSelectedDoctor(null);
      doctorCredentialsForm.reset();
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to create doctor credentials", variant: "destructive" });
    },
  });

  const deleteUserMutation = useMutation({
    mutationFn: async (userId: string) => {
      return await apiRequest(`/api/admin/users/${userId}`, { method: "DELETE" });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "User deleted successfully" });
      queryClient.invalidateQueries({ predicate: (query) => (query.queryKey[0] as string) === "/api/admin/users" });
      setUserToDelete(null);
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to delete user", variant: "destructive" });
    },
  });

  const deleteDepartmentMutation = useMutation({
    mutationFn: async (departmentId: number) => {
      return await apiRequest(`/api/departments/${departmentId}`, { method: "DELETE" });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Department deleted successfully" });
      queryClient.invalidateQueries({ predicate: (query) => {
        const key = query.queryKey[0] as string;
        return key === "/api/departments" || key === "/api/user/departments";
      }});
      setDepartmentToDelete(null);
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to delete department", variant: "destructive" });
    },
  });

  const setDepartmentHeadMutation = useMutation({
    mutationFn: async ({ departmentId, userId }: { departmentId: number; userId: string }) => {
      return await apiRequest(`/api/admin/departments/${departmentId}/set-head`, {
        method: "POST",
        body: JSON.stringify({ userId }),
      });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Department head assigned successfully" });
      queryClient.invalidateQueries({ predicate: (query) => {
        const key = query.queryKey[0] as string;
        return key === "/api/departments" || key === "/api/user/departments";
      }});
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to assign department head", variant: "destructive" });
    },
  });

  const updateCenterNameMutation = useMutation({
    mutationFn: async (data: z.infer<typeof updateCenterNameSchema>) => {
      return await apiRequest("/api/settings/center-name", {
        method: "PUT",
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Center name updated successfully" });
      queryClient.invalidateQueries({ queryKey: ["/api/settings/center-name"] });
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to update center name", variant: "destructive" });
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: async ({ userId, newPassword }: { userId: string; newPassword: string }) => {
      return await apiRequest(`/api/admin/users/${userId}/password`, {
        method: "PATCH",
        body: JSON.stringify({ newPassword }),
      });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Password changed successfully" });
      setShowChangePasswordDialog(false);
      setUserToChangePassword(null);
      changePasswordForm.reset();
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to change password", variant: "destructive" });
    },
  });

  const assignRoleMutation = useMutation({
    mutationFn: async (data: z.infer<typeof assignRoleSchema>) => {
      const permissions = getDefaultPermissionsForRole(data.role);
      return await apiRequest(`/api/departments/${data.departmentId}/members`, {
        method: "POST",
        body: JSON.stringify({
          userId: data.userId,
          departmentId: data.departmentId,
          role: data.role,
          canEdit: permissions.canEdit,
          canViewOthers: permissions.canViewOthers,
          canAssignEmergencies: data.canAssignEmergencies || permissions.canAssignEmergencies,
          canManageLeaves: data.canManageLeaves || permissions.canManageLeaves,
          canViewReports: data.canViewReports || permissions.canViewReports,
        }),
      });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Staff member assigned to department successfully" });
      queryClient.invalidateQueries({ queryKey: ["/api/departments", selectedDepartmentForRoles, "members"] });
      queryClient.invalidateQueries({ queryKey: ["/api/departments"] });
      setShowAssignRoleDialog(false);
      assignRoleForm.reset();
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to assign staff member", variant: "destructive" });
    },
  });

  const updateMemberPermissionsMutation = useMutation({
    mutationFn: async ({ userId, departmentId, updates }: { userId: string; departmentId: number; updates: any }) => {
      return await apiRequest(`/api/departments/${departmentId}/members/${userId}`, {
        method: "PUT",
        body: JSON.stringify(updates),
      });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Permissions updated successfully" });
      queryClient.invalidateQueries({ queryKey: ["/api/departments", selectedDepartmentForRoles, "members"] });
      setShowEditPermissionsDialog(false);
      setMemberToEdit(null);
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to update permissions", variant: "destructive" });
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: async ({ userId, departmentId }: { userId: string; departmentId: number }) => {
      return await apiRequest(`/api/departments/${departmentId}/members/${userId}`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Staff member removed from department" });
      queryClient.invalidateQueries({ queryKey: ["/api/departments", selectedDepartmentForRoles, "members"] });
      setMemberToRemove(null);
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to remove staff member", variant: "destructive" });
    },
  });

  const renameCenterMutation = useMutation({
    mutationFn: async ({ centerId, newName }: { centerId: number; newName: string }) => {
      return await apiRequest(`/api/centers/${centerId}`, {
        method: "PUT",
        body: JSON.stringify({ name: newName }),
      });
    },
    onSuccess: () => {
      toast({ title: "Success", description: "Center name updated successfully" });
      queryClient.invalidateQueries({ queryKey: ["/api/centers"] });
      queryClient.invalidateQueries({ queryKey: ["/api/user/centers"] });
      setEditingCenterId(null);
      setEditingCenterName("");
    },
    onError: (error: any) => {
      toast({ title: "Error", description: error.message || "Failed to update center name", variant: "destructive" });
    },
  });

  const getDefaultPermissionsForRole = (role: string) => {
    switch (role) {
      case "head":
        return { canEdit: true, canViewOthers: true, canAssignEmergencies: true, canManageLeaves: true, canViewReports: true };
      case "reception":
        return { canEdit: false, canViewOthers: false, canAssignEmergencies: true, canManageLeaves: false, canViewReports: true };
      case "secretary":
        return { canEdit: false, canViewOthers: false, canAssignEmergencies: false, canManageLeaves: true, canViewReports: true };
      case "viewer":
        return { canEdit: false, canViewOthers: true, canAssignEmergencies: false, canManageLeaves: false, canViewReports: false };
      default:
        return { canEdit: false, canViewOthers: false, canAssignEmergencies: false, canManageLeaves: false, canViewReports: false };
    }
  };

  const openDoctorCredentialsDialog = (doctor: Doctor) => {
    setSelectedDoctor(doctor);
    doctorCredentialsForm.reset({
      doctorId: doctor.id,
      username: doctor.username || "",
      password: "",
    });
    setShowDoctorCredentialsDialog(true);
  };

  if (!user || !user.isCenterHead) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle>Access Denied</CardTitle>
            <CardDescription>
              Only Center Heads can access the administration panel.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => window.location.href = "/"} data-testid="button-go-back">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Go Back
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto p-6">
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                Center Administration
              </h1>
              <p className="text-gray-600 dark:text-gray-300 mt-2">
                Manage departments, users, and doctor portal access
              </p>
            </div>
            <div className="flex items-center space-x-3">
              {allCenters.length > 0 && (
                <Select value={selectedAdminCenterId} onValueChange={handleAdminCenterChange}>
                  <SelectTrigger className="w-64">
                    <Hospital className="h-4 w-4 mr-2 text-blue-600" />
                    <SelectValue placeholder="Select center" />
                  </SelectTrigger>
                  <SelectContent>
                    {allCenters.map((center) => (
                      <SelectItem key={center.id} value={center.id.toString()}>
                        {center.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Button variant="outline" onClick={() => window.location.href = "/"} data-testid="button-back-home">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Home
              </Button>
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Users in Center</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold" data-testid="text-total-users">{users.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Center Heads</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold" data-testid="text-center-heads">
                {users.filter(u => u.isCenterHead).length}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Departments</CardTitle>
              <Building className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold" data-testid="text-total-departments">{departments.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Doctors with Portal</CardTitle>
              <Stethoscope className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold" data-testid="text-doctors-with-portal">
                {doctors.filter(d => d.username).length} / {doctors.length}
              </div>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="centers" data-testid="tab-centers">
              <Hospital className="mr-2 h-4 w-4" />
              Centers
            </TabsTrigger>
            <TabsTrigger value="departments" data-testid="tab-departments">
              <Building className="mr-2 h-4 w-4" />
              Departments
            </TabsTrigger>
            <TabsTrigger value="users" data-testid="tab-users">
              <Users className="mr-2 h-4 w-4" />
              Users
            </TabsTrigger>
            <TabsTrigger value="staff-roles" data-testid="tab-staff-roles">
              <UserCog className="mr-2 h-4 w-4" />
              Staff Roles
            </TabsTrigger>
            <TabsTrigger value="doctor-portal" data-testid="tab-doctor-portal">
              <Stethoscope className="mr-2 h-4 w-4" />
              Doctor Portal
            </TabsTrigger>
            <TabsTrigger value="settings" data-testid="tab-settings">
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </TabsTrigger>
          </TabsList>

          <TabsContent value="centers" className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Center Management</CardTitle>
                    <CardDescription>Manage your medical centers</CardDescription>
                  </div>
                  <Button onClick={() => setShowCreateCenterDialog(true)} data-testid="button-add-center">
                    <Plus className="mr-2 h-4 w-4" />
                    Create Center
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {allCenters.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No centers created yet. Click "Create Center" to create one.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {allCenters.map((center) => (
                        <TableRow key={center.id}>
                          <TableCell className="font-medium">
                            {editingCenterId === center.id ? (
                              <div className="flex items-center gap-2">
                                <Input
                                  value={editingCenterName}
                                  onChange={(e) => setEditingCenterName(e.target.value)}
                                  className="h-8 w-48"
                                  data-testid={`input-edit-center-name-${center.id}`}
                                />
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => {
                                    if (editingCenterName.trim()) {
                                      renameCenterMutation.mutate({ centerId: center.id, newName: editingCenterName.trim() });
                                    }
                                  }}
                                  disabled={renameCenterMutation.isPending}
                                  data-testid={`button-save-center-name-${center.id}`}
                                >
                                  <Check className="h-4 w-4" />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => { setEditingCenterId(null); setEditingCenterName(""); }}
                                  data-testid={`button-cancel-center-name-${center.id}`}
                                >
                                  <X className="h-4 w-4" />
                                </Button>
                              </div>
                            ) : (
                              center.name
                            )}
                          </TableCell>
                          <TableCell>{center.description || "—"}</TableCell>
                          <TableCell>
                            <Badge variant={center.isActive ? "default" : "secondary"}>
                              {center.isActive ? "Active" : "Inactive"}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {center.createdAt ? new Date(center.createdAt).toLocaleDateString() : "—"}
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setEditingCenterId(center.id);
                                setEditingCenterName(center.name);
                              }}
                              data-testid={`button-edit-center-${center.id}`}
                            >
                              <Edit className="h-4 w-4 mr-1" />
                              Edit Name
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="departments" className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Department Management</CardTitle>
                    <CardDescription>Add, remove, and manage departments</CardDescription>
                  </div>
                  <Button onClick={() => setShowCreateDepartmentDialog(true)} data-testid="button-add-department">
                    <Plus className="mr-2 h-4 w-4" />
                    Add Department
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {isDepartmentsLoading ? (
                  <div className="text-center py-4">Loading departments...</div>
                ) : departments.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No departments created yet. Click "Add Department" to create one.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Department Name</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Department Head</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {departments.map((dept) => (
                        <TableRow key={dept.id} data-testid={`row-department-${dept.id}`}>
                          <TableCell className="font-medium">{dept.name}</TableCell>
                          <TableCell>{dept.description || "-"}</TableCell>
                          <TableCell>
                            <Select
                              value={dept.headUserId || "unassigned"}
                              onValueChange={(userId) => setDepartmentHeadMutation.mutate({
                                departmentId: dept.id,
                                userId: userId === "unassigned" ? "" : userId
                              })}
                            >
                              <SelectTrigger className="w-48" data-testid={`select-head-${dept.id}`}>
                                <SelectValue placeholder="Select head" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="unassigned">No head assigned</SelectItem>
                                {users.map((userItem) => (
                                  <SelectItem key={userItem.id} value={userItem.id}>
                                    {userItem.firstName} {userItem.lastName}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setDepartmentToDelete(dept)}
                              className="text-red-600 hover:text-red-800 hover:bg-red-50"
                              data-testid={`button-delete-department-${dept.id}`}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="users" className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>User Management</CardTitle>
                    <CardDescription>Add, remove, and manage system users</CardDescription>
                  </div>
                  <Button onClick={() => setShowCreateUserDialog(true)} data-testid="button-add-user">
                    <Plus className="mr-2 h-4 w-4" />
                    Add User
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {isUsersLoading ? (
                  <div className="text-center py-4">Loading users...</div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Username</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map((userItem) => (
                        <TableRow key={userItem.id} data-testid={`row-user-${userItem.id}`}>
                          <TableCell className="font-medium">
                            {userItem.firstName} {userItem.lastName}
                          </TableCell>
                          <TableCell>{userItem.username || "-"}</TableCell>
                          <TableCell>{userItem.email || "-"}</TableCell>
                          <TableCell>
                            {userItem.isCenterHead ? (
                              <Badge className="bg-red-100 text-red-800">Center Head</Badge>
                            ) : userItem.isLocalAccount ? (
                              <Badge variant="secondary">Local User</Badge>
                            ) : (
                              <Badge variant="outline">Replit User</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end space-x-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setUserToChangePassword(userItem);
                                  setShowChangePasswordDialog(true);
                                }}
                                data-testid={`button-change-password-${userItem.id}`}
                                title="Change Password"
                              >
                                <Key className="h-4 w-4" />
                              </Button>
                              {userItem.id !== user?.id && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setUserToDelete(userItem)}
                                  className="text-red-600 hover:text-red-800"
                                  data-testid={`button-delete-user-${userItem.id}`}
                                  title="Delete User"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="staff-roles" className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Staff Role Management</CardTitle>
                    <CardDescription>Assign users to departments and manage their access permissions</CardDescription>
                  </div>
                  {selectedDepartmentForRoles && (
                    <Button onClick={() => setShowAssignRoleDialog(true)} data-testid="button-assign-role">
                      <Plus className="mr-2 h-4 w-4" />
                      Assign Staff Member
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium mb-2 block">Select Department</label>
                    <Select
                      value={selectedDepartmentForRoles?.toString() || ""}
                      onValueChange={(value) => setSelectedDepartmentForRoles(value ? parseInt(value) : null)}
                    >
                      <SelectTrigger className="w-full max-w-sm" data-testid="select-department-for-roles">
                        <SelectValue placeholder="Choose a department to manage staff" />
                      </SelectTrigger>
                      <SelectContent>
                        {departments.map((dept) => (
                          <SelectItem key={dept.id} value={dept.id.toString()}>
                            {dept.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {selectedDepartmentForRoles && (
                    <div className="mt-6">
                      {isMembersLoading ? (
                        <div className="text-center py-4">Loading staff members...</div>
                      ) : departmentMembers.length === 0 ? (
                        <div className="text-center py-8 text-gray-500">
                          <UserCog className="mx-auto h-12 w-12 text-gray-400 mb-2" />
                          <p>No staff members assigned to this department yet.</p>
                          <p className="text-sm">Click "Assign Staff Member" to add someone.</p>
                        </div>
                      ) : (
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Name</TableHead>
                              <TableHead>Role</TableHead>
                              <TableHead>Permissions</TableHead>
                              <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {departmentMembers.map((member) => (
                              <TableRow key={member.id} data-testid={`row-member-${member.id}`}>
                                <TableCell className="font-medium">
                                  {member.user?.firstName} {member.user?.lastName}
                                  <div className="text-xs text-gray-500">{member.user?.email}</div>
                                </TableCell>
                                <TableCell>
                                  <Badge className={roleColors[member.role] || "bg-gray-100 text-gray-800"}>
                                    {roleLabels[member.role] || member.role}
                                  </Badge>
                                </TableCell>
                                <TableCell>
                                  <div className="flex flex-wrap gap-1">
                                    {member.canAssignEmergencies && (
                                      <Badge variant="outline" className="text-xs bg-green-50">Emergency</Badge>
                                    )}
                                    {member.canManageLeaves && (
                                      <Badge variant="outline" className="text-xs bg-blue-50">Leaves</Badge>
                                    )}
                                    {member.canViewReports && (
                                      <Badge variant="outline" className="text-xs bg-purple-50">Reports</Badge>
                                    )}
                                    {member.canEdit && (
                                      <Badge variant="outline" className="text-xs bg-orange-50">Edit</Badge>
                                    )}
                                  </div>
                                </TableCell>
                                <TableCell className="text-right">
                                  <div className="flex items-center justify-end space-x-2">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => {
                                        setMemberToEdit(member);
                                        setShowEditPermissionsDialog(true);
                                      }}
                                      data-testid={`button-edit-permissions-${member.id}`}
                                      title="Edit Permissions"
                                    >
                                      <Edit className="h-4 w-4" />
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => setMemberToRemove(member)}
                                      className="text-red-600 hover:text-red-800"
                                      data-testid={`button-remove-member-${member.id}`}
                                      title="Remove from Department"
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      )}
                    </div>
                  )}

                  {!selectedDepartmentForRoles && (
                    <div className="text-center py-8 text-gray-500">
                      <Building className="mx-auto h-12 w-12 text-gray-400 mb-2" />
                      <p>Select a department to manage staff roles and permissions.</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Role Descriptions</CardTitle>
                <CardDescription>Understanding the different staff roles and their default permissions</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div className="border rounded-lg p-4">
                    <Badge className={roleColors.head}>Department Head</Badge>
                    <p className="text-sm mt-2 text-gray-600">Full access to department management including editing, emergency assignments, leave management, and reports.</p>
                  </div>
                  <div className="border rounded-lg p-4">
                    <Badge className={roleColors.reception}>Reception</Badge>
                    <p className="text-sm mt-2 text-gray-600">Can assign emergency walk-in patients to doctors and view reports. Ideal for front desk staff.</p>
                  </div>
                  <div className="border rounded-lg p-4">
                    <Badge className={roleColors.secretary}>Secretary</Badge>
                    <p className="text-sm mt-2 text-gray-600">Can manage doctor leaves and permissions, and view reports. Ideal for administrative assistants.</p>
                  </div>
                  <div className="border rounded-lg p-4">
                    <Badge className={roleColors.member}>Staff Member</Badge>
                    <p className="text-sm mt-2 text-gray-600">Basic department access without special permissions. Custom permissions can be assigned.</p>
                  </div>
                  <div className="border rounded-lg p-4">
                    <Badge className={roleColors.viewer}>View Only</Badge>
                    <p className="text-sm mt-2 text-gray-600">Can view schedules from other departments. No editing or management capabilities.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="doctor-portal" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Doctor Portal Access</CardTitle>
                <CardDescription>
                  Create username and password credentials for doctors to access their personal portal
                </CardDescription>
              </CardHeader>
              <CardContent>
                {isDoctorsLoading ? (
                  <div className="text-center py-4">Loading doctors...</div>
                ) : doctors.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No doctors found. Add doctors to departments first.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Doctor Name</TableHead>
                        <TableHead>Title</TableHead>
                        <TableHead>Department</TableHead>
                        <TableHead>Portal Username</TableHead>
                        <TableHead>Portal Status</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {doctors.map((doctor) => {
                        const department = departments.find(d => d.id === doctor.departmentId);
                        return (
                          <TableRow key={doctor.id} data-testid={`row-doctor-${doctor.id}`}>
                            <TableCell className="font-medium">{doctor.name}</TableCell>
                            <TableCell>{doctor.title}</TableCell>
                            <TableCell>{department?.name || "-"}</TableCell>
                            <TableCell>{doctor.username || "-"}</TableCell>
                            <TableCell>
                              {doctor.username ? (
                                <Badge className="bg-green-100 text-green-800">
                                  <Check className="mr-1 h-3 w-3" />
                                  Active
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-gray-500">
                                  <X className="mr-1 h-3 w-3" />
                                  No Access
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                size="sm"
                                variant={doctor.username ? "outline" : "default"}
                                onClick={() => openDoctorCredentialsDialog(doctor)}
                                data-testid={`button-manage-credentials-${doctor.id}`}
                              >
                                <Key className="mr-2 h-4 w-4" />
                                {doctor.username ? "Update Credentials" : "Create Credentials"}
                              </Button>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="settings" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Settings className="mr-2 h-5 w-5" />
                  Center Settings
                </CardTitle>
                <CardDescription>
                  Configure medical center information
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Form {...centerNameForm}>
                  <form onSubmit={centerNameForm.handleSubmit((data) => updateCenterNameMutation.mutate(data))} className="space-y-4">
                    <FormField
                      control={centerNameForm.control}
                      name="centerName"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Center Name</FormLabel>
                          <FormControl>
                            <Input placeholder="Medical Center" {...field} data-testid="input-center-name" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <Button 
                      type="submit" 
                      disabled={updateCenterNameMutation.isPending}
                      data-testid="button-update-center-name"
                    >
                      {updateCenterNameMutation.isPending ? "Updating..." : "Update Name"}
                    </Button>
                  </form>
                </Form>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <Dialog open={showCreateUserDialog} onOpenChange={setShowCreateUserDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New User</DialogTitle>
            <DialogDescription>
              Add a new user to the system with login credentials
            </DialogDescription>
          </DialogHeader>
          <Form {...createUserForm}>
            <form onSubmit={createUserForm.handleSubmit((data) => createUserMutation.mutate(data))} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={createUserForm.control}
                  name="firstName"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>First Name</FormLabel>
                      <FormControl>
                        <Input {...field} data-testid="input-user-firstname" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={createUserForm.control}
                  name="lastName"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Last Name</FormLabel>
                      <FormControl>
                        <Input {...field} data-testid="input-user-lastname" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={createUserForm.control}
                name="username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Username</FormLabel>
                    <FormControl>
                      <Input {...field} data-testid="input-user-username" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createUserForm.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input type="password" {...field} data-testid="input-user-password" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createUserForm.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email (Optional)</FormLabel>
                    <FormControl>
                      <Input type="email" {...field} data-testid="input-user-email" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createUserForm.control}
                name="isCenterHead"
                render={({ field }) => (
                  <FormItem className="flex items-center space-x-2">
                    <FormControl>
                      <input 
                        type="checkbox" 
                        checked={field.value} 
                        onChange={field.onChange}
                        className="h-4 w-4"
                        data-testid="checkbox-center-head"
                      />
                    </FormControl>
                    <FormLabel className="!mt-0">Make this user a Center Head (Admin)</FormLabel>
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setShowCreateUserDialog(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createUserMutation.isPending} data-testid="button-submit-user">
                  {createUserMutation.isPending ? "Creating..." : "Create User"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Dialog open={showCreateDepartmentDialog} onOpenChange={setShowCreateDepartmentDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Department</DialogTitle>
            <DialogDescription>
              Add a new department to the medical center
            </DialogDescription>
          </DialogHeader>
          <Form {...createDepartmentForm}>
            <form onSubmit={createDepartmentForm.handleSubmit((data) => createDepartmentMutation.mutate(data))} className="space-y-4">
              <FormField
                control={createDepartmentForm.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Department Name</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Prosthodontics" {...field} data-testid="input-department-name" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createDepartmentForm.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description (Optional)</FormLabel>
                    <FormControl>
                      <Textarea 
                        placeholder="Brief description of the department" 
                        {...field} 
                        data-testid="input-department-description"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setShowCreateDepartmentDialog(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createDepartmentMutation.isPending} data-testid="button-submit-department">
                  {createDepartmentMutation.isPending ? "Creating..." : "Create Department"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Dialog open={showDoctorCredentialsDialog} onOpenChange={setShowDoctorCredentialsDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selectedDoctor?.username ? "Update" : "Create"} Doctor Portal Credentials
            </DialogTitle>
            <DialogDescription>
              {selectedDoctor?.username 
                ? `Update login credentials for ${selectedDoctor?.name}`
                : `Create login credentials for ${selectedDoctor?.name} to access the doctor portal`
              }
            </DialogDescription>
          </DialogHeader>
          <Form {...doctorCredentialsForm}>
            <form onSubmit={doctorCredentialsForm.handleSubmit((data) => createDoctorCredentialsMutation.mutate(data))} className="space-y-4">
              <FormField
                control={doctorCredentialsForm.control}
                name="username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Username</FormLabel>
                    <FormControl>
                      <Input 
                        placeholder="Enter username" 
                        {...field} 
                        data-testid="input-doctor-username"
                      />
                    </FormControl>
                    <FormDescription>
                      The doctor will use this username to log in to their portal
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={doctorCredentialsForm.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input 
                        type="password" 
                        placeholder="Enter password" 
                        {...field}
                        data-testid="input-doctor-password"
                      />
                    </FormControl>
                    <FormDescription>
                      Password must be at least 6 characters
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setShowDoctorCredentialsDialog(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createDoctorCredentialsMutation.isPending} data-testid="button-submit-credentials">
                  {createDoctorCredentialsMutation.isPending ? "Saving..." : "Save Credentials"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Dialog open={showChangePasswordDialog} onOpenChange={setShowChangePasswordDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Password</DialogTitle>
            <DialogDescription>
              Change password for {userToChangePassword?.firstName} {userToChangePassword?.lastName}
            </DialogDescription>
          </DialogHeader>
          <Form {...changePasswordForm}>
            <form onSubmit={changePasswordForm.handleSubmit((data) => {
              if (userToChangePassword) {
                changePasswordMutation.mutate({ 
                  userId: userToChangePassword.id, 
                  newPassword: data.newPassword 
                });
              }
            })} className="space-y-4">
              <FormField
                control={changePasswordForm.control}
                name="newPassword"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>New Password</FormLabel>
                    <FormControl>
                      <Input type="password" {...field} data-testid="input-new-password" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={changePasswordForm.control}
                name="confirmPassword"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Confirm Password</FormLabel>
                    <FormControl>
                      <Input type="password" {...field} data-testid="input-confirm-password" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setShowChangePasswordDialog(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={changePasswordMutation.isPending} data-testid="button-submit-password">
                  {changePasswordMutation.isPending ? "Changing..." : "Change Password"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!userToDelete} onOpenChange={() => setUserToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete User</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {userToDelete?.firstName} {userToDelete?.lastName}? 
              This action cannot be undone and will remove all their assignments and data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => userToDelete && deleteUserMutation.mutate(userToDelete.id)}
              className="bg-red-600 hover:bg-red-700"
              data-testid="button-confirm-delete-user"
            >
              Delete User
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!departmentToDelete} onOpenChange={() => setDepartmentToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Department</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{departmentToDelete?.name}"? 
              This action cannot be undone. Note: You must first remove all doctors and clinics from this department before deleting it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => departmentToDelete && deleteDepartmentMutation.mutate(departmentToDelete.id)}
              className="bg-red-600 hover:bg-red-700"
              data-testid="button-confirm-delete-department"
            >
              Delete Department
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={showAssignRoleDialog} onOpenChange={setShowAssignRoleDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign Staff Member</DialogTitle>
            <DialogDescription>
              Add a user to {departments.find(d => d.id === selectedDepartmentForRoles)?.name} with a specific role
            </DialogDescription>
          </DialogHeader>
          <Form {...assignRoleForm}>
            <form onSubmit={assignRoleForm.handleSubmit((data) => {
              data.departmentId = selectedDepartmentForRoles || 0;
              assignRoleMutation.mutate(data);
            })} className="space-y-4">
              <FormField
                control={assignRoleForm.control}
                name="userId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Select User</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger data-testid="select-assign-user">
                          <SelectValue placeholder="Choose a user to assign" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {users
                          .filter(u => !departmentMembers.some(m => m.userId === u.id))
                          .map((userItem) => (
                            <SelectItem key={userItem.id} value={userItem.id}>
                              {userItem.firstName} {userItem.lastName}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={assignRoleForm.control}
                name="role"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Role</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger data-testid="select-assign-role">
                          <SelectValue placeholder="Select a role" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="head">Department Head</SelectItem>
                        <SelectItem value="reception">Reception</SelectItem>
                        <SelectItem value="secretary">Secretary</SelectItem>
                        <SelectItem value="member">Staff Member</SelectItem>
                        <SelectItem value="viewer">View Only</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      {assignRoleForm.watch("role") === "reception" && "Reception can assign emergency patients"}
                      {assignRoleForm.watch("role") === "secretary" && "Secretary can manage leaves and permissions"}
                      {assignRoleForm.watch("role") === "head" && "Department head has full access to the department"}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setShowAssignRoleDialog(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={assignRoleMutation.isPending} data-testid="button-submit-assign">
                  {assignRoleMutation.isPending ? "Assigning..." : "Assign to Department"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Dialog open={showEditPermissionsDialog} onOpenChange={setShowEditPermissionsDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Permissions</DialogTitle>
            <DialogDescription>
              Manage permissions for {memberToEdit?.user?.firstName} {memberToEdit?.user?.lastName}
            </DialogDescription>
          </DialogHeader>
          {memberToEdit && (
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">Role</label>
                <Select
                  value={memberToEdit.role}
                  onValueChange={(value) => {
                    const permissions = getDefaultPermissionsForRole(value);
                    updateMemberPermissionsMutation.mutate({
                      userId: memberToEdit.userId,
                      departmentId: memberToEdit.departmentId,
                      updates: { role: value, ...permissions }
                    });
                  }}
                >
                  <SelectTrigger data-testid="select-edit-role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="head">Department Head</SelectItem>
                    <SelectItem value="reception">Reception</SelectItem>
                    <SelectItem value="secretary">Secretary</SelectItem>
                    <SelectItem value="member">Staff Member</SelectItem>
                    <SelectItem value="viewer">View Only</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-3 border-t pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium">Can Assign Emergencies</label>
                    <p className="text-xs text-gray-500">Allow assigning emergency walk-in patients</p>
                  </div>
                  <Switch
                    checked={memberToEdit.canAssignEmergencies}
                    onCheckedChange={(checked) => {
                      updateMemberPermissionsMutation.mutate({
                        userId: memberToEdit.userId,
                        departmentId: memberToEdit.departmentId,
                        updates: { canAssignEmergencies: checked }
                      });
                    }}
                    data-testid="switch-edit-emergencies"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium">Can Manage Leaves</label>
                    <p className="text-xs text-gray-500">Allow managing doctor leaves and permissions</p>
                  </div>
                  <Switch
                    checked={memberToEdit.canManageLeaves}
                    onCheckedChange={(checked) => {
                      updateMemberPermissionsMutation.mutate({
                        userId: memberToEdit.userId,
                        departmentId: memberToEdit.departmentId,
                        updates: { canManageLeaves: checked }
                      });
                    }}
                    data-testid="switch-edit-leaves"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium">Can View Reports</label>
                    <p className="text-xs text-gray-500">Allow viewing department reports and statistics</p>
                  </div>
                  <Switch
                    checked={memberToEdit.canViewReports}
                    onCheckedChange={(checked) => {
                      updateMemberPermissionsMutation.mutate({
                        userId: memberToEdit.userId,
                        departmentId: memberToEdit.departmentId,
                        updates: { canViewReports: checked }
                      });
                    }}
                    data-testid="switch-edit-reports"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium">Can Edit Department</label>
                    <p className="text-xs text-gray-500">Allow editing department settings and data</p>
                  </div>
                  <Switch
                    checked={memberToEdit.canEdit}
                    onCheckedChange={(checked) => {
                      updateMemberPermissionsMutation.mutate({
                        userId: memberToEdit.userId,
                        departmentId: memberToEdit.departmentId,
                        updates: { canEdit: checked }
                      });
                    }}
                    data-testid="switch-edit-department"
                  />
                </div>
              </div>

              <DialogFooter>
                <Button onClick={() => setShowEditPermissionsDialog(false)}>
                  Done
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <CreateCenterDialog
        open={showCreateCenterDialog}
        onOpenChange={setShowCreateCenterDialog}
      />

      <AlertDialog open={!!memberToRemove} onOpenChange={() => setMemberToRemove(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Staff Member</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove {memberToRemove?.user?.firstName} {memberToRemove?.user?.lastName} from this department? 
              They will lose all access to this department's data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => memberToRemove && removeMemberMutation.mutate({
                userId: memberToRemove.userId,
                departmentId: memberToRemove.departmentId
              })}
              className="bg-red-600 hover:bg-red-700"
              data-testid="button-confirm-remove-member"
            >
              Remove from Department
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
