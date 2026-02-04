import React, { useEffect, useRef } from 'react';
import { Download, Share2, Edit3, Copy, Trash2, Move } from 'lucide-react';

const ContextMenu = ({ x, y, file, onClose, onAction }) => {
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

  const menuItems = [
    ...(file.is_folder ? [] : [
      { icon: Download, label: 'Download', action: 'download', testId: 'context-download' }
    ]),
    { icon: Share2, label: 'Share', action: 'share', testId: 'context-share' },
    { icon: Edit3, label: 'Rename', action: 'rename', testId: 'context-rename' },
    { icon: Copy, label: 'Copy', action: 'copy', testId: 'context-copy' },
    { icon: Move, label: 'Move', action: 'move', testId: 'context-move' },
    { divider: true },
    { icon: Trash2, label: 'Delete', action: 'delete', danger: true, testId: 'context-delete' },
  ];

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
