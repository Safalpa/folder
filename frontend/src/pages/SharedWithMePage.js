import React, { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import FileCard from '@/components/FileCard';
import { toast } from 'sonner';
import api from '@/lib/api';

const SharedWithMePage = () => {
  const [sharedFiles, setSharedFiles] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadSharedFiles();
  }, []);

  const loadSharedFiles = async () => {
    setLoading(true);
    try {
      const response = await api.get('/shares/with-me');
      // Backend returns {shared_files: [...]}
      setSharedFiles(response.data.shared_files || []);
    } catch (error) {
      toast.error('Failed to load shared files');
    } finally {
      setLoading(false);
    }
  };

  const handleFileClick = (file) => {
    if (!file.is_folder) {
      handleDownload(file);
    }
  };

  const handleDownload = async (file) => {
    try {
      const response = await api.get(`/files/download?path=${encodeURIComponent(file.path)}`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', file.filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      toast.success('Download started');
    } catch (error) {
      toast.error('Failed to download file');
    }
  };

  return (
    <div className="flex h-screen bg-slate-50" data-testid="shared-with-me-page">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="bg-white/80 backdrop-blur-md border-b border-slate-200 px-8 py-6">
          <h2 className="text-2xl font-semibold text-slate-900">Shared with Me</h2>
          <p className="text-sm text-slate-600 mt-1">Files and folders shared by other users</p>
        </div>

        <div className="flex-1 overflow-y-auto px-8 py-6">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <p className="text-slate-500">Loading...</p>
            </div>
          ) : sharedFiles.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-slate-500 text-lg">No shared files</p>
              <p className="text-slate-400 text-sm mt-2">Files shared with you will appear here</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
              {sharedFiles.map((file) => (
                <div key={file.id} className="relative">
                  <FileCard
                    file={file}
                    onClick={handleFileClick}
                    onContextMenu={() => {}}
                  />
                  <div className="absolute bottom-2 left-2 right-2">
                    <div className="bg-white/90 backdrop-blur-sm rounded px-2 py-1 text-xs text-slate-600 text-center">
                      Shared by {file.owner_username}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SharedWithMePage;
