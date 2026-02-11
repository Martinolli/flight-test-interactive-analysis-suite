import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { trpc } from "@/lib/trpc";
import { Plus, Search, Calendar, Plane } from "lucide-react";
import { useState } from "react";
import { Link } from "wouter";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { format } from "date-fns";

export default function Home() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [newTestName, setNewTestName] = useState("");
  const [newTestDescription, setNewTestDescription] = useState("");
  const [newTestDate, setNewTestDate] = useState("");
  const [newTestAircraft, setNewTestAircraft] = useState("");

  const { data: flightTests, isLoading, refetch } = trpc.flightTests.list.useQuery();
  const createMutation = trpc.flightTests.create.useMutation();

  const filteredTests = flightTests?.filter((test) =>
    test.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    test.aircraft?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCreateTest = async () => {
    if (!newTestName || !newTestDate) {
      toast.error("Please fill in required fields");
      return;
    }

    try {
      await createMutation.mutateAsync({
        name: newTestName,
        description: newTestDescription,
        testDate: new Date(newTestDate),
        aircraft: newTestAircraft,
        status: "draft",
      });
      toast.success("Flight test created successfully");
      setIsCreateDialogOpen(false);
      setNewTestName("");
      setNewTestDescription("");
      setNewTestDate("");
      setNewTestAircraft("");
      refetch();
    } catch (error) {
      toast.error("Failed to create flight test");
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Flight Tests</h1>
          <p className="text-muted-foreground mt-1">
            Manage and analyze your flight test data
          </p>
        </div>
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button size="lg">
              <Plus className="w-4 h-4 mr-2" />
              New Flight Test
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Flight Test</DialogTitle>
              <DialogDescription>
                Add a new flight test to start collecting and analyzing data.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Test Name *</Label>
                <Input
                  id="name"
                  placeholder="e.g., Cruise Performance Test"
                  value={newTestName}
                  onChange={(e) => setNewTestName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="date">Test Date *</Label>
                <Input
                  id="date"
                  type="date"
                  value={newTestDate}
                  onChange={(e) => setNewTestDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="aircraft">Aircraft</Label>
                <Input
                  id="aircraft"
                  placeholder="e.g., Boeing 737-800"
                  value={newTestAircraft}
                  onChange={(e) => setNewTestAircraft(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  placeholder="Brief description of the test objectives..."
                  value={newTestDescription}
                  onChange={(e) => setNewTestDescription(e.target.value)}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateTest} disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create Test"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
        <Input
          placeholder="Search flight tests..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-6 bg-muted rounded w-3/4"></div>
                <div className="h-4 bg-muted rounded w-1/2 mt-2"></div>
              </CardHeader>
              <CardContent>
                <div className="h-4 bg-muted rounded w-full"></div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredTests && filteredTests.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTests.map((test) => (
            <Link key={test.id} href={`/flight-test/${test.id}`}>
              <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Plane className="w-5 h-5 text-primary" />
                    {test.name}
                  </CardTitle>
                  <CardDescription className="flex items-center gap-2 mt-2">
                    <Calendar className="w-4 h-4" />
                    {format(new Date(test.testDate), "MMM dd, yyyy")}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {test.aircraft && (
                      <p className="text-sm text-muted-foreground">
                        Aircraft: {test.aircraft}
                      </p>
                    )}
                    {test.description && (
                      <p className="text-sm text-muted-foreground line-clamp-2">
                        {test.description}
                      </p>
                    )}
                    <div className="pt-2">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        test.status === "completed" ? "bg-green-100 text-green-800" :
                        test.status === "in_progress" ? "bg-blue-100 text-blue-800" :
                        test.status === "archived" ? "bg-gray-100 text-gray-800" :
                        "bg-yellow-100 text-yellow-800"
                      }`}>
                        {test.status.replace("_", " ").toUpperCase()}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Plane className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No flight tests found</h3>
            <p className="text-muted-foreground text-center mb-4">
              {searchQuery ? "Try adjusting your search" : "Create your first flight test to get started"}
            </p>
            {!searchQuery && (
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create Flight Test
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
