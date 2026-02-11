import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FileUp, Upload as UploadIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

export default function Upload() {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    handleFiles(files);
  };

  const handleFiles = (files: File[]) => {
    files.forEach((file) => {
      const extension = file.name.split(".").pop()?.toLowerCase();
      if (extension === "csv" || extension === "xlsx" || extension === "xls") {
        toast.success(`File ${file.name} ready for upload`);
        // TODO: Implement actual file upload logic
      } else {
        toast.error(`Invalid file type: ${file.name}`);
      }
    });
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Upload Data</h1>
        <p className="text-muted-foreground mt-1">
          Import flight test data from CSV or Excel files
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileUp className="w-5 h-5 text-primary" />
              CSV Upload
            </CardTitle>
            <CardDescription>
              Upload flight test data points in CSV format
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragging
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50"
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <UploadIcon className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-sm text-foreground mb-2">
                Drag and drop your CSV file here
              </p>
              <p className="text-xs text-muted-foreground mb-4">or</p>
              <Button variant="outline" asChild>
                <label className="cursor-pointer">
                  Browse Files
                  <input
                    type="file"
                    accept=".csv"
                    className="hidden"
                    onChange={handleFileInput}
                  />
                </label>
              </Button>
            </div>
            <div className="mt-4 text-sm text-muted-foreground">
              <p className="font-medium mb-2">Expected CSV format:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>First row: Parameter names</li>
                <li>Second row: Units (optional)</li>
                <li>Data rows: Timestamp + values</li>
              </ul>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileUp className="w-5 h-5 text-primary" />
              Excel Upload
            </CardTitle>
            <CardDescription>
              Upload parameter definitions in Excel format
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragging
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50"
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <UploadIcon className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-sm text-foreground mb-2">
                Drag and drop your Excel file here
              </p>
              <p className="text-xs text-muted-foreground mb-4">or</p>
              <Button variant="outline" asChild>
                <label className="cursor-pointer">
                  Browse Files
                  <input
                    type="file"
                    accept=".xlsx,.xls"
                    className="hidden"
                    onChange={handleFileInput}
                  />
                </label>
              </Button>
            </div>
            <div className="mt-4 text-sm text-muted-foreground">
              <p className="font-medium mb-2">Expected Excel format:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Column A: Parameter Name</li>
                <li>Column B: Unit</li>
                <li>Column C: Description</li>
                <li>Column D: Type (optional)</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload History</CardTitle>
          <CardDescription>Recent file uploads and their status</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <p>No uploads yet</p>
            <p className="text-sm mt-2">Upload files will appear here</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
