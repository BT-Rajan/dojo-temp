import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Building, Users, Calendar, Shield, Heart, Clock, CheckCircle } from "lucide-react";
import { useCenterName } from "@/hooks/useCenterName";

export default function Landing() {
  const { centerName } = useCenterName();
  return (
    <div className="min-h-screen">
      <div className="container mx-auto px-4 py-24">
        <div className="text-center mb-20">
          <div className="flex justify-center mb-10">
            <div className="p-6 medical-gradient rounded-3xl shadow-2xl">
              <Building className="h-20 w-20 text-white" />
            </div>
          </div>
          <h1 className="text-6xl font-bold bg-gradient-to-r from-blue-600 to-teal-600 bg-clip-text text-transparent mb-8">
            {centerName}
          </h1>
          <p className="text-2xl text-gray-600 mb-12 max-w-4xl mx-auto leading-relaxed">
            A comprehensive platform for medical departments to manage doctor assignments, 
            clinic schedules, emergency rotations, and administrative functions with modern technology.
          </p>
          <div className="flex flex-col sm:flex-row gap-6 justify-center">
            <Button 
              size="lg" 
              className="btn-gradient px-12 py-6 text-xl font-semibold rounded-2xl shadow-2xl"
              onClick={() => window.location.href = "/login"}
            >
              Staff Login
            </Button>
            <Button 
              size="lg" 
              variant="outline"
              className="px-12 py-6 text-xl border-teal-500/20 hover:bg-teal-500/10 rounded-2xl text-teal-700 border-2"
              onClick={() => window.location.href = "/reception-login"}
            >
              Reception Desk
            </Button>
            <Button 
              size="lg" 
              variant="outline"
              className="px-12 py-6 text-xl border-green-500/20 hover:bg-green-500/10 rounded-2xl text-green-700 border-2"
              onClick={() => window.location.href = "/doctor-login"}
            >
              Doctor Portal
            </Button>
            <Button 
              size="lg" 
              variant="outline"
              className="px-12 py-6 text-xl border-violet-500/20 hover:bg-violet-500/10 rounded-2xl text-violet-700 border-2"
              onClick={() => window.location.href = "/callcenter-login"}
            >
              Call Center
            </Button>
            <Button 
              size="lg" 
              variant="outline"
              className="px-12 py-6 text-xl border-medical-blue/20 hover:bg-medical-blue/10 rounded-2xl"
              onClick={() => window.location.href = "/api/login"}
            >
              Replit Account
            </Button>
          </div>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8 mb-20">
          <Card className="text-center card-hover glass-effect rounded-2xl overflow-hidden">
            <CardHeader className="pb-4">
              <div className="p-4 bg-medical-blue/10 rounded-2xl w-fit mx-auto mb-4">
                <Building className="h-12 w-12 text-medical-blue" />
              </div>
              <CardTitle className="text-xl">Multi-Department</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-gray-600">
                Support for multiple medical departments with isolated data and independent management
              </CardDescription>
            </CardContent>
          </Card>

          <Card className="text-center card-hover glass-effect rounded-2xl overflow-hidden">
            <CardHeader className="pb-4">
              <div className="p-4 bg-healthcare-green/10 rounded-2xl w-fit mx-auto mb-4">
                <Users className="h-12 w-12 text-healthcare-green" />
              </div>
              <CardTitle className="text-xl">Doctor Management</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-gray-600">
                Complete doctor profiles, availability tracking, and assignment management
              </CardDescription>
            </CardContent>
          </Card>

          <Card className="text-center card-hover glass-effect rounded-2xl overflow-hidden">
            <CardHeader className="pb-4">
              <div className="p-4 bg-medical-purple/10 rounded-2xl w-fit mx-auto mb-4">
                <Calendar className="h-12 w-12 text-medical-purple" />
              </div>
              <CardTitle className="text-xl">Smart Scheduling</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-gray-600">
                Automated clinic assignments, emergency rotations, and examination scheduling
              </CardDescription>
            </CardContent>
          </Card>

          <Card className="text-center card-hover glass-effect rounded-2xl overflow-hidden">
            <CardHeader className="pb-4">
              <div className="p-4 bg-warning-orange/10 rounded-2xl w-fit mx-auto mb-4">
                <Shield className="h-12 w-12 text-warning-orange" />
              </div>
              <CardTitle className="text-xl">Secure Access</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-gray-600">
                Role-based access control with department isolation and secure authentication
              </CardDescription>
            </CardContent>
          </Card>
        </div>

        <div className="glass-effect rounded-3xl shadow-2xl p-12">
          <h2 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-teal-600 bg-clip-text text-transparent mb-12 text-center">
            Key Features
          </h2>
          <div className="grid md:grid-cols-2 gap-12">
            <div>
              <div className="flex items-center mb-6">
                <div className="p-3 bg-medical-blue/10 rounded-xl mr-4">
                  <Heart className="h-8 w-8 text-medical-blue" />
                </div>
                <h3 className="text-2xl font-semibold text-gray-800">
                  Department Management
                </h3>
              </div>
              <ul className="space-y-4 text-gray-600">
                <li className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-healthcare-green mr-3" />
                  Create and manage multiple departments
                </li>
                <li className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-healthcare-green mr-3" />
                  Department-specific data isolation
                </li>
                <li className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-healthcare-green mr-3" />
                  Role-based member management
                </li>
                <li className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-healthcare-green mr-3" />
                  Independent scheduling systems
                </li>
              </ul>
            </div>
            <div>
              <div className="flex items-center mb-6">
                <div className="p-3 bg-healthcare-green/10 rounded-xl mr-4">
                  <Clock className="h-8 w-8 text-healthcare-green" />
                </div>
                <h3 className="text-2xl font-semibold text-gray-800">
                  Operations Management
                </h3>
              </div>
              <ul className="space-y-4 text-gray-600">
                <li className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-healthcare-green mr-3" />
                  Weekly clinic assignments
                </li>
                <li className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-healthcare-green mr-3" />
                  Emergency call rotations
                </li>
                <li className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-healthcare-green mr-3" />
                  Leave and permission tracking
                </li>
                <li className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-healthcare-green mr-3" />
                  Examination clinic scheduling
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}