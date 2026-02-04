export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};

export const getFileIcon = (filename, isFolder) => {
  if (isFolder) return 'Folder';
  
  const ext = filename.split('.').pop().toLowerCase();
  
  const iconMap = {
    pdf: 'FileText',
    doc: 'FileText',
    docx: 'FileText',
    txt: 'FileText',
    jpg: 'Image',
    jpeg: 'Image',
    png: 'Image',
    gif: 'Image',
    svg: 'Image',
    mp4: 'Video',
    avi: 'Video',
    mov: 'Video',
    mp3: 'Music',
    wav: 'Music',
    zip: 'Archive',
    rar: 'Archive',
    '7z': 'Archive',
  };
  
  return iconMap[ext] || 'File';
};

export const getFileIconColor = (filename, isFolder) => {
  if (isFolder) return 'text-amber-500';
  
  const ext = filename.split('.').pop().toLowerCase();
  
  const colorMap = {
    pdf: 'text-red-500',
    doc: 'text-blue-500',
    docx: 'text-blue-500',
    txt: 'text-slate-500',
    jpg: 'text-purple-500',
    jpeg: 'text-purple-500',
    png: 'text-purple-500',
    gif: 'text-purple-500',
    mp4: 'text-pink-500',
    avi: 'text-pink-500',
    mp3: 'text-green-500',
    zip: 'text-orange-500',
  };
  
  return colorMap[ext] || 'text-slate-500';
};

export const formatDate = (dateString) => {
  const date = new Date(dateString);
  const now = new Date();
  const diff = now - date;
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 7) {
    return date.toLocaleDateString();
  } else if (days > 0) {
    return `${days} day${days > 1 ? 's' : ''} ago`;
  } else if (hours > 0) {
    return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  } else if (minutes > 0) {
    return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
  } else {
    return 'Just now';
  }
};
