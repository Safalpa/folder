import React, { useEffect, useRef } from 'react';
import { Download, Share2, Edit3, Copy, Trash2, Move } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

/**
 * ACL-aware Context Menu
 * 
 * Permission Levels:
 * - read: Download only
 * - write: Download, Rename, Move, Copy
 * - full: All actions including Share and Delete
 * - owner: Always has full permission
 */
const ContextMenu = ({ x, y, file, onClose, onAction }) => {
  const { user } = useAuth();
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        onClose();
      }
    };

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  // Determine effective permission
  const getEffectivePermission = () => {
    // If user is owner (based on owner_id or owner_username match)
    if (file.owner_id === user?.id || file.owner_username === user?.username) {
      return 'full';
    }
    // Otherwise use shared_permission from backend
    return file.shared_permission || null;
  };

  const permission = getEffectivePermission();
  
  // If no permission and not owner, hide context menu
  if (!permission) {
    return null;
  }

  // Define available actions based on permission level
  const canDownload = permission === 'read' || permission === 'write' || permission === 'full';
  const canModify = permission === 'write' || permission === 'full';
  const canDelete = permission === 'full';
  const canShare = permission === 'full';

  const menuItems = [
    // Download (available for files with read+ permission)
    ...(file.is_folder ? [] : canDownload ? [
      { icon: Download, label: 'Download', action: 'download', testId: 'context-download' }
    ] : []),
    
    // Share (only for full permission)
    ...(canShare ? [
      { icon: Share2, label: 'Share', action: 'share', testId: 'context-share' }
    ] : []),
    
    // Modify actions (write+ permission)
    ...(canModify ? [
      { icon: Edit3, label: 'Rename', action: 'rename', testId: 'context-rename' },
      { icon: Copy, label: 'Copy', action: 'copy', testId: 'context-copy' },
      { icon: Move, label: 'Move', action: 'move', testId: 'context-move' },
    ] : []),
    
    // Divider before delete
    ...(canDelete ? [{ divider: true }] : []),
    
    // Delete (only for full permission)
    ...(canDelete ? [
      { icon: Trash2, label: 'Delete', action: 'delete', danger: true, testId: 'context-delete' },
    ] : []),
  ];

  // If no actions available, don't show menu
  if (menuItems.length === 0) {
    return null;
  }

  return (
    <div
      ref={menuRef}
      className="context-menu"
      style={{ left: x, top: y }}
      data-testid="context-menu"
    >
      {menuItems.map((item, index) =>
        item.divider ? (
          <div key={index} className="context-menu-divider" />
        ) : (
          <button
            key={index}
            onClick={() => {
              onAction(item.action, file);
              onClose();
            }}
            data-testid={item.testId}
            className={`context-menu-item ${item.danger ? 'text-red-600 hover:bg-red-50' : ''}`}
          >
            <item.icon size={16} />
            <span>{item.label}</span>
          </button>
        )
      )}
    </div>
  );
};

export default ContextMenu;
