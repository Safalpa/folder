import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileUp } from 'lucide-react';
import { toast } from 'sonner';

const UploadDropzone = ({ onUpload, currentPath }) => {
  const onDrop = useCallback(async (acceptedFiles) => {
    for (const file of acceptedFiles) {
      try {
        await onUpload(file, currentPath);
        toast.success(`${file.name} uploaded successfully`);
      } catch (error) {
        toast.error(`Failed to upload ${file.name}: ${error.message}`);
      }
    }
  }, [onUpload, currentPath]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxSize: 500 * 1024 * 1024, // 500MB
  });

  return (
    <div
      {...getRootProps()}
      data-testid="upload-dropzone"
      className={`dropzone ${isDragActive ? 'active' : ''}`}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3">
        {isDragActive ? (
          <FileUp className="text-indigo-600" size={48} />
        ) : (
          <Upload className="text-slate-400" size={48} />
        )}
        <div className="text-center">
          <p className="text-base font-medium text-slate-700">
            {isDragActive ? 'Drop files here' : 'Drag and drop files here'}
          </p>
          <p className="text-sm text-slate-500 mt-1">
            or click to browse (max 500MB per file)
          </p>
        </div>
      </div>
    </div>
  );
};

export default UploadDropzone;
