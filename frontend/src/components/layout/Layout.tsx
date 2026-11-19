import React from 'react';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { AnalysisDetail } from '../../types';

interface LayoutProps {
  children: React.ReactNode;
  currentTab: string;
  onSelectTab: (tabId: string) => void;
  activeAnalysis: AnalysisDetail | null;
  isProcessing?: boolean;
}

export const Layout: React.FC<LayoutProps> = ({
  children,
  currentTab,
  onSelectTab,
  activeAnalysis,
  isProcessing = false,
}) => {
  const isDraftMode = currentTab === 'upload';
  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC]">
      <Navbar
        onNewAnalysis={() => onSelectTab('upload')}
        activeAnalysisTitle={activeAnalysis?.title}
        activeAnalysisScore={activeAnalysis?.overall_score}
        isDraftMode={isDraftMode}
        isProcessing={isProcessing}
      />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          currentTab={currentTab}
          onSelectTab={onSelectTab}
          activeAnalysis={activeAnalysis}
          isProcessing={isProcessing}
        />
        <main className="flex-1 overflow-y-auto p-8 max-w-7xl mx-auto w-full">
          {children}
        </main>
      </div>
    </div>
  );
};
