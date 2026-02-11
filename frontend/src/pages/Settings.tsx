/**
 * Settings Page
 * Application settings
 */

import Sidebar from '../components/Sidebar';
import { Settings as SettingsIcon } from 'lucide-react';

export default function Settings() {
  return (
    <Sidebar>
      <div className="p-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Settings</h1>
          <p className="text-gray-600">Configure application settings</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <SettingsIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Application Settings</h3>
          <p className="text-gray-600">Settings configuration will be available here</p>
        </div>
      </div>
    </Sidebar>
  );
}
