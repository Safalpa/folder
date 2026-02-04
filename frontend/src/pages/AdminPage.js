import React, { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Users, HardDrive, Activity, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { formatFileSize, formatDate } from '@/lib/fileUtils';
import api from '@/lib/api';

const AdminPage = () => {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAdminData();
  }, []);

  const loadAdminData = async () => {
    setLoading(true);
    try {
      const [statsRes, usersRes, logsRes] = await Promise.all([
        api.get('/admin/stats'),
        api.get('/admin/users'),
        api.get('/admin/audit-logs?limit=50'),
      ]);
      
      setStats(statsRes.data);
      setUsers(usersRes.data.users);
      setAuditLogs(logsRes.data.logs);
    } catch (error) {
      toast.error('Failed to load admin data');
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    {
      title: 'Total Users',
      value: stats?.user_count || 0,
      icon: Users,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      title: 'Total Files',
      value: stats?.total_files || 0,
      icon: FileText,
      color: 'text-green-600',
      bg: 'bg-green-50',
    },
    {
      title: 'Storage Used',
      value: stats ? formatFileSize(stats.total_size) : '0 Bytes',
      icon: HardDrive,
      color: 'text-purple-600',
      bg: 'bg-purple-50',
    },
    {
      title: 'Recent Activity',
      value: stats?.recent_activity || 0,
      icon: Activity,
      color: 'text-orange-600',
      bg: 'bg-orange-50',
      subtitle: 'Last 24 hours',
    },
  ];

  return (
    <div className="flex h-screen bg-slate-50" data-testid="admin-page">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="bg-white/80 backdrop-blur-md border-b border-slate-200 px-8 py-6">
          <h2 className="text-2xl font-semibold text-slate-900">Admin Dashboard</h2>
          <p className="text-sm text-slate-600 mt-1">System overview and management</p>
        </div>

        <div className="flex-1 overflow-y-auto px-8 py-6">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <p className="text-slate-500">Loading...</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Stats Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {statCards.map((stat) => (
                  <Card key={stat.title} data-testid={`stat-card-${stat.title.toLowerCase().replace(' ', '-')}`}>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-slate-600">{stat.title}</p>
                          <p className="text-2xl font-semibold text-slate-900 mt-1">{stat.value}</p>
                          {stat.subtitle && (
                            <p className="text-xs text-slate-500 mt-1">{stat.subtitle}</p>
                          )}
                        </div>
                        <div className={`${stat.bg} ${stat.color} p-3 rounded-lg`}>
                          <stat.icon size={24} />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Users Table */}
              <Card data-testid="users-table">
                <CardHeader>
                  <CardTitle>Users</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Username</TableHead>
                        <TableHead>Display Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Last Login</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map((user) => (
                        <TableRow key={user.id}>
                          <TableCell className="font-medium">{user.username}</TableCell>
                          <TableCell>{user.display_name}</TableCell>
                          <TableCell>{user.email}</TableCell>
                          <TableCell>
                            {user.is_admin ? (
                              <span className="px-2 py-1 bg-indigo-100 text-indigo-700 text-xs font-medium rounded">
                                Admin
                              </span>
                            ) : (
                              <span className="px-2 py-1 bg-slate-100 text-slate-700 text-xs font-medium rounded">
                                User
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-sm text-slate-600">
                            {user.last_login ? formatDate(user.last_login) : 'Never'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* Audit Logs */}
              <Card data-testid="audit-logs-table">
                <CardHeader>
                  <CardTitle>Recent Activity (Audit Logs)</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>User</TableHead>
                        <TableHead>Action</TableHead>
                        <TableHead>Resource</TableHead>
                        <TableHead>IP Address</TableHead>
                        <TableHead>Timestamp</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {auditLogs.map((log) => (
                        <TableRow key={log.id}>
                          <TableCell className="font-medium">{log.username}</TableCell>
                          <TableCell>
                            <span className="px-2 py-1 bg-slate-100 text-slate-700 text-xs font-mono rounded">
                              {log.action}
                            </span>
                          </TableCell>
                          <TableCell className="text-sm text-slate-600 max-w-md truncate" title={log.resource}>
                            {log.resource || '-'}
                          </TableCell>
                          <TableCell className="text-sm text-slate-600">{log.ip_address}</TableCell>
                          <TableCell className="text-sm text-slate-600">{formatDate(log.timestamp)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AdminPage;
