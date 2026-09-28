import { Users, Home, Settings, Shield, LogOut } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useCenterName } from "@/hooks/useCenterName";
import { Button } from "@/components/ui/button";
import { useLocation } from "wouter";

export function Header() {
  const { user } = useAuth();
  const { centerName } = useCenterName();
  const [location, setLocation] = useLocation();

  const navigateToHome = () => setLocation("/");
  const navigateToControlCenter = () => setLocation("/control-center");
  const navigateToAdmin = () => setLocation("/admin");
  const handleLogout = () => window.location.href = "/api/logout";

  const isActive = (path: string) => location === path;

  return (
    <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <Users className="text-2xl text-medical-blue mr-3" />
            <h1 className="text-xl font-semibold text-gray-900">{centerName || "Department Manager"}</h1>
          </div>
          
          {/* Navigation Buttons */}
          <div className="flex items-center space-x-2">
            <Button
              variant={isActive("/") ? "default" : "ghost"}
              size="sm"
              onClick={navigateToHome}
              className={isActive("/") ? "bg-medical-blue hover:bg-blue-700" : ""}
            >
              <Home className="h-4 w-4 mr-1" />
              Dashboard
            </Button>
            
            {user?.isCenterHead && (
              <Button
                variant={isActive("/control-center") ? "default" : "ghost"}
                size="sm"
                onClick={navigateToControlCenter}
                className={isActive("/control-center") ? "bg-medical-blue hover:bg-blue-700" : ""}
              >
                <Settings className="h-4 w-4 mr-1" />
                Control Center
              </Button>
            )}
            
            {user?.isCenterHead && (
              <Button
                variant={isActive("/admin") ? "default" : "ghost"}
                size="sm"
                onClick={navigateToAdmin}
                className={isActive("/admin") ? "bg-medical-blue hover:bg-blue-700" : ""}
              >
                <Shield className="h-4 w-4 mr-1" />
                Admin
              </Button>
            )}
          </div>

          <div className="flex items-center space-x-4">
            {user && (
              <div className="text-sm text-gray-600">
                <span>{user.firstName ? `${user.firstName} ${user.lastName}` : user.email}</span>
                <span className="text-gray-400 ml-2">{user.isCenterHead ? "Center Head" : "Department Head"}</span>
              </div>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="text-red-600 hover:text-red-700 hover:bg-red-50"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}
