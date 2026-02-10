import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { trpc } from "@/lib/trpc";
import { ArrowLeft, Calendar, Plane, Download } from "lucide-react";
import { useRoute } from "wouter";
import { Link } from "wouter";
import { format } from "date-fns";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function FlightTestDetail() {
  const [, params] = useRoute("/flight-test/:id");
  const flightTestId = params?.id ? parseInt(params.id) : 0;
  const [selectedParameter, setSelectedParameter] = useState<string>("");

  const { data: flightTest, isLoading: isLoadingTest } = trpc.flightTests.getById.useQuery(
    { id: flightTestId },
    { enabled: flightTestId > 0 }
  );

  const { data: dataPoints, isLoading: isLoadingData } = trpc.dataPoints.getByFlightTest.useQuery(
    { flightTestId, limit: 1000 },
    { enabled: flightTestId > 0 }
  );

  const { data: parameters } = trpc.parameters.list.useQuery();

  if (isLoadingTest) {
    return (
      <div className="space-y-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-muted rounded w-1/4"></div>
          <div className="h-64 bg-muted rounded"></div>
        </div>
      </div>
    );
  }

  if (!flightTest) {
    return (
      <div className="text-center py-12">
        <h2 className="text-2xl font-bold text-foreground mb-2">Flight Test Not Found</h2>
        <p className="text-muted-foreground mb-4">
          The requested flight test could not be found.
        </p>
        <Link href="/">
          <Button>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
        </Link>
      </div>
    );
  }

  // Group data points by parameter
  const dataByParameter = dataPoints?.reduce((acc, point) => {
    if (!acc[point.parameterId]) {
      acc[point.parameterId] = [];
    }
    acc[point.parameterId].push(point);
    return {};
  }, {} as Record<number, typeof dataPoints>);

  // Prepare chart data
  const chartData = dataPoints?.map((point) => ({
    timestamp: new Date(point.timestamp).getTime(),
    value: point.value,
    parameterId: point.parameterId,
  })) || [];

  const uniqueParameters = Array.from(new Set(dataPoints?.map(p => p.parameterId) || []));
  const parameterOptions = uniqueParameters.map(id => {
    const param = parameters?.find(p => p.id === id);
    return { id, name: param?.name || `Parameter ${id}`, unit: param?.unit };
  });

  const filteredChartData = selectedParameter
    ? chartData.filter(d => d.parameterId === parseInt(selectedParameter))
    : chartData.slice(0, 100); // Show first 100 points if no parameter selected

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/">
            <Button variant="outline" size="icon">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold text-foreground">{flightTest.name}</h1>
            <div className="flex items-center gap-4 mt-2 text-muted-foreground">
              <span className="flex items-center gap-1">
                <Calendar className="w-4 h-4" />
                {format(new Date(flightTest.testDate), "MMM dd, yyyy")}
              </span>
              {flightTest.aircraft && (
                <span className="flex items-center gap-1">
                  <Plane className="w-4 h-4" />
                  {flightTest.aircraft}
                </span>
              )}
            </div>
          </div>
        </div>
        <Button variant="outline">
          <Download className="w-4 h-4 mr-2" />
          Export Data
        </Button>
      </div>

      {flightTest.description && (
        <Card>
          <CardHeader>
            <CardTitle>Test Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-foreground">{flightTest.description}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Data Visualization</CardTitle>
          <CardDescription>
            {dataPoints?.length || 0} data points collected
          </CardDescription>
        </CardHeader>
        <CardContent>
          {parameterOptions.length > 0 && (
            <div className="mb-6">
              <label className="text-sm font-medium text-foreground mb-2 block">
                Select Parameter
              </label>
              <Select value={selectedParameter} onValueChange={setSelectedParameter}>
                <SelectTrigger className="w-full md:w-64">
                  <SelectValue placeholder="Select a parameter to visualize" />
                </SelectTrigger>
                <SelectContent>
                  {parameterOptions.map((param) => (
                    <SelectItem key={param.id} value={param.id.toString()}>
                      {param.name} {param.unit && `(${param.unit})`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {isLoadingData ? (
            <div className="h-96 flex items-center justify-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            </div>
          ) : filteredChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={filteredChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={(value) => format(new Date(value), "HH:mm:ss")}
                  label={{ value: "Time", position: "insideBottom", offset: -5 }}
                />
                <YAxis
                  label={{ value: "Value", angle: -90, position: "insideLeft" }}
                />
                <Tooltip
                  labelFormatter={(value) => format(new Date(value), "HH:mm:ss")}
                  formatter={(value: number) => [value.toFixed(2), "Value"]}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={false}
                  name={parameterOptions.find(p => p.id === parseInt(selectedParameter))?.name || "Value"}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-96 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <p className="mb-2">No data points available</p>
                <p className="text-sm">Upload data to visualize flight test results</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Status</CardTitle>
          </CardHeader>
          <CardContent>
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
              flightTest.status === "completed" ? "bg-green-100 text-green-800" :
              flightTest.status === "in_progress" ? "bg-blue-100 text-blue-800" :
              flightTest.status === "archived" ? "bg-gray-100 text-gray-800" :
              "bg-yellow-100 text-yellow-800"
            }`}>
              {flightTest.status.replace("_", " ").toUpperCase()}
            </span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Data Points</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-primary">{dataPoints?.length || 0}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Parameters</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-primary">{uniqueParameters.length}</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
