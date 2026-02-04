import React from 'react';
import { NavLink } from 'react-router-dom';
import { Home, Share2, Shield, LogOut, FolderOpen } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

const Sidebar = () => {
  const { user, logout } = useAuth();

  const navItems = [
    { icon: Home, label: 'My Files', path: '/', testId: 'nav-my-files' },
    { icon: Share2, label: 'Shared with me', path: '/shared', testId: 'nav-shared' },
  ];

  if (user?.is_admin) {
    navItems.push({ icon: Shield, label: 'Admin', path: '/admin', testId: 'nav-admin' });
  }

  return (
    <div className="w-64 bg-white border-r border-slate-200 h-full flex flex-col" data-testid="sidebar">
      <div className="p-6 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center">
            <FolderOpen className="text-white" size={20} />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Secure Vault</h1>
            <p className="text-xs text-slate-500">File Manager</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4">
        <div className="space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              data-testid={item.testId}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700 font-medium'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`
              }
            >
              <item.icon size={20} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      <div className="p-4 border-t border-slate-200">
        <div className="bg-slate-50 rounded-lg p-4 mb-3">
          <p className="text-sm font-medium text-slate-900">{user?.display_name || user?.username}</p>
          <p className="text-xs text-slate-500">{user?.email}</p>
          {user?.is_admin && (
            <span className="inline-block mt-2 px-2 py-1 bg-indigo-100 text-indigo-700 text-xs font-medium rounded">
              Admin
            </span>
          )}
        </div>
        <button
          onClick={logout}
          data-testid="logout-button"
          className="w-full flex items-center gap-2 px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
        >
          <LogOut size={18} />
          <span>Logout</span>
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
