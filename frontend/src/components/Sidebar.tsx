/**
 * Sidebar Component
 * Navigation sidebar for the application
 */

import {
  LayoutDashboard,
  Upload,
  Settings,
  User,
  BarChart3,
  LogOut
} from 'lucide-react';
import { useLocation } from 'wouter';
import { useAuth } from '../contexts/AuthContext';

interface SidebarProps {
  children: React.ReactNode;
}

export default function Sidebar({ children }: SidebarProps) {
  const [location, setLocation] = useLocation();
  const { user, logout } = useAuth();

  const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Upload Data', href: '/upload', icon: Upload },
    { name: 'Parameters', href: '/parameters', icon: BarChart3 },
    { name: 'Profile', href: '/profile', icon: User },
    { name: 'Settings', href: '/settings', icon: Settings },
  ];

  const handleLogout = async () => {
    await logout();
    setLocation('/login');
  };

  return (
    <div className="min-h-screen flex bg-gray-50">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-gray-200">
          <h1 className="text-xl font-bold text-gray-900">FTIAS</h1>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-1">
          {navigation.map((item) => {
            const isActive = location === item.href;
            const Icon = item.icon;

            return (
              <button
                key={item.name}
                onClick={() => setLocation(item.href)}
                className={`
                  w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                  ${isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-700 hover:bg-gray-100'
                  }
                `}
              >
                <Icon className="w-5 h-5" />
                <span>{item.name}</span>
              </button>
            );
          })}
        </nav>

        {/* User section */}
        <div className="border-t border-gray-200 p-4">
          <div className="flex items-center space-x-3 mb-3">
            <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-medium">
              {user?.username?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {user?.full_name || user?.username}
              </p>
              <p className="text-xs text-gray-500 truncate">
                {user?.email}
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>Logout</span>
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-auto">
        {children}
      </div>
    </div>
  );
}
