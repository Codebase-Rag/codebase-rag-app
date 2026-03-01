import React, { createContext, useContext, useState, ReactNode } from 'react';


interface WorkspaceContextType {
  workspace: string;
  setWorkspace: (newPath: string) => void;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export const WorkspaceProvider = ({ children }: { children: ReactNode }) => {
  const [workspace, setWorkspace] = useState<string>(process.cwd());

  const value: WorkspaceContextType = {
    workspace, 
    setWorkspace,
  }

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = () => {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('WorkspacePath must be used within a WorkspaceProvider');
  }
  return context;
};