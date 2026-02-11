import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { trpc } from "@/lib/trpc";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

export default function Parameters() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [newParamName, setNewParamName] = useState("");
  const [newParamUnit, setNewParamUnit] = useState("");
  const [newParamDescription, setNewParamDescription] = useState("");
  const [newParamType, setNewParamType] = useState("");

  const { data: parameters, isLoading, refetch } = trpc.parameters.list.useQuery();
  const createMutation = trpc.parameters.create.useMutation();

  const filteredParams = parameters?.filter((param) =>
    param.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    param.unit?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCreateParameter = async () => {
    if (!newParamName) {
      toast.error("Please enter a parameter name");
      return;
    }

    try {
      await createMutation.mutateAsync({
        name: newParamName,
        unit: newParamUnit,
        description: newParamDescription,
        parameterType: newParamType,
      });
      toast.success("Parameter created successfully");
      setIsCreateDialogOpen(false);
      setNewParamName("");
      setNewParamUnit("");
      setNewParamDescription("");
      setNewParamType("");
      refetch();
    } catch (error) {
      toast.error("Failed to create parameter");
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Parameters</h1>
          <p className="text-muted-foreground mt-1">
            Manage test parameters and their definitions
          </p>
        </div>
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button size="lg">
              <Plus className="w-4 h-4 mr-2" />
              New Parameter
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Parameter</DialogTitle>
              <DialogDescription>
                Add a new parameter definition for flight test measurements.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="param-name">Parameter Name *</Label>
                <Input
                  id="param-name"
                  placeholder="e.g., Altitude"
                  value={newParamName}
                  onChange={(e) => setNewParamName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="param-unit">Unit</Label>
                <Input
                  id="param-unit"
                  placeholder="e.g., ft, m/s, °C"
                  value={newParamUnit}
                  onChange={(e) => setNewParamUnit(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="param-type">Type</Label>
                <Input
                  id="param-type"
                  placeholder="e.g., Altitude, Speed, Temperature"
                  value={newParamType}
                  onChange={(e) => setNewParamType(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="param-description">Description</Label>
                <Textarea
                  id="param-description"
                  placeholder="Brief description of the parameter..."
                  value={newParamDescription}
                  onChange={(e) => setNewParamDescription(e.target.value)}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateParameter} disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create Parameter"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
        <Input
          placeholder="Search parameters..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {isLoading ? (
        <Card>
          <CardContent className="py-12">
            <div className="animate-pulse space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 bg-muted rounded"></div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : filteredParams && filteredParams.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Parameter List</CardTitle>
            <CardDescription>
              {filteredParams.length} parameter{filteredParams.length !== 1 ? "s" : ""} defined
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {filteredParams.map((param) => (
                <div
                  key={param.id}
                  className="flex items-center justify-between p-4 border border-border rounded-lg hover:bg-accent/50 transition-colors"
                >
                  <div className="flex-1">
                    <h3 className="font-semibold text-foreground">{param.name}</h3>
                    {param.description && (
                      <p className="text-sm text-muted-foreground mt-1">
                        {param.description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-4">
                    {param.unit && (
                      <span className="text-sm font-medium text-muted-foreground">
                        {param.unit}
                      </span>
                    )}
                    {param.parameterType && (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
                        {param.parameterType}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <h3 className="text-lg font-semibold mb-2">No parameters found</h3>
            <p className="text-muted-foreground text-center mb-4">
              {searchQuery ? "Try adjusting your search" : "Create your first parameter to get started"}
            </p>
            {!searchQuery && (
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create Parameter
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
