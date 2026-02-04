import React from 'react';
import { ChevronRight, Home } from 'lucide-react';

const Breadcrumb = ({ path, onNavigate }) => {
  const pathParts = path.split('/').filter(Boolean);
  
  const handleClick = (index) => {
    if (index === -1) {
      onNavigate('/');
    } else {
      const newPath = '/' + pathParts.slice(0, index + 1).join('/');
      onNavigate(newPath);
    }
  };

  return (
    <div className="flex items-center gap-2 text-sm" data-testid="breadcrumb">
      <button
        onClick={() => handleClick(-1)}
        className="flex items-center gap-1 text-slate-600 hover:text-indigo-600 transition-colors"
        data-testid="breadcrumb-home"
      >
        <Home size={16} />
        <span>Home</span>
      </button>
      
      {pathParts.map((part, index) => (
        <React.Fragment key={index}>
          <ChevronRight size={16} className="text-slate-400" />
          <button
            onClick={() => handleClick(index)}
            className="text-slate-600 hover:text-indigo-600 transition-colors"
            data-testid={`breadcrumb-${part}`}
          >
            {part}
          </button>
        </React.Fragment>
      ))}
    </div>
  );
};

export default Breadcrumb;
