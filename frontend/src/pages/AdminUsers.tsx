import { useState, useEffect } from 'react';
import {
  Shield,
  ShieldOff,
  Trash2,
  KeyRound,
  UserCheck,
  UserX,
  Loader2,
  AlertCircle,
  Search,
  RefreshCw,
  Users,
} from 'lucide-react';
import Sidebar from '../components/Sidebar';
import { ConfirmDialog } from '../components/ui/confirm-dialog';
import { ToastContainer, useToast } from '../components/ui/toast';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { ApiService, AdminUser, AdminUserUpdate } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

// ─── Reset Password Modal ─────────────────────────────────────────────────────

function ResetPasswordModal({
  user,
  onClose,
  onSave,
}: {
  user: AdminUser;
  onClose: () => void;
  onSave: (userId: number, newPassword: string) => Promise<void>;
}) {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSave() {
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await onSave(user.id, password);
      onClose();
    } catch (err) {
      setError((err as Error).message || 'Failed to reset password.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Reset Password</h2>
        <p className="text-sm text-gray-500 mb-4">
          Set a new password for <span className="font-medium">{user.username}</span>.
        </p>

        {error && (
          <div className="flex items-start gap-2 p-3 mb-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            {error}
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Min. 8 characters"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Repeat new password"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <Button variant="outline" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saving}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <KeyRound className="w-4 h-4 mr-1" />}
            Save Password
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── User Row ─────────────────────────────────────────────────────────────────

function UserRow({
  user,
  currentUserId,
  onToggleActive,
  onToggleAdmin,
  onResetPassword,
  onDelete,
}: {
  user: AdminUser;
  currentUserId: number;
  onToggleActive: (u: AdminUser) => void;
  onToggleAdmin: (u: AdminUser) => void;
  onResetPassword: (u: AdminUser) => void;
  onDelete: (u: AdminUser) => void;
}) {
  const isSelf = user.id === currentUserId;

  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {user.username.charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">
              {user.username}
              {isSelf && (
                <span className="ml-2 text-xs text-blue-500 font-normal">(you)</span>
              )}
            </p>
            <p className="text-xs text-gray-500">{user.full_name || '—'}</p>
          </div>
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">{user.email}</td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          <Badge
            className={
              user.is_superuser
                ? 'bg-purple-100 text-purple-700 border-purple-200'
                : 'bg-gray-100 text-gray-600 border-gray-200'
            }
          >
            {user.is_superuser ? 'Admin' : 'User'}
          </Badge>
          <Badge
            className={
              user.is_active
                ? 'bg-green-100 text-green-700 border-green-200'
                : 'bg-red-100 text-red-700 border-red-200'
            }
          >
            {user.is_active ? 'Active' : 'Inactive'}
          </Badge>
        </div>
      </td>
      <td className="px-4 py-3 text-xs text-gray-500">
        {new Date(user.created_at).toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        })}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          {/* Toggle active */}
          <button
            title={user.is_active ? 'Deactivate user' : 'Activate user'}
            onClick={() => onToggleActive(user)}
            className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
          >
            {user.is_active ? (
              <UserX className="w-4 h-4 text-orange-500" />
            ) : (
              <UserCheck className="w-4 h-4 text-green-500" />
            )}
          </button>

          {/* Toggle admin */}
          <button
            title={user.is_superuser ? 'Remove admin role' : 'Grant admin role'}
            onClick={() => onToggleAdmin(user)}
            disabled={isSelf}
            className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {user.is_superuser ? (
              <ShieldOff className="w-4 h-4 text-purple-500" />
            ) : (
              <Shield className="w-4 h-4 text-gray-400" />
            )}
          </button>

          {/* Reset password */}
          <button
            title="Reset password"
            onClick={() => onResetPassword(user)}
            className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
          >
            <KeyRound className="w-4 h-4 text-blue-500" />
          </button>

          {/* Delete */}
          <button
            title="Delete user"
            onClick={() => onDelete(user)}
            disabled={isSelf}
            className="p-1.5 rounded hover:bg-red-50 text-gray-500 hover:text-red-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </td>
    </tr>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AdminUsers() {
  const { user: currentUser } = useAuth();
  const toast = useToast();
  const { toasts, dismiss } = toast;

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  // Modals
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  async function loadUsers() {
    setLoading(true);
    setError('');
    try {
      const data = await ApiService.adminListUsers();
      setUsers(data);
    } catch (err) {
      setError((err as Error).message || 'Failed to load users.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function applyUpdate(userId: number, update: AdminUserUpdate, successMsg: string) {
    try {
      const updated = await ApiService.adminUpdateUser(userId, update);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      toast.success(successMsg);
    } catch (err) {
      toast.error((err as Error).message || 'Update failed.');
    }
  }

  function handleToggleActive(user: AdminUser) {
    applyUpdate(
      user.id,
      { is_active: !user.is_active },
      user.is_active
        ? `${user.username} has been deactivated.`
        : `${user.username} has been activated.`
    );
  }

  function handleToggleAdmin(user: AdminUser) {
    applyUpdate(
      user.id,
      { is_superuser: !user.is_superuser },
      user.is_superuser
        ? `Admin role removed from ${user.username}.`
        : `${user.username} is now an admin.`
    );
  }

  async function handleResetPassword(userId: number, newPassword: string) {
    await ApiService.adminUpdateUser(userId, { new_password: newPassword });
    toast.success('Password reset successfully.');
  }

  async function handleDeleteConfirm() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await ApiService.adminDeleteUser(deleteTarget.id);
      setUsers((prev) => prev.filter((u) => u.id !== deleteTarget.id));
      toast.success(`User "${deleteTarget.username}" deleted.`);
    } catch (err) {
      toast.error((err as Error).message || 'Delete failed.');
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  }

  const filtered = users.filter(
    (u) =>
      u.username.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      (u.full_name || '').toLowerCase().includes(search.toLowerCase())
  );

  const adminCount = users.filter((u) => u.is_superuser).length;
  const activeCount = users.filter((u) => u.is_active).length;

  return (
    <Sidebar>
      <ToastContainer toasts={toasts} onDismiss={dismiss} />

      {/* Reset password modal */}
      {resetTarget && (
        <ResetPasswordModal
          user={resetTarget}
          onClose={() => setResetTarget(null)}
          onSave={handleResetPassword}
        />
      )}

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete User"
        description={
          deleteTarget
            ? `Permanently delete "${deleteTarget.username}"? This action cannot be undone.`
            : ''
        }
        confirmLabel="Delete"
        isLoading={isDeleting}
        onConfirm={handleDeleteConfirm}
        onClose={() => setDeleteTarget(null)}
      />

      <div className="p-6 max-w-6xl mx-auto">
        {/* Page header */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-1">
            <Users className="w-5 h-5 text-blue-600" />
            <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          </div>
          <p className="text-sm text-gray-500">
            Manage user accounts, roles, and access. Admin-only panel.
          </p>
        </div>

        {/* Stats row */}
        {!loading && !error && (
          <div className="grid grid-cols-3 gap-4 mb-6">
            <Card>
              <CardContent className="pt-4 pb-4">
                <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Total Users</p>
                <p className="text-2xl font-bold text-gray-900">{users.length}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-4">
                <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Active</p>
                <p className="text-2xl font-bold text-green-600">{activeCount}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-4">
                <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Admins</p>
                <p className="text-2xl font-bold text-purple-600">{adminCount}</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Table card */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="text-base">All Users</CardTitle>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search users…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-8 pr-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-52"
                  />
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadUsers}
                  disabled={loading}
                  className="gap-1"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center py-16 gap-2 text-gray-400">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="text-sm">Loading users…</span>
              </div>
            ) : error ? (
              <div className="flex items-start gap-2 p-6 text-red-700">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium">{error}</p>
                  <button
                    onClick={loadUsers}
                    className="text-xs text-red-600 underline mt-1"
                  >
                    Try again
                  </button>
                </div>
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-16 text-gray-400 text-sm">
                {search ? 'No users match your search.' : 'No users found.'}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50">
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        User
                      </th>
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Email
                      </th>
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Role / Status
                      </th>
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Joined
                      </th>
                      <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((u) => (
                      <UserRow
                        key={u.id}
                        user={u}
                        currentUserId={currentUser?.id ?? -1}
                        onToggleActive={handleToggleActive}
                        onToggleAdmin={handleToggleAdmin}
                        onResetPassword={setResetTarget}
                        onDelete={setDeleteTarget}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </Sidebar>
  );
}
