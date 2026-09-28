import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { User, Shield, Building2 } from "lucide-react";

export function AuthStatus() {
  const { data: user, isLoading, error } = useQuery<any>({
    queryKey: ["/api/auth/user"],
    retry: false,
  });

  if (isLoading) {
    return (
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center">
            <User className="mr-2 h-5 w-5" />
            Authentication Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600">Loading...</p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="w-full max-w-md border-red-200">
        <CardHeader>
          <CardTitle className="flex items-center text-red-700">
            <User className="mr-2 h-5 w-5" />
            Authentication Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Badge variant="destructive" className="mb-2">Not Authenticated</Badge>
          <p className="text-sm text-gray-600">
            You need to log in to access the Control Center.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-md border-green-200">
      <CardHeader>
        <CardTitle className="flex items-center text-green-700">
          <User className="mr-2 h-5 w-5" />
          Authentication Status
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">User:</span>
          <span className="text-sm">{user?.firstName} {user?.lastName}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Email:</span>
          <span className="text-sm">{user?.email}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Center Head:</span>
          {user?.isCenterHead ? (
            <Badge variant="default" className="bg-green-100 text-green-800">
              <Shield className="mr-1 h-3 w-3" />
              Yes
            </Badge>
          ) : (
            <Badge variant="secondary">
              No
            </Badge>
          )}
        </div>
        {!user?.isCenterHead && (
          <div className="mt-3 p-3 bg-orange-50 rounded-lg">
            <p className="text-sm text-orange-700">
              <strong>Control Center Access:</strong> You need Center Head privileges to access the Control Center.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}