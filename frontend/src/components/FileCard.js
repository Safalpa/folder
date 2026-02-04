import React from 'react';
import * as LucideIcons from 'lucide-react';
import { getFileIcon, getFileIconColor, formatFileSize, formatDate } from '@/lib/fileUtils';

const FileCard = ({ file, onClick, onContextMenu }) => {
  const IconComponent = LucideIcons[getFileIcon(file.filename, file.is_folder)] || LucideIcons.File;
  const iconColor = getFileIconColor(file.filename, file.is_folder);

  return (
    <div
      onClick={() => onClick(file)}
      onContextMenu={(e) => onContextMenu(e, file)}
      data-testid={`file-card-${file.filename}`}
      className="group relative flex flex-col items-center justify-center p-6 aspect-square bg-white border border-slate-100 hover:border-indigo-200 rounded-xl transition-all cursor-pointer hover:bg-slate-50 hover:shadow-md"
    >
      <div className={`mb-3 ${iconColor} transition-transform group-hover:scale-110`}>
        <IconComponent size={48} strokeWidth={1.5} />
      </div>
      
      <div className="w-full text-center">
        <p className="text-sm font-medium text-slate-900 truncate px-2" title={file.filename}>
          {file.filename}
        </p>
        {!file.is_folder && (
          <p className="text-xs text-slate-500 mt-1">
            {formatFileSize(file.size)}
          </p>
        )}
        <p className="text-xs text-slate-400 mt-1">
          {formatDate(file.modified_at)}
        </p>
      </div>
      
      {file.permission && (
        <div className="absolute top-2 right-2">
          <span className="px-2 py-1 bg-indigo-100 text-indigo-700 text-xs font-medium rounded">
            Shared
          </span>
        </div>
      )}
    </div>
  );
};

export default FileCard;
