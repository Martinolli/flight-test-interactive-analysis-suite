/**
 * Parameters Page
 * Manage test parameters
 */

import Sidebar from '../components/Sidebar';
import { BarChart3 } from 'lucide-react';

export default function Parameters() {
  return (
    <Sidebar>
      <div className="p-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Parameters</h1>
          <p className="text-gray-600">Manage and configure test parameters</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <BarChart3 className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Parameters Configuration</h3>
          <p className="text-gray-600">Parameter management will be available here</p>
        </div>
      </div>
    </Sidebar>
  );
}
