import React from 'react';
import type { TestSuite, TestCase, ExecutionAttempt } from '@/lib/types';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface FinalAnalysisProps {
  finalAnalysis?: string;
  attempts?: ExecutionAttempt[];
  suite?: TestSuite;
  testCase?: TestCase;
}

export const FinalAnalysis: React.FC<FinalAnalysisProps> = ({
  finalAnalysis,
  attempts = [],
  suite,
  testCase,
}) => {
  const [isOpen, setIsOpen] = React.useState(true);
  
  // Calculate summary stats
  const totalAttempts = attempts.length;
  const successfulAttempts = attempts.filter(a => a.status === 'success').length;
  const failedAttempts = attempts.filter(a => a.status === 'error').length;
  
  return (
    <div className="flex flex-col h-full">
      <div 
        className="flex items-center px-4 py-2 bg-muted/30 cursor-pointer hover:bg-muted/50 select-none border-b border-border"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <ChevronDown className="h-4 w-4 mr-2" /> : <ChevronRight className="h-4 w-4 mr-2" />}
        <span className="text-xs font-bold tracking-wider text-muted-foreground whitespace-nowrap overflow-hidden text-ellipsis">FINAL ANALYSIS</span>
      </div>
      
      {isOpen && (
        <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
          <div className="overflow-auto h-full p-4 text-sm">
            {/* Test Summary */}
            {(suite || testCase || attempts.length > 0) && (
              <div className="mb-4 pb-4 border-b border-border">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">Test Summary</h3>
                {testCase && (
                  <div className="mb-2">
                    <div className="font-semibold">{testCase.name}</div>
                    <div className="text-xs text-muted-foreground">{testCase.description}</div>
                  </div>
                )}
                {suite && (
                  <div className="mb-2">
                    <div className="text-xs text-muted-foreground">
                      Target Function: <span className="font-mono">{suite.target_function}</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Total Tests: {suite.tests?.length || 0}
                    </div>
                  </div>
                )}
                {attempts.length > 0 && (
                  <div className="mt-2 text-xs">
                    <div className="text-muted-foreground">
                      Execution Attempts: {totalAttempts} ({successfulAttempts} successful, {failedAttempts} failed)
                    </div>
                  </div>
                )}
              </div>
            )}
            
            {/* Final Analysis Content */}
            {finalAnalysis ? (
              <div className="whitespace-pre-wrap text-sm">
                {finalAnalysis.split('\n').map((line, idx) => {
                  // Simple markdown-like formatting
                  if (line.startsWith('# ')) {
                    return <h1 key={idx} className="text-lg font-bold mt-4 mb-2">{line.substring(2)}</h1>;
                  } else if (line.startsWith('## ')) {
                    return <h2 key={idx} className="text-base font-bold mt-3 mb-1">{line.substring(3)}</h2>;
                  } else if (line.startsWith('### ')) {
                    return <h3 key={idx} className="text-sm font-bold mt-2 mb-1">{line.substring(4)}</h3>;
                  } else if (line.startsWith('- ') || line.startsWith('* ')) {
                    return <div key={idx} className="ml-4 mb-1">• {line.substring(2)}</div>;
                  } else if (line.trim() === '') {
                    return <br key={idx} />;
                  } else {
                    return <div key={idx} className="mb-1">{line}</div>;
                  }
                })}
              </div>
            ) : (
              <div className="text-muted-foreground text-sm">
                No final analysis available.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

