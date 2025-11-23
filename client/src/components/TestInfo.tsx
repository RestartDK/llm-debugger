import React from 'react';
import type { TestSuite, TestCase } from '@/lib/types';
import { ChevronDown, ChevronRight, TestTube, FileText } from 'lucide-react';

interface TestInfoProps {
  suite?: TestSuite;
  testCase?: TestCase;
}

export const TestInfo: React.FC<TestInfoProps> = ({ suite, testCase }) => {
  const [isOpen, setIsOpen] = React.useState(true);

  if (!suite && !testCase) {
    return null;
  }

  return (
    <div className="flex flex-col border-b border-border bg-card">
      <div 
        className="flex items-center px-4 py-2 bg-muted/30 cursor-pointer hover:bg-muted/50 select-none"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <ChevronDown className="h-4 w-4 mr-2" /> : <ChevronRight className="h-4 w-4 mr-2" />}
        <TestTube className="h-4 w-4 mr-2" />
        <span className="text-xs font-bold tracking-wider text-muted-foreground">TEST INFORMATION</span>
      </div>
      
      {isOpen && (
        <div className="px-4 py-3 space-y-4 text-xs">
          {suite && (
            <div className="space-y-2">
              <div className="font-semibold text-foreground">Test Suite</div>
              <div className="space-y-1 text-muted-foreground">
                <div>
                  <span className="font-medium">Target Function:</span> {suite.target_function}
                </div>
                <div>
                  <span className="font-medium">Test Style:</span> {suite.test_style}
                </div>
                <div>
                  <span className="font-medium">Total Tests:</span> {suite.tests.length}
                </div>
                {suite.summary && (
                  <div className="mt-2 pt-2 border-t border-border">
                    <div className="font-medium mb-1">Summary:</div>
                    <div className="text-[11px] leading-relaxed">{suite.summary}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {testCase && (
            <div className="space-y-2 pt-2 border-t border-border">
              <div className="flex items-center gap-2">
                <FileText className="h-3 w-3" />
                <div className="font-semibold text-foreground">Executed Test Case</div>
              </div>
              <div className="space-y-2 text-muted-foreground">
                <div>
                  <span className="font-medium">Name:</span> {testCase.name}
                </div>
                {testCase.description && (
                  <div>
                    <span className="font-medium">Description:</span>
                    <div className="mt-1 text-[11px] leading-relaxed pl-2 border-l-2 border-border">
                      {testCase.description}
                    </div>
                  </div>
                )}
                {testCase.input && (
                  <div>
                    <span className="font-medium">Input:</span>
                    <pre className="mt-1 p-2 bg-muted rounded text-[10px] font-mono overflow-x-auto border border-border">
                      {testCase.input}
                    </pre>
                  </div>
                )}
                {testCase.expected_output && (
                  <div>
                    <span className="font-medium">Expected Output:</span>
                    <pre className="mt-1 p-2 bg-muted rounded text-[10px] font-mono overflow-x-auto border border-border">
                      {testCase.expected_output}
                    </pre>
                  </div>
                )}
                {testCase.notes && (
                  <div>
                    <span className="font-medium">Notes:</span>
                    <div className="mt-1 text-[11px] leading-relaxed pl-2 border-l-2 border-border italic">
                      {testCase.notes}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

