import { useState } from 'react';
import { Edit2, Save, X, User as UserIcon } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { ToastContainer, useToast } from '../components/ui/toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { AuthService } from '../services/auth';

export default function Profile() {
  const { user } = useAuth();
  const toast = useToast();

  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const token = AuthService.getAccessToken();
      const response = await fetch('http://localhost:8000/api/auth/me', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({ full_name: fullName, email }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Update failed' }));
        throw new Error(err.detail || 'Update failed');
      }

      toast.success('Profile updated', 'Your changes have been saved.');
      setIsEditing(false);
    } catch (err) {
      toast.error('Update failed', err instanceof Error ? err.message : 'Could not save changes.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setFullName(user?.full_name ?? '');
    setEmail(user?.email ?? '');
    setIsEditing(false);
  };

  const initial = user?.username?.charAt(0).toUpperCase() ?? 'U';

  return (
    <Sidebar>
      <div className="p-8 max-w-2xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-1">Profile</h1>
          <p className="text-gray-500">Manage your account information</p>
        </div>

        {/* Avatar + name */}
        <div className="flex items-center gap-5 mb-8">
          <div className="w-20 h-20 bg-blue-600 rounded-full flex items-center justify-center text-white text-3xl font-bold shrink-0">
            {initial}
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              {user?.full_name || user?.username}
            </h2>
            <p className="text-gray-500 text-sm">{user?.email}</p>
            <span className="inline-block mt-1 px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-xs font-medium capitalize border border-blue-100">
              {user?.role ?? 'user'}
            </span>
          </div>
        </div>

        {/* Account details card */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Account Details</CardTitle>
                <CardDescription>Your personal information</CardDescription>
              </div>
              {!isEditing ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsEditing(true)}
                  className="gap-2"
                >
                  <Edit2 className="w-4 h-4" />
                  Edit
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCancel}
                    disabled={isSaving}
                    className="gap-1.5"
                  >
                    <X className="w-4 h-4" />
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSave}
                    disabled={isSaving}
                    className="gap-1.5"
                  >
                    <Save className="w-4 h-4" />
                    {isSaving ? 'Saving…' : 'Save'}
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* Username (read-only) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                  Username
                </label>
                <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-600">
                  <UserIcon className="w-4 h-4 text-gray-400" />
                  {user?.username}
                  <span className="ml-auto text-xs text-gray-400">read-only</span>
                </div>
              </div>

              {/* Role (read-only) */}
              <div>
                <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                  Role
                </label>
                <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-600 capitalize flex items-center justify-between">
                  {user?.role ?? 'user'}
                  <span className="text-xs text-gray-400">read-only</span>
                </div>
              </div>
            </div>

            {/* Full name */}
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                Full Name
              </label>
              {isEditing ? (
                <Input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Enter your full name"
                  disabled={isSaving}
                />
              ) : (
                <p className="text-sm text-gray-900 py-2 px-3 bg-gray-50 border border-gray-200 rounded-lg">
                  {user?.full_name || <span className="text-gray-400 italic">Not set</span>}
                </p>
              )}
            </div>

            {/* Email */}
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                Email Address
              </label>
              {isEditing ? (
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                  disabled={isSaving}
                />
              ) : (
                <p className="text-sm text-gray-900 py-2 px-3 bg-gray-50 border border-gray-200 rounded-lg">
                  {user?.email || <span className="text-gray-400 italic">Not set</span>}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismiss} />
    </Sidebar>
  );
}
