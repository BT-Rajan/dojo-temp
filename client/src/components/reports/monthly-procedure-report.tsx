import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { CalendarDays, Download, FileText, Users, Activity } from 'lucide-react';
import { format } from 'date-fns';
import type { Doctor, Department } from '@shared/schema';

interface MonthlyReportProps {
  departmentId?: number;
  doctorId?: number;
}

interface MonthlyReport {
  reportType: 'doctor' | 'department';
  period: { year: number; month: number };
  doctor?: Doctor;
  department?: Department;
  summary: {
    totalPatientsTreated: number;
    totalProceduresCompleted: number;
    appointmentsCompleted: number;
    procedures: Record<string, number>;
  };
  procedures: Record<string, number>;
  doctorReports?: Array<{
    doctor: Doctor;
    summary: {
      totalPatientsTreated: number;
      totalProceduresCompleted: number;
      appointmentsCompleted: number;
    };
    procedures: Record<string, number>;
  }>;
  generatedAt: string;
}

const procedureLabels: Record<string, string> = {
  treatedPatients: "Treated Patients",
  alginatePreparation: "Alginate Preparation",
  crownPreparation: "Crown Preparation",
  bridgePreparation: "Bridge Preparation",
  finalImpression: "Final Impression",
  tempCementation: "Temp Cementation",
  cementAccBb: "Cement ACC BB",
  cementPorcelainCb: "Cement Porcelain CB",
  metalCrownCb: "Metal Crown CB",
  porcelainCb: "Porcelain CB",
  postPreparation: "Post Preparation",
  postCanal: "Post Canal",
  compositeFilling: "Composite Filling",
  amalgamFilling: "Amalgam Filling",
  removableProstho: "Removable Prostho",
  removableProsthoRepair: "Removable Prostho Repair",
  cbRemovalPostCore: "CB Removal Post Core",
  orthoAppliances: "Ortho Appliances",
  buckleAppointment: "Buckle Appointment",
  implantUnits: "Implant Units",
};

export function MonthlyProcedureReport({ departmentId, doctorId }: MonthlyReportProps) {
  const currentDate = new Date();
  const [selectedYear, setSelectedYear] = useState(currentDate.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(currentDate.getMonth() + 1);

  const { data: report, isLoading, error } = useQuery({
    queryKey: ['/api/monthly-procedure-report', { departmentId, doctorId, year: selectedYear, month: selectedMonth }],
    queryFn: async () => {
      const params = new URLSearchParams({
        year: selectedYear.toString(),
        month: selectedMonth.toString(),
      });
      
      if (departmentId) {
        params.append('departmentId', departmentId.toString());
      }
      if (doctorId) {
        params.append('doctorId', doctorId.toString());
      }
      
      const response = await fetch(`/api/monthly-procedure-report?${params}`);
      if (!response.ok) {
        throw new Error('Failed to fetch monthly report');
      }
      return response.json() as Promise<MonthlyReport>;
    },
    enabled: !!(departmentId || doctorId),
  });

  const handleExport = () => {
    if (!report) return;
    
    // Create CSV content
    const csvContent = generateCSV(report);
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `monthly-report-${selectedYear}-${selectedMonth.toString().padStart(2, '0')}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const generateCSV = (report: MonthlyReport): string => {
    const monthName = format(new Date(selectedYear, selectedMonth - 1), 'MMMM yyyy');
    
    let csv = `Monthly Procedure Report - ${monthName}\n`;
    csv += `Generated: ${format(new Date(report.generatedAt), 'PPP')}\n\n`;
    
    if (report.reportType === 'doctor' && report.doctor) {
      csv += `Doctor: ${report.doctor.title} ${report.doctor.name}\n`;
      csv += `Department: ${report.department?.name || 'N/A'}\n\n`;
      csv += `Summary:\n`;
      csv += `Patients Treated,${report.summary.totalPatientsTreated}\n`;
      csv += `Appointments Completed,${report.summary.appointmentsCompleted}\n`;
      csv += `Total Procedures,${report.summary.totalProceduresCompleted}\n\n`;
      csv += `Procedures:\n`;
      csv += `Procedure,Count\n`;
      Object.entries(report.procedures).forEach(([key, value]) => {
        if (value > 0) {
          csv += `${procedureLabels[key] || key},${value}\n`;
        }
      });
    } else if (report.reportType === 'department' && report.department) {
      csv += `Department: ${report.department.name}\n\n`;
      csv += `Department Summary:\n`;
      csv += `Total Patients Treated,${report.summary.totalPatientsTreated}\n`;
      csv += `Total Appointments Completed,${report.summary.appointmentsCompleted}\n`;
      csv += `Total Procedures,${report.summary.totalProceduresCompleted}\n\n`;
      
      csv += `Department Procedures:\n`;
      csv += `Procedure,Count\n`;
      Object.entries(report.summary.procedures || {}).forEach(([key, value]) => {
        if ((value as number) > 0) {
          csv += `${procedureLabels[key] || key},${value}\n`;
        }
      });
      
      csv += `\n\nDoctor Details:\n`;
      report.doctorReports?.forEach(doctorReport => {
        csv += `\n${doctorReport.doctor.title} ${doctorReport.doctor.name}:\n`;
        csv += `Patients Treated,${doctorReport.summary.totalPatientsTreated}\n`;
        csv += `Appointments Completed,${doctorReport.summary.appointmentsCompleted}\n`;
        csv += `Procedures,${doctorReport.summary.totalProceduresCompleted}\n`;
        Object.entries(doctorReport.procedures).forEach(([key, value]) => {
          if (value > 0) {
            csv += `${procedureLabels[key] || key},${value}\n`;
          }
        });
      });
    }
    
    return csv;
  };

  const renderProcedureGrid = (procedures: Record<string, number>) => {
    const activeProcedures = Object.entries(procedures).filter(([_, count]) => count > 0);
    
    if (activeProcedures.length === 0) {
      return (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          No procedures recorded for this period
        </div>
      );
    }
    
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {activeProcedures.map(([procedure, count]) => (
          <div key={procedure} className="flex justify-between items-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {procedureLabels[procedure] || procedure}
            </span>
            <Badge variant="secondary" className="ml-2">
              {count}
            </Badge>
          </div>
        ))}
      </div>
    );
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600 dark:text-gray-400">Generating report...</span>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <div className="text-center">
            <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600 dark:text-gray-400">Failed to load report</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const monthName = format(new Date(selectedYear, selectedMonth - 1), 'MMMM yyyy');

  return (
    <div className="space-y-6">
      {/* Header with Controls */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center space-x-2">
                <FileText className="h-5 w-5" />
                <span>Monthly Procedure Report</span>
              </CardTitle>
              <CardDescription>
                Detailed statistics for {monthName}
              </CardDescription>
            </div>
            <div className="flex items-center space-x-4">
              {/* Year Selector */}
              <div className="flex items-center space-x-2">
                <label className="text-sm font-medium">Year:</label>
                <Select 
                  value={selectedYear.toString()} 
                  onValueChange={(value) => setSelectedYear(parseInt(value))}
                >
                  <SelectTrigger className="w-24">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 5 }, (_, i) => currentDate.getFullYear() - 2 + i).map(year => (
                      <SelectItem key={year} value={year.toString()}>
                        {year}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              {/* Month Selector */}
              <div className="flex items-center space-x-2">
                <label className="text-sm font-medium">Month:</label>
                <Select 
                  value={selectedMonth.toString()} 
                  onValueChange={(value) => setSelectedMonth(parseInt(value))}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map(month => (
                      <SelectItem key={month} value={month.toString()}>
                        {format(new Date(2025, month - 1), 'MMMM')}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              {/* Export Button */}
              <Button onClick={handleExport} variant="outline" className="flex items-center space-x-2">
                <Download className="h-4 w-4" />
                <span>Export CSV</span>
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Report Content */}
      {report && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Patients Treated</p>
                    <p className="text-3xl font-bold text-blue-600">{report.summary.totalPatientsTreated}</p>
                  </div>
                  <Users className="h-8 w-8 text-blue-600" />
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Appointments Completed</p>
                    <p className="text-3xl font-bold text-green-600">{report.summary.appointmentsCompleted}</p>
                  </div>
                  <CalendarDays className="h-8 w-8 text-green-600" />
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Total Procedures</p>
                    <p className="text-3xl font-bold text-purple-600">{report.summary.totalProceduresCompleted}</p>
                  </div>
                  <Activity className="h-8 w-8 text-purple-600" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Report Type Specific Content */}
          {report.reportType === 'doctor' && report.doctor && (
            <Card>
              <CardHeader>
                <CardTitle>Doctor Report: {report.doctor.title} {report.doctor.name}</CardTitle>
                <CardDescription>
                  Department: {report.department?.name || 'N/A'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <h4 className="text-lg font-semibold mb-4">Procedures Performed</h4>
                {renderProcedureGrid(report.procedures)}
              </CardContent>
            </Card>
          )}

          {report.reportType === 'department' && report.department && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Department Report: {report.department.name}</CardTitle>
                  <CardDescription>
                    Aggregated statistics for all doctors in the department
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <h4 className="text-lg font-semibold mb-4">Department Procedure Totals</h4>
                  {renderProcedureGrid(report.summary.procedures || {})}
                </CardContent>
              </Card>

              {/* Individual Doctor Reports */}
              {report.doctorReports && report.doctorReports.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Individual Doctor Reports</CardTitle>
                    <CardDescription>
                      Detailed breakdown by doctor
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-6">
                      {report.doctorReports.map((doctorReport) => (
                        <div key={doctorReport.doctor.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-6">
                          <div className="flex items-center justify-between mb-4">
                            <h5 className="text-lg font-semibold">
                              {doctorReport.doctor.title} {doctorReport.doctor.name}
                            </h5>
                            <div className="flex space-x-4 text-sm">
                              <span className="bg-blue-100 dark:bg-blue-900 px-2 py-1 rounded">
                                {doctorReport.summary.totalPatientsTreated} patients
                              </span>
                              <span className="bg-green-100 dark:bg-green-900 px-2 py-1 rounded">
                                {doctorReport.summary.appointmentsCompleted} appointments
                              </span>
                              <span className="bg-purple-100 dark:bg-purple-900 px-2 py-1 rounded">
                                {doctorReport.summary.totalProceduresCompleted} procedures
                              </span>
                            </div>
                          </div>
                          {renderProcedureGrid(doctorReport.procedures)}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}

          {/* Report Footer */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between text-sm text-gray-600 dark:text-gray-400">
                <span>Report generated on {format(new Date(report.generatedAt), 'PPP p')}</span>
                <span>Al-Adan Dental Specialist Center</span>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}