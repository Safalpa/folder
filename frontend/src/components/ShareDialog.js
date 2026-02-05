import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import api from '@/lib/api';

const ShareDialog = ({ isOpen, onClose, file }) => {
  const [username, setUsername] = useState('');
  const [permission, setPermission] = useState('read');
  const [loading, setLoading] = useState(false);

  const handleShare = async () => {
    if (!username.trim()) {
      toast.error('Please enter a username');
      return;
    }

    setLoading(true);
    try {
      await api.post('/shares', {
        file_path: file.path,
        shared_with_username: username,
        permission: permission,
      });
      
      toast.success(`Shared ${file.filename} with ${username}`);
      setUsername('');
      setPermission('read');
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to share file');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent data-testid="share-dialog">
        <DialogHeader>
          <DialogTitle>Share {file?.filename}</DialogTitle>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          <div>
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              data-testid="share-username-input"
              placeholder="Enter AD username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="mt-2"
            />
          </div>
          
          <div>
            <Label htmlFor="permission">Permission Level</Label>
            <Select value={permission} onValueChange={setPermission}>
              <SelectTrigger className="mt-2" data-testid="share-permission-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="read">Read Only</SelectItem>
                <SelectItem value="write">Read & Write</SelectItem>
                <SelectItem value="full">Full Control</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleShare} disabled={loading} data-testid="share-submit-button">
            {loading ? 'Sharing...' : 'Share'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ShareDialog;
