import Sidebar from '../components/Sidebar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Upload as UploadIcon } from 'lucide-react';

export default function Upload() {
  return (
    <Sidebar>
      <div className="p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Upload Data</h1>
        <p className="text-gray-600 mb-8">Upload flight test data files</p>

        <Card>
          <CardHeader>
            <CardTitle>File Upload</CardTitle>
            <CardDescription>Upload CSV or Excel files with flight test data</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center">
              <UploadIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">Upload functionality coming soon</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </Sidebar>
  );
}
