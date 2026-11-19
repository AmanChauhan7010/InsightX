import React, { useState, useEffect } from 'react';
import { Layout } from './components/layout/Layout';
import { OverviewDashboard } from './features/dashboard/OverviewDashboard';
import { NewAnalysisWorkspace } from './features/upload/NewAnalysisWorkspace';
import { AnalysisResults } from './features/findings/AnalysisResults';
import { RootCauseExplorer } from './features/root-cause/RootCauseExplorer';
import { RecommendationsView } from './features/recommendations/RecommendationsView';
import { EvidenceView } from './features/evidence/EvidenceView';
import { HistoryAndReportsView } from './features/reports/HistoryAndReportsView';
import { AnalysisDetail, FixApplyResult } from './types';
import { api } from './services/api';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('overview');
  const [activeAnalysis, setActiveAnalysis] = useState<AnalysisDetail | null>(null);
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [lastFixResult, setLastFixResult] = useState<FixApplyResult | null>(null);
  const [dashboardRefreshSignal, setDashboardRefreshSignal] = useState(0);

  // On first load, hydrate the most recent analysis if any exists in SQLite
  useEffect(() => {
    api.listAnalyses(1)
      .then((analyses) => {
        if (analyses.length > 0) {
          api.getAnalysis(analyses[0].id)
            .then((detail) => setActiveAnalysis(detail))
            .catch((e) => console.error(e));
        }
      })
      .catch((e) => console.error(e));
  }, []);

  const handleSelectAnalysis = async (id: string, targetTab: string = 'findings') => {
    try {
      const detail = await api.getAnalysis(id);
      setLastFixResult(null);
      setActiveAnalysis(detail);
      setCurrentTab(targetTab);
    } catch (e) {
      console.error(e);
    }
  };

  const handleSelectRevision = async (id: string) => {
    try {
      const detail = await api.getAnalysis(id);
      setLastFixResult(null);
      setActiveAnalysis(detail);
    } catch (e) {
      console.error(e);
    }
  };

  const handleLoadSample = async (caseId: string) => {
    setIsLoadingSample(true);
    setIsProcessing(true);
    try {
      const detail = await api.loadSampleCase(caseId);
      setLastFixResult(null);
      setActiveAnalysis(detail);
      setDashboardRefreshSignal((n) => n + 1);
      setCurrentTab('findings');
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoadingSample(false);
      setIsProcessing(false);
    }
  };

  const handleAnalysisComplete = (analysis: AnalysisDetail) => {
    setLastFixResult(null);
    setActiveAnalysis(analysis);
    setDashboardRefreshSignal((n) => n + 1);
    setCurrentTab('findings');
  };

  const handleFixApplied = (updatedAnalysis: AnalysisDetail, fixResult?: FixApplyResult) => {
    setActiveAnalysis(updatedAnalysis);
    setLastFixResult(fixResult || null);
    setDashboardRefreshSignal((n) => n + 1);
  };

  const handleRefreshAnalysis = async () => {
    if (activeAnalysis) {
      try {
        const updated = await api.getAnalysis(activeAnalysis.id);
        setActiveAnalysis(updated);
      } catch (e) {
        console.error(e);
      }
    }
  };

  return (
    <Layout
      currentTab={currentTab}
      onSelectTab={setCurrentTab}
      activeAnalysis={activeAnalysis}
      isProcessing={isProcessing}
    >
      {currentTab === 'overview' && (
        <OverviewDashboard
          onSelectAnalysis={(id) => handleSelectAnalysis(id, 'findings')}
          onOpenReport={(id) => handleSelectAnalysis(id, 'reports')}
          onNewAnalysis={() => setCurrentTab('upload')}
          onViewAllHistory={() => setCurrentTab('reports')}
          onLoadSample={handleLoadSample}
          isLoadingSample={isLoadingSample}
          refreshSignal={dashboardRefreshSignal}
        />
      )}

      {currentTab === 'upload' && (
        <NewAnalysisWorkspace
          onAnalysisComplete={handleAnalysisComplete}
          onProcessingChange={setIsProcessing}
        />
      )}

      {currentTab === 'findings' && (
        activeAnalysis ? (
          <AnalysisResults
            key={activeAnalysis.id}
            analysis={activeAnalysis}
            onNavigateToRootCause={() => setCurrentTab('root-cause')}
            onNavigateToRecommendations={() => setCurrentTab('recommendations')}
          />
        ) : (
          <div className="p-12 text-center bg-white rounded-xl border border-slate-200 space-y-3">
            <h3 className="font-semibold text-slate-800 text-sm">No Active Analysis Selected</h3>
            <p className="text-xs text-slate-500">Run a new analysis or select one from history to inspect findings.</p>
            <button
              onClick={() => setCurrentTab('upload')}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg"
            >
              Start New Analysis
            </button>
          </div>
        )
      )}

      {currentTab === 'root-cause' && (
        activeAnalysis ? (
          <RootCauseExplorer
            key={activeAnalysis.id}
            analysis={activeAnalysis}
            onNavigateToRecommendations={() => setCurrentTab('recommendations')}
          />
        ) : (
          <div className="p-12 text-center bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
            Please run or select an analysis to explore probable root causes.
          </div>
        )
      )}

      {currentTab === 'recommendations' && (
        activeAnalysis ? (
          <RecommendationsView
            key={activeAnalysis.id}
            analysis={activeAnalysis}
            onRefreshAnalysis={handleRefreshAnalysis}
            onAnalysisUpdated={handleFixApplied}
            onSelectAnalysis={handleSelectRevision}
            lastFixResult={lastFixResult}
            onClearFixResult={() => setLastFixResult(null)}
          />
        ) : (
          <div className="p-12 text-center bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
            Please run or select an analysis to review recommendations.
          </div>
        )
      )}

      {currentTab === 'evidence' && (
        activeAnalysis ? (
          <EvidenceView key={activeAnalysis.id} analysis={activeAnalysis} />
        ) : (
          <div className="p-12 text-center bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
            Please run or select an analysis to inspect supporting forensic evidence.
          </div>
        )
      )}

      {currentTab === 'reports' && (
        <HistoryAndReportsView
          activeAnalysis={activeAnalysis}
          onSelectAnalysis={(id) => handleSelectAnalysis(id, 'findings')}
        />
      )}
    </Layout>
  );
};

export default App;
