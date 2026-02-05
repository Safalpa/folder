import React, { useState, useEffect } from 'react';
import { Search, Plus, Upload, Grid3x3, List, FolderPlus } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import Breadcrumb from '@/components/Breadcrumb';
import FileCard from '@/components/FileCard';
import ContextMenu from '@/components/ContextMenu';
import ShareDialog from '@/components/ShareDialog';
import UploadDropzone from '@/components/UploadDropzone';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import api from '@/lib/api';

const FileExplorerPage = () => {
  const [files, setFiles] = useState([]);
  const [currentPath, setCurrentPath] = useState('/');
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('grid');
  const [contextMenu, setContextMenu] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [showShareDialog, setShowShareDialog] = useState(false);
  const [showNewFolderDialog, setShowNewFolderDialog] = useState(false);
  const [showRenameDialog, setShowRenameDialog] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [newFileName, setNewFileName] = useState('');

  useEffect(() => {
    loadFiles(currentPath);
  }, [currentPath]);

  const loadFiles = async (path) => {
    setLoading(true);
    try {
      const response = await api.get(`/files?path=${encodeURIComponent(path)}`);
      // Backend returns array directly, not {files}
      setFiles(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      toast.error('Failed to load files');
    } finally {
      setLoading(false);
    }
  };

  const handleFileClick = (file) => {
    if (file.is_folder) {
      setCurrentPath(file.path);
    } else {
      // Preview or download
      handleDownload(file);
    }
  };

  const handleContextMenu = (e, file) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY });
    setSelectedFile(file);
  };

  const handleContextAction = async (action, file) => {
    switch (action) {
      case 'download':
        handleDownload(file);
        break;
      case 'share':
        setShowShareDialog(true);
        break;
      case 'rename':
        setNewFileName(file.filename);
        setShowRenameDialog(true);
        break;
      case 'delete':
        handleDelete(file);
        break;
      default:
        toast.info(`${action} feature coming soon`);
    }
  };

  const handleDownload = async (file) => {
    try {
      const response = await api.get(`/files/download?path=${encodeURIComponent(file.file_path)}`, {
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

  const handleUpload = async (file, path) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('parent_path', path);

    await api.post('/files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    loadFiles(currentPath);
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) {
      toast.error('Folder name cannot be empty');
      return;
    }

    try {
      await api.post('/files/folder', {
        filename: newFolderName,
        parent_path: currentPath,
        is_folder: true,
      });

      toast.success('Folder created successfully');
      setShowNewFolderDialog(false);
      setNewFolderName('');
      loadFiles(currentPath);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create folder');
    }
  };

  const handleRename = async () => {
    if (!newFileName.trim()) {
      toast.error('File name cannot be empty');
      return;
    }

    try {
      await api.put('/files/rename', {
        source_path: selectedFile.file_path,
        new_name: newFileName,
      });

      toast.success('Renamed successfully');
      setShowRenameDialog(false);
      setNewFileName('');
      loadFiles(currentPath);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to rename');
    }
  };

  const handleDelete = async (file) => {
    if (!window.confirm(`Are you sure you want to delete "${file.filename}"?`)) {
      return;
    }

    try {
      await api.delete(`/files/delete?path=${encodeURIComponent(file.file_path)}`);
      toast.success('Deleted successfully');
      loadFiles(currentPath);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete');
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadFiles(currentPath);
      return;
    }

    try {
      const response = await api.get(`/search?query=${encodeURIComponent(searchQuery)}`);
      setFiles(response.data.results);
    } catch (error) {
      toast.error('Search failed');
    }
  };

  return (
    <div className="flex h-screen bg-slate-50" data-testid="file-explorer-page">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white/80 backdrop-blur-md border-b border-slate-200 px-8 py-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-semibold text-slate-900">My Files</h2>
            <div className="flex items-center gap-2">
              <Button
                onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
                variant="outline"
                size="sm"
                data-testid="view-mode-toggle"
              >
                {viewMode === 'grid' ? <List size={18} /> : <Grid3x3 size={18} />}
              </Button>
              <Button
                onClick={() => setShowNewFolderDialog(true)}
                variant="outline"
                size="sm"
                data-testid="new-folder-button"
              >
                <FolderPlus size={18} className="mr-2" />
                New Folder
              </Button>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <Breadcrumb path={currentPath} onNavigate={setCurrentPath} />
            <div className="flex-1 max-w-md ml-auto">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={18} />
                <Input
                  placeholder="Search files..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  className="pl-10"
                  data-testid="search-input"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto px-8 py-6">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <p className="text-slate-500">Loading...</p>
            </div>
          ) : (
            <>
              {/* Upload Dropzone */}
              <div className="mb-6">
                <UploadDropzone onUpload={handleUpload} currentPath={currentPath} />
              </div>

              {/* Files Grid */}
              {files.length === 0 ? (
                <div className="text-center py-16">
                  <p className="text-slate-500 text-lg">This folder is empty</p>
                  <p className="text-slate-400 text-sm mt-2">Upload files or create a new folder to get started</p>
                </div>
              ) : (
                <div className={`
                  ${viewMode === 'grid' 
                    ? 'grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6'
                    : 'space-y-2'
                  }
                `}>
                  {files.map((file) => (
                    <FileCard
                      key={file.id}
                      file={file}
                      onClick={handleFileClick}
                      onContextMenu={handleContextMenu}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          file={selectedFile}
          onClose={() => setContextMenu(null)}
          onAction={handleContextAction}
        />
      )}

      {/* Share Dialog */}
      {showShareDialog && selectedFile && (
        <ShareDialog
          isOpen={showShareDialog}
          onClose={() => setShowShareDialog(false)}
          file={selectedFile}
        />
      )}

      {/* New Folder Dialog */}
      <Dialog open={showNewFolderDialog} onOpenChange={setShowNewFolderDialog}>
        <DialogContent data-testid="new-folder-dialog">
          <DialogHeader>
            <DialogTitle>Create New Folder</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Label htmlFor="folder-name">Folder Name</Label>
            <Input
              id="folder-name"
              data-testid="folder-name-input"
              placeholder="Enter folder name"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              className="mt-2"
              onKeyPress={(e) => e.key === 'Enter' && handleCreateFolder()}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewFolderDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateFolder} data-testid="create-folder-submit">
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename Dialog */}
      <Dialog open={showRenameDialog} onOpenChange={setShowRenameDialog}>
        <DialogContent data-testid="rename-dialog">
          <DialogHeader>
            <DialogTitle>Rename</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Label htmlFor="new-name">New Name</Label>
            <Input
              id="new-name"
              data-testid="rename-input"
              placeholder="Enter new name"
              value={newFileName}
              onChange={(e) => setNewFileName(e.target.value)}
              className="mt-2"
              onKeyPress={(e) => e.key === 'Enter' && handleRename()}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRenameDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleRename} data-testid="rename-submit">
              Rename
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default FileExplorerPage;
