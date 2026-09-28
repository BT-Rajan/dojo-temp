import { useState, useEffect } from "react";
import { useLocation } from "wouter";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PhoneCall, Lock, Building2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface Department { id: number; name: string }

export default function CallCenterLogin() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentId, setDepartmentId] = useState("");
  const [code, setCode] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [, setLocation] = useLocation();
  const { toast } = useToast();

  useEffect(() => {
    fetch("/api/departments/public-list")
      .then(r => r.json())
      .then(setDepartments)
      .catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!departmentId || !code.trim()) {
      setError("Please select a department and enter the access code");
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      const res = await fetch("/api/callcenter/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ departmentId: parseInt(departmentId), code: code.trim() }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        localStorage.setItem("callCenterUser", JSON.stringify({
          departmentId: data.department.id,
          departmentName: data.department.name,
          code: code.trim(),
        }));
        toast({ title: "Access granted", description: `Welcome to ${data.department.name} Examination Schedule` });
        setLocation("/exam-schedule");
      } else {
        setError(data.message || "Access denied");
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-violet-50 via-white to-violet-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center mb-4">
            <div className="p-4 bg-violet-600 rounded-2xl shadow-lg">
              <PhoneCall className="h-10 w-10 text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Call Center</h1>
          <p className="text-gray-500">Examination Appointment Scheduler</p>
        </div>

        <Card className="shadow-xl border border-violet-100">
          <CardHeader>
            <CardTitle className="text-center text-violet-800">Sign In</CardTitle>
            <CardDescription className="text-center">Select your department and enter the access code</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label className="flex items-center gap-1.5"><Building2 className="w-4 h-4" /> Department</Label>
                <Select value={departmentId} onValueChange={setDepartmentId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select department..." />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map(d => (
                      <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label className="flex items-center gap-1.5"><Lock className="w-4 h-4" /> Access Code</Label>
                <Input
                  type="password"
                  placeholder="Enter your access code"
                  value={code}
                  onChange={e => setCode(e.target.value)}
                  autoComplete="current-password"
                />
              </div>

              <Button
                type="submit"
                className="w-full bg-violet-600 hover:bg-violet-700 text-white"
                disabled={isLoading}
              >
                {isLoading ? "Verifying..." : "Access Exam Schedule"}
              </Button>
            </form>

            <div className="mt-4 text-center text-sm text-gray-500">
              <a href="/" className="text-violet-600 hover:underline">← Back to home</a>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
