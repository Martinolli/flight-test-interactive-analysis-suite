import Sidebar from '../components/Sidebar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { BarChart3 } from 'lucide-react';

export default function Parameters() {
  return (
    <Sidebar>
      <div className="p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Parameters</h1>
        <p className="text-gray-600 mb-8">View and analyze flight test parameters</p>

        <Card>
          <CardHeader>
            <CardTitle>Parameter Analysis</CardTitle>
            <CardDescription>Interactive parameter visualization and analysis</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center">
              <BarChart3 className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">Parameter visualization coming soon</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </Sidebar>
  );
}
