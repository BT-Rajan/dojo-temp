import { cn } from "@/lib/utils";
import { 
  ChartLine, 
  UserCheck, 
  Calendar, 
  Ambulance, 
  CalendarX, 
  Microscope,
  FileText,
  CalendarCheck
} from "lucide-react";

type Tab = "dashboard" | "doctors" | "clinics" | "appointments" | "emergency" | "leave" | "examination" | "reports";

interface NavigationProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export function Navigation({ activeTab, onTabChange }: NavigationProps) {
  const tabs = [
    { id: "dashboard", label: "Daily Dashboard", icon: ChartLine },
    { id: "doctors", label: "Doctor Management", icon: UserCheck },
    { id: "clinics", label: "Clinic Assignment", icon: Calendar },
    { id: "appointments", label: "Appointments", icon: CalendarCheck },
    { id: "emergency", label: "Emergency Walk-ins", icon: Ambulance },
    { id: "leave", label: "Leave & Permissions", icon: CalendarX },
    { id: "examination", label: "Examination Clinics", icon: Microscope },
    { id: "reports", label: "Print Reports", icon: FileText },
  ];

  return (
    <nav className="flex space-x-8 border-b border-gray-200">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id as Tab)}
            className={cn(
              "py-2 px-1 border-b-2 font-medium text-sm transition-colors",
              activeTab === tab.id
                ? "border-medical-blue text-medical-blue"
                : "border-transparent text-gray-500 hover:text-gray-700"
            )}
          >
            <Icon className="mr-2 h-4 w-4 inline" />
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}
