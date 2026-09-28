import { useQuery } from "@tanstack/react-query";
import { Link, useSearch } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Clock, Users, Building2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const WEEKDAY_COLORS = [
  "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
  "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
];

interface Doctor {
  id: number;
  name: string;
  title: string;
  departmentId: number;
}

interface Clinic {
  id: number;
  name: string;
  description: string | null;
  startTime: string;
  endTime: string;
  departmentId: number;
}

interface ClinicAssignment {
  id: number;
  doctorId: number;
  clinicId: number;
  weekday: number;
  isActive: boolean;
}

interface Department {
  id: number;
  name: string;
}

interface ClinicWithDoctors {
  clinic: Clinic;
  doctors: {
    doctor: Doctor;
    days: number[];
  }[];
}

export default function ClinicOverview() {
  const searchString = useSearch();
  const params = new URLSearchParams(searchString);
  const departmentId = parseInt(params.get("dept") || "0");

  const { data: department } = useQuery<Department>({
    queryKey: ["/api/departments", departmentId],
    queryFn: async () => {
      const res = await fetch(`/api/departments/${departmentId}`, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch department");
      return res.json();
    },
    enabled: departmentId > 0,
  });

  const { data: clinics = [], isLoading: clinicsLoading } = useQuery<Clinic[]>({
    queryKey: ["/api/clinics", departmentId],
    queryFn: async () => {
      const res = await fetch(`/api/clinics?departmentId=${departmentId}`, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch clinics");
      return res.json();
    },
    enabled: departmentId > 0,
  });

  const { data: doctors = [], isLoading: doctorsLoading } = useQuery<Doctor[]>({
    queryKey: ["/api/doctors", departmentId],
    queryFn: async () => {
      const res = await fetch(`/api/doctors?departmentId=${departmentId}`, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch doctors");
      return res.json();
    },
    enabled: departmentId > 0,
  });

  const { data: assignments = [], isLoading: assignmentsLoading } = useQuery<ClinicAssignment[]>({
    queryKey: ["/api/clinic-assignments", departmentId],
    queryFn: async () => {
      const res = await fetch(`/api/clinic-assignments?departmentId=${departmentId}`, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch assignments");
      return res.json();
    },
    enabled: departmentId > 0,
  });

  const isLoading = clinicsLoading || doctorsLoading || assignmentsLoading;

  const clinicsWithDoctors: ClinicWithDoctors[] = clinics.map((clinic) => {
    const clinicAssignments = assignments.filter(
      (a) => a.clinicId === clinic.id && a.isActive
    );
    
    const doctorMap = new Map<number, number[]>();
    
    clinicAssignments.forEach((assignment) => {
      const existing = doctorMap.get(assignment.doctorId) || [];
      existing.push(assignment.weekday);
      doctorMap.set(assignment.doctorId, existing);
    });

    const doctorsInClinic = Array.from(doctorMap.entries()).map(([doctorId, days]) => {
      const doctor = doctors.find((d) => d.id === doctorId);
      return {
        doctor: doctor!,
        days: days.sort(),
      };
    }).filter((d) => d.doctor);

    return {
      clinic,
      doctors: doctorsInClinic,
    };
  });

  const formatTime = (time: string) => {
    const [hours, minutes] = time.split(":");
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? "PM" : "AM";
    const displayHour = hour % 12 || 12;
    return `${displayHour}:${minutes} ${ampm}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="outline" size="sm">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Home
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                {department?.name || "Department"} - Clinic Overview
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                Visual representation of clinics and doctor assignments
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2 bg-blue-50 dark:bg-blue-900/30 px-4 py-2 rounded-lg">
            <Building2 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            <span className="text-blue-700 dark:text-blue-300 font-medium">
              {department?.name || "Loading..."}
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Card key={i} className="bg-white dark:bg-gray-800 shadow-lg border-t-4 border-t-gray-300">
                <CardHeader className="pb-3">
                  <Skeleton className="h-6 w-3/4 mb-2" />
                  <Skeleton className="h-4 w-1/2" />
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <Skeleton className="h-20 w-full" />
                    <Skeleton className="h-20 w-full" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {clinicsWithDoctors.map(({ clinic, doctors: clinicDoctors }) => (
            <Card 
              key={clinic.id} 
              className="bg-white dark:bg-gray-800 shadow-lg hover:shadow-xl transition-shadow duration-300 border-t-4 border-t-blue-500"
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-xl font-bold text-gray-900 dark:text-white">
                    {clinic.name}
                  </CardTitle>
                  <Badge variant="secondary" className="flex items-center gap-1">
                    <Users className="h-3 w-3" />
                    {clinicDoctors.length}
                  </Badge>
                </div>
                {clinic.description && (
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    {clinic.description}
                  </p>
                )}
                <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300 mt-2">
                  <Clock className="h-4 w-4" />
                  <span>{formatTime(clinic.startTime)} - {formatTime(clinic.endTime)}</span>
                </div>
              </CardHeader>
              
              <CardContent className="pt-0">
                {clinicDoctors.length === 0 ? (
                  <div className="text-center py-6 text-gray-400">
                    <Users className="h-10 w-10 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">No doctors assigned</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {clinicDoctors.map(({ doctor, days }) => (
                      <div 
                        key={doctor.id} 
                        className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-100 dark:border-gray-600"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div>
                            <h4 className="font-semibold text-gray-900 dark:text-white">
                              {doctor.name}
                            </h4>
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                              {doctor.title}
                            </p>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {days.map((day) => (
                            <Badge 
                              key={day} 
                              className={`text-xs font-medium ${WEEKDAY_COLORS[day]}`}
                            >
                              {WEEKDAYS[day].substring(0, 3)}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
        )}

        {!isLoading && clinicsWithDoctors.length === 0 && (
          <div className="text-center py-16">
            <Building2 className="h-16 w-16 mx-auto text-gray-300 mb-4" />
            <h3 className="text-xl font-semibold text-gray-600 dark:text-gray-400 mb-2">
              No Clinics Found
            </h3>
            <p className="text-gray-500 dark:text-gray-500">
              No clinics have been created for this department yet.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
