/**
 * Upload Data Page
 * Upload flight test data files
 */

import Sidebar from '../components/Sidebar';
import { Upload as UploadIcon } from 'lucide-react';

export default function Upload() {
  return (
    <Sidebar>
      <div className="p-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Upload Data</h1>
          <p className="text-gray-600">Upload flight test data files</p>
        </div>

        <div className="bg-white rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
          <UploadIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Upload your files</h3>
          <p className="text-gray-600 mb-6">Drag and drop files here, or click to browse</p>
          <button className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
            Select Files
          </button>
        </div>
      </div>
    </Sidebar>
  );
}
