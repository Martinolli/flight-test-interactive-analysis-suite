import { useAuth } from "@/_core/hooks/useAuth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Mail, User as UserIcon, Calendar } from "lucide-react";
import { format } from "date-fns";

export default function Profile() {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading user profile...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Profile</h1>
        <p className="text-muted-foreground mt-1">
          View and manage your account information
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <CardContent className="flex flex-col items-center pt-6">
            <Avatar className="w-24 h-24 mb-4">
              <AvatarFallback className="text-2xl">
                {user.name?.charAt(0).toUpperCase() || "U"}
              </AvatarFallback>
            </Avatar>
            <h2 className="text-xl font-semibold text-foreground">{user.name || "User"}</h2>
            <p className="text-sm text-muted-foreground mt-1">{user.email}</p>
            <div className="mt-4">
              <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
                user.role === "admin" ? "bg-primary/10 text-primary" : "bg-secondary text-secondary-foreground"
              }`}>
                {user.role?.toUpperCase()}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Account Information</CardTitle>
            <CardDescription>Your personal details and account status</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <UserIcon className="w-5 h-5 text-primary" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-muted-foreground">Full Name</p>
                <p className="text-foreground mt-1">{user.name || "Not provided"}</p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <Mail className="w-5 h-5 text-primary" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-muted-foreground">Email Address</p>
                <p className="text-foreground mt-1">{user.email || "Not provided"}</p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <Calendar className="w-5 h-5 text-primary" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-muted-foreground">Member Since</p>
                <p className="text-foreground mt-1">
                  {user.createdAt ? format(new Date(user.createdAt), "MMMM dd, yyyy") : "Unknown"}
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <Calendar className="w-5 h-5 text-primary" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-muted-foreground">Last Sign In</p>
                <p className="text-foreground mt-1">
                  {user.lastSignedIn ? format(new Date(user.lastSignedIn), "MMMM dd, yyyy 'at' HH:mm") : "Unknown"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Activity Summary</CardTitle>
          <CardDescription>Your recent activity in the system</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <p>Activity tracking coming soon</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
