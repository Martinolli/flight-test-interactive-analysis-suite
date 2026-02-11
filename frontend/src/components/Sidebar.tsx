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
  LogOut,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'wouter';
import { useAuth } from '../contexts/AuthContext';

interface SidebarProps {
  children: React.ReactNode;
}

export default function Sidebar({ children }: SidebarProps) {
  const [location, setLocation] = useLocation();
  const { user, logout } = useAuth();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(256);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const navigation = useMemo(
    () => [
      { name: 'Dashboard', href: '/', icon: LayoutDashboard },
      { name: 'Upload Data', href: '/upload', icon: Upload },
      { name: 'Parameters', href: '/parameters', icon: BarChart3 },
      { name: 'Profile', href: '/profile', icon: User },
      { name: 'Settings', href: '/settings', icon: Settings },
    ],
    []
  );

  const handleLogout = async () => {
    await logout();
    setLocation('/login');
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!dragRef.current || isCollapsed) return;
      const minWidth = 220;
      const maxWidth = 360;
      const next = dragRef.current.startWidth + (e.clientX - dragRef.current.startX);
      setSidebarWidth(Math.max(minWidth, Math.min(maxWidth, next)));
    };

    const handleMouseUp = () => {
      dragRef.current = null;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isCollapsed]);

  return (
    <div className="h-screen flex bg-gray-50">
      {/* Sidebar */}
      <div
        className="bg-white border-r border-gray-200 flex flex-col shrink-0"
        style={{ width: isCollapsed ? 72 : sidebarWidth }}
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between gap-2 px-4 border-b border-gray-200">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center font-semibold">
              F
            </div>
            {!isCollapsed && (
              <div className="min-w-0">
                <h1 className="text-sm font-semibold text-gray-900 leading-tight truncate">
                  FTIAS
                </h1>
                <p className="text-xs text-gray-500 leading-tight truncate">
                  Flight Test Suite
                </p>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={() => setIsCollapsed((v) => !v)}
            className="p-2 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
            aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? (
              <ChevronRight className="w-5 h-5" />
            ) : (
              <ChevronLeft className="w-5 h-5" />
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 min-h-0 overflow-y-auto px-3 py-4 space-y-1">
          {navigation.map((item) => {
            const isActive = location === item.href;
            const Icon = item.icon;

            return (
              <button
                key={item.name}
                onClick={() => setLocation(item.href)}
                className={`
                  w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors
                  ${isActive
                    ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-100'
                    : 'text-gray-700 hover:bg-gray-100'
                  }
                `}
                title={isCollapsed ? item.name : undefined}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon className="w-5 h-5" />
                {!isCollapsed && <span className="truncate">{item.name}</span>}
              </button>
            );
          })}
        </nav>

        {/* User section */}
        <div className="border-t border-gray-200 p-3">
          <div className={`flex items-center gap-3 ${isCollapsed ? 'justify-center' : ''}`}>
            <div className="w-9 h-9 bg-blue-600 rounded-full flex items-center justify-center text-white font-medium">
              {user?.username?.charAt(0).toUpperCase() || 'U'}
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {user?.full_name || user?.username}
                </p>
                <p className="text-xs text-gray-500 truncate">
                  {user?.email}
                </p>
              </div>
            )}
          </div>
          <button
            onClick={handleLogout}
            className={`mt-3 w-full flex items-center ${isCollapsed ? 'justify-center' : 'gap-2'} px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-xl transition-colors`}
            title={isCollapsed ? 'Logout' : undefined}
          >
            <LogOut className="w-4 h-4" />
            {!isCollapsed && <span>Logout</span>}
          </button>
        </div>
      </div>

      {/* Resize handle */}
      <div
        className={`w-1 shrink-0 self-stretch bg-transparent hover:bg-gray-200 ${isCollapsed ? 'hidden' : 'block'}`}
        onMouseDown={(e) => {
          e.preventDefault();
          dragRef.current = { startX: e.clientX, startWidth: sidebarWidth };
        }}
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize sidebar"
        style={{ cursor: 'col-resize' }}
      />

      {/* Main content */}
      <div className="flex-1 min-w-0 overflow-auto">
        {children}
      </div>
    </div>
  );
}
