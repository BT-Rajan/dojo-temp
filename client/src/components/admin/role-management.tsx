import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { Settings, Users, Shield, UserCheck } from "lucide-react";

interface RoleManagementProps {
  departmentId: number;
}

interface Member {
  id: number;
  userId: string;
  departmentId: number;
  role: string;
  canEdit: boolean;
  canViewOthers: boolean;
  canAssignEmergencies: boolean;
  canManageLeaves: boolean;
  canViewReports: boolean;
  user: {
    id: string;
    firstName: string;
    lastName: string;
    email: string;
  };
}

const roleLabels = {
  head: "Department Head",
  member: "Staff Member", 
  viewer: "View Only",
  reception: "Reception",
  secretary: "Secretary"
};

const roleColors = {
  head: "bg-purple-100 text-purple-800",
  member: "bg-blue-100 text-blue-800",
  viewer: "bg-gray-100 text-gray-800",
  reception: "bg-green-100 text-green-800",
  secretary: "bg-yellow-100 text-yellow-800"
};

export function RoleManagement({ departmentId }: RoleManagementProps) {
  const [editingMember, setEditingMember] = useState<Member | null>(null);
  const [showDialog, setShowDialog] = useState(false);
  const { toast } = useToast();

  const { data: members, isLoading } = useQuery({
    queryKey: ["/api/departments", departmentId, "members"],
    queryFn: async () => {
      const response = await fetch(`/api/departments/${departmentId}/members`);
      if (!response.ok) throw new Error('Failed to fetch members');
      return response.json();
    },
  });

  const updateMemberMutation = useMutation({
    mutationFn: async ({ userId, updates }: { userId: string; updates: any }) => {
      await apiRequest(`/api/departments/${departmentId}/members/${userId}`, {
        method: "PUT",
        body: JSON.stringify(updates),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/departments", departmentId, "members"] });
      setShowDialog(false);
      setEditingMember(null);
      toast({
        title: "Success",
        description: "Member permissions updated successfully",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to update member permissions",
        variant: "destructive",
      });
    },
  });

  const handleRoleChange = (member: Member, newRole: string) => {
    let updates: any = { role: newRole };
    
    // Set default permissions based on role
    if (newRole === "head") {
      updates = {
        ...updates,
        canEdit: true,
        canViewOthers: true,
        canAssignEmergencies: true,
        canManageLeaves: true,
        canViewReports: true,
      };
    } else if (newRole === "reception") {
      updates = {
        ...updates,
        canEdit: false,
        canViewOthers: false,
        canAssignEmergencies: true,
        canManageLeaves: false,
        canViewReports: true,
      };
    } else if (newRole === "secretary") {
      updates = {
        ...updates,
        canEdit: false,
        canViewOthers: false,
        canAssignEmergencies: false,
        canManageLeaves: true,
        canViewReports: true,
      };
    } else if (newRole === "viewer") {
      updates = {
        ...updates,
        canEdit: false,
        canViewOthers: true,
        canAssignEmergencies: false,
        canManageLeaves: false,
        canViewReports: false,
      };
    } else {
      // member role
      updates = {
        ...updates,
        canEdit: false,
        canViewOthers: false,
        canAssignEmergencies: false,
        canManageLeaves: false,
        canViewReports: false,
      };
    }

    updateMemberMutation.mutate({ userId: member.userId, updates });
  };

  const handlePermissionChange = (member: Member, permission: string, value: boolean) => {
    updateMemberMutation.mutate({ 
      userId: member.userId, 
      updates: { [permission]: value } 
    });
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Role Management
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div>Loading members...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-5 w-5" />
          Role Management
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {members?.map((member: Member) => (
          <div key={member.id} className="border rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">
                  {member.user.firstName} {member.user.lastName}
                </div>
                <div className="text-sm text-gray-500">{member.user.email}</div>
              </div>
              <div className="flex items-center gap-3">
                <Badge className={roleColors[member.role as keyof typeof roleColors] || "bg-gray-100 text-gray-800"}>
                  {roleLabels[member.role as keyof typeof roleLabels] || member.role}
                </Badge>
                <Dialog open={showDialog && editingMember?.id === member.id} onOpenChange={(open) => {
                  setShowDialog(open);
                  if (!open) setEditingMember(null);
                }}>
                  <DialogTrigger asChild>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => setEditingMember(member)}
                      data-testid={`button-edit-member-${member.id}`}
                    >
                      <Settings className="h-4 w-4" />
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-md">
                    <DialogHeader>
                      <DialogTitle>
                        Edit Permissions - {member.user.firstName} {member.user.lastName}
                      </DialogTitle>
                    </DialogHeader>
                    
                    <div className="space-y-4">
                      <div>
                        <label className="text-sm font-medium">Role</label>
                        <Select
                          value={member.role}
                          onValueChange={(value) => handleRoleChange(member, value)}
                        >
                          <SelectTrigger data-testid={`select-role-${member.id}`}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="head">Department Head</SelectItem>
                            <SelectItem value="member">Staff Member</SelectItem>
                            <SelectItem value="reception">Reception</SelectItem>
                            <SelectItem value="secretary">Secretary</SelectItem>
                            <SelectItem value="viewer">View Only</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <label className="text-sm">Can Edit Department Data</label>
                          <Switch
                            checked={member.canEdit}
                            onCheckedChange={(checked) => handlePermissionChange(member, "canEdit", checked)}
                            data-testid={`switch-can-edit-${member.id}`}
                          />
                        </div>

                        <div className="flex items-center justify-between">
                          <label className="text-sm">Can Assign Emergencies</label>
                          <Switch
                            checked={member.canAssignEmergencies}
                            onCheckedChange={(checked) => handlePermissionChange(member, "canAssignEmergencies", checked)}
                            data-testid={`switch-can-assign-emergencies-${member.id}`}
                          />
                        </div>

                        <div className="flex items-center justify-between">
                          <label className="text-sm">Can Manage Leaves</label>
                          <Switch
                            checked={member.canManageLeaves}
                            onCheckedChange={(checked) => handlePermissionChange(member, "canManageLeaves", checked)}
                            data-testid={`switch-can-manage-leaves-${member.id}`}
                          />
                        </div>

                        <div className="flex items-center justify-between">
                          <label className="text-sm">Can View Reports</label>
                          <Switch
                            checked={member.canViewReports}
                            onCheckedChange={(checked) => handlePermissionChange(member, "canViewReports", checked)}
                            data-testid={`switch-can-view-reports-${member.id}`}
                          />
                        </div>

                        <div className="flex items-center justify-between">
                          <label className="text-sm">Can View Other Departments</label>
                          <Switch
                            checked={member.canViewOthers}
                            onCheckedChange={(checked) => handlePermissionChange(member, "canViewOthers", checked)}
                            data-testid={`switch-can-view-others-${member.id}`}
                          />
                        </div>
                      </div>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex items-center gap-1">
                <UserCheck className="h-3 w-3" />
                <span className={member.canAssignEmergencies ? "text-green-600" : "text-gray-400"}>
                  Emergency Assignment
                </span>
              </div>
              <div className="flex items-center gap-1">
                <Users className="h-3 w-3" />
                <span className={member.canManageLeaves ? "text-green-600" : "text-gray-400"}>
                  Leave Management
                </span>
              </div>
            </div>
          </div>
        ))}

        {(!members || members.length === 0) && (
          <div className="text-center py-8">
            <Users className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-sm text-gray-500">No members found</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}