import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { 
  Printer, 
  Users, 
  Calendar, 
  ClipboardList, 
  Stethoscope,
  FileText,
  Download
} from "lucide-react";
import { format } from "date-fns";
import { formatDate } from "@/lib/date-utils";

const weekdayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"];

export function PrintReports() {
  const [selectedReport, setSelectedReport] = useState<string | null>(null);

  const { data: doctors, isLoading: doctorsLoading } = useQuery({
    queryKey: ["/api/doctors"],
  });

  const { data: leaves, isLoading: leavesLoading } = useQuery({
    queryKey: ["/api/leaves"],
  });

  const { data: clinicAssignments, isLoading: clinicAssignmentsLoading } = useQuery({
    queryKey: ["/api/clinic-assignments"],
  });

  const { data: examinationSlots, isLoading: examinationSlotsLoading } = useQuery({
    queryKey: ["/api/examination-slots"],
  });

  const printReport = (reportType: string) => {
    setSelectedReport(reportType);
    setTimeout(() => {
      window.print();
      setSelectedReport(null);
    }, 100);
  };

  const exportToCSV = (data: any[], filename: string, headers: string[]) => {
    const csvContent = [
      headers.join(","),
      ...data.map(row => headers.map(header => `"${row[header] || ''}"`).join(","))
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const DoctorsList = () => (
    <div className="print-content">
      <div className="print-header">
        <h1>Prosthodontics Department - Doctors List</h1>
        <p>Generated on: {format(new Date(), "PPP")}</p>
      </div>
      
      <table className="print-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Title</th>
            <th>Civil ID</th>
            <th>File Number</th>
            <th>Phone</th>
            <th>Email</th>
          </tr>
        </thead>
        <tbody>
          {doctors?.map((doctor: any) => (
            <tr key={doctor.id}>
              <td>{doctor.name}</td>
              <td>{doctor.title}</td>
              <td>{doctor.civilId}</td>
              <td>{doctor.fileNumber}</td>
              <td>{doctor.phone}</td>
              <td>{doctor.email}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const LeavesSummary = () => {
    const activeLeaves = leaves?.filter((leave: any) => leave.isActive) || [];
    const upcomingLeaves = leaves?.filter((leave: any) => 
      new Date(leave.startDate) > new Date() && leave.isActive
    ) || [];

    return (
      <div className="print-content">
        <div className="print-header">
          <h1>Prosthodontics Department - Leaves Summary</h1>
          <p>Generated on: {format(new Date(), "PPP")}</p>
        </div>
        
        <div className="print-section">
          <h2>Active Leaves</h2>
          <table className="print-table">
            <thead>
              <tr>
                <th>Doctor</th>
                <th>Type</th>
                <th>Start Date</th>
                <th>End Date</th>
                <th>Duration (Days)</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {activeLeaves.map((leave: any) => {
                const startDate = new Date(leave.startDate);
                const endDate = new Date(leave.endDate);
                const duration = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)) + 1;
                
                return (
                  <tr key={leave.id}>
                    <td>{leave.doctor.name}</td>
                    <td>{leave.type}</td>
                    <td>{format(startDate, "PP")}</td>
                    <td>{format(endDate, "PP")}</td>
                    <td>{duration}</td>
                    <td>{leave.reason || '-'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="print-section">
          <h2>Upcoming Leaves</h2>
          <table className="print-table">
            <thead>
              <tr>
                <th>Doctor</th>
                <th>Type</th>
                <th>Start Date</th>
                <th>End Date</th>
                <th>Duration (Days)</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {upcomingLeaves.map((leave: any) => {
                const startDate = new Date(leave.startDate);
                const endDate = new Date(leave.endDate);
                const duration = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)) + 1;
                
                return (
                  <tr key={leave.id}>
                    <td>{leave.doctor.name}</td>
                    <td>{leave.type}</td>
                    <td>{format(startDate, "PP")}</td>
                    <td>{format(endDate, "PP")}</td>
                    <td>{duration}</td>
                    <td>{leave.reason || '-'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const ClinicWeeklySchedule = () => {
    const scheduleByWeekday = weekdayNames.map((day, weekdayIndex) => {
      const dayAssignments = clinicAssignments?.filter((assignment: any) => 
        assignment.weekday === weekdayIndex
      ) || [];
      
      return {
        day,
        assignments: dayAssignments
      };
    });

    return (
      <div className="print-content">
        <div className="print-header">
          <h1>Prosthodontics Department - Clinic Weekly Schedule</h1>
          <p>Generated on: {format(new Date(), "PPP")}</p>
        </div>
        
        {scheduleByWeekday.map(({ day, assignments }) => (
          <div key={day} className="print-section">
            <h2>{day}</h2>
            <table className="print-table">
              <thead>
                <tr>
                  <th>Clinic</th>
                  <th>Time</th>
                  <th>Doctor</th>
                  <th>Doctor Title</th>
                </tr>
              </thead>
              <tbody>
                {assignments.length > 0 ? assignments.map((assignment: any) => (
                  <tr key={assignment.id}>
                    <td>{assignment.clinic.name}</td>
                    <td>{assignment.clinic.startTime} - {assignment.clinic.endTime}</td>
                    <td>{assignment.doctor.name}</td>
                    <td>{assignment.doctor.title}</td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={4} className="text-center text-gray-500">No clinic assignments</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    );
  };

  const ExaminationWeeklySchedule = () => {
    const scheduleByWeekday = weekdayNames.map((day, weekdayIndex) => {
      const daySlots = examinationSlots?.filter((slot: any) => 
        slot.weekday === weekdayIndex
      ) || [];
      
      return {
        day,
        slots: daySlots
      };
    });

    return (
      <div className="print-content">
        <div className="print-header">
          <h1>Prosthodontics Department - Examination Weekly Schedule</h1>
          <p>Generated on: {format(new Date(), "PPP")}</p>
        </div>
        
        {scheduleByWeekday.map(({ day, slots }) => (
          <div key={day} className="print-section">
            <h2>{day}</h2>
            <table className="print-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Capacity</th>
                  <th>Assigned Doctors</th>
                  <th>Available Spots</th>
                </tr>
              </thead>
              <tbody>
                {slots.length > 0 ? slots.map((slot: any) => (
                  <tr key={slot.id}>
                    <td>{slot.startTime} - {slot.endTime}</td>
                    <td>{slot.capacity}</td>
                    <td>
                      {slot.assignments?.map((assignment: any) => assignment.doctor.name).join(", ") || "None"}
                    </td>
                    <td>{slot.capacity - (slot.assignments?.length || 0)}</td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={4} className="text-center text-gray-500">No examination slots</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    );
  };

  if (doctorsLoading || leavesLoading || clinicAssignmentsLoading || examinationSlotsLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="no-print">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Print Reports</h2>
        <p className="text-gray-600">Generate and print various department reports</p>
      </div>

      {/* Report Selection */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 no-print">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center mb-4">
              <Users className="text-medical-blue mr-3" size={24} />
              <h3 className="text-lg font-semibold">Doctors List</h3>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Complete list of all doctors with their contact information and details
            </p>
            <div className="space-y-2">
              <Button 
                onClick={() => printReport("doctors")} 
                className="w-full bg-medical-blue hover:bg-blue-700"
              >
                <Printer className="mr-2 h-4 w-4" />
                Print Doctors List
              </Button>
              <Button 
                variant="outline" 
                onClick={() => exportToCSV(
                  doctors || [], 
                  "doctors-list", 
                  ["name", "title", "civilId", "fileNumber", "phone", "email"]
                )}
                className="w-full"
              >
                <Download className="mr-2 h-4 w-4" />
                Export to CSV
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center mb-4">
              <Calendar className="text-green-600 mr-3" size={24} />
              <h3 className="text-lg font-semibold">Leaves Summary</h3>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Summary of active and upcoming leaves with duration and reasons
            </p>
            <div className="space-y-2">
              <Button 
                onClick={() => printReport("leaves")} 
                className="w-full bg-green-600 hover:bg-green-700"
              >
                <Printer className="mr-2 h-4 w-4" />
                Print Leaves Summary
              </Button>
              <Button 
                variant="outline" 
                onClick={() => exportToCSV(
                  leaves?.filter((l: any) => l.isActive) || [], 
                  "leaves-summary", 
                  ["doctor.name", "type", "startDate", "endDate", "reason"]
                )}
                className="w-full"
              >
                <Download className="mr-2 h-4 w-4" />
                Export to CSV
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center mb-4">
              <ClipboardList className="text-purple-600 mr-3" size={24} />
              <h3 className="text-lg font-semibold">Clinic Weekly Schedule</h3>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Weekly clinic assignments showing doctor schedules for each day
            </p>
            <div className="space-y-2">
              <Button 
                onClick={() => printReport("clinic-schedule")} 
                className="w-full bg-purple-600 hover:bg-purple-700"
              >
                <Printer className="mr-2 h-4 w-4" />
                Print Clinic Schedule
              </Button>
              <Button 
                variant="outline" 
                onClick={() => exportToCSV(
                  clinicAssignments || [], 
                  "clinic-schedule", 
                  ["clinic.name", "doctor.name", "clinic.startTime", "clinic.endTime"]
                )}
                className="w-full"
              >
                <Download className="mr-2 h-4 w-4" />
                Export to CSV
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center mb-4">
              <Stethoscope className="text-orange-600 mr-3" size={24} />
              <h3 className="text-lg font-semibold">Examination Schedule</h3>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Weekly examination slots with assigned doctors and capacity information
            </p>
            <div className="space-y-2">
              <Button 
                onClick={() => printReport("examination-schedule")} 
                className="w-full bg-orange-600 hover:bg-orange-700"
              >
                <Printer className="mr-2 h-4 w-4" />
                Print Examination Schedule
              </Button>
              <Button 
                variant="outline" 
                onClick={() => exportToCSV(
                  examinationSlots || [], 
                  "examination-schedule", 
                  ["weekday", "startTime", "endTime", "capacity"]
                )}
                className="w-full"
              >
                <Download className="mr-2 h-4 w-4" />
                Export to CSV
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Print Preview */}
      <div className={`print-only ${selectedReport ? 'block' : 'hidden'}`}>
        {selectedReport === "doctors" && <DoctorsList />}
        {selectedReport === "leaves" && <LeavesSummary />}
        {selectedReport === "clinic-schedule" && <ClinicWeeklySchedule />}
        {selectedReport === "examination-schedule" && <ExaminationWeeklySchedule />}
      </div>

      <style>{`
        @media print {
          /* Hide everything by default */
          body * {
            visibility: hidden;
          }
          
          /* Show only print content */
          .print-only, .print-only * {
            visibility: visible !important;
          }
          
          .print-only {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            display: block !important;
          }
          
          /* Hide specific elements */
          .no-print, nav, .tabs, .sidebar, header, .navigation, button {
            display: none !important;
          }
          
          .print-content {
            max-width: 100%;
            margin: 0;
            padding: 20px;
          }
          
          .print-header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #333;
            padding-bottom: 20px;
          }
          
          .print-header h1 {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
          }
          
          .print-section {
            margin: 30px 0;
            page-break-inside: avoid;
          }
          
          .print-section h2 {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            color: #333;
            border-bottom: 1px solid #ccc;
            padding-bottom: 5px;
          }
          
          .print-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
          }
          
          .print-table th,
          .print-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            font-size: 12px;
          }
          
          .print-table th {
            background-color: #f5f5f5 !important;
            font-weight: bold;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          
          .print-table tr:nth-child(even) {
            background-color: #f9f9f9 !important;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
        }
        
        .print-only {
          display: none;
        }
      `}</style>
    </div>
  );
}