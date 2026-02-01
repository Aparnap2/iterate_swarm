'use client';

import { Component, ReactNode, ErrorInfo, useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  reloadCount: number;
}

// Class-based ErrorBoundary for proper error catching
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      reloadCount: 0,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps, prevState: ErrorBoundaryState) {
    // Clear error state when children change to a working state
    if (prevState.hasError && !this.state.hasError) {
      this.setState({ error: null, errorInfo: null });
    }
  }

  handleReload = () => {
    this.setState((prev) => ({ reloadCount: prev.reloadCount + 1 }));
    if (typeof window !== 'undefined') {
      // Add a flag to prevent infinite loops
      const reloadKey = 'error-boundary-last-reload';
      const lastReload = sessionStorage.getItem(reloadKey);
      const now = Date.now();

      if (lastReload && now - parseInt(lastReload) < 2000) {
        // Already reloaded recently, don't reload again
        return;
      }

      sessionStorage.setItem(reloadKey, now.toString());
      window.location.reload();
    }
  };

  handleReset = () => {
    // Only reset if we've already tried reloading
    if (this.state.reloadCount > 0) {
      this.setState({ hasError: false, error: null, errorInfo: null });
    } else {
      // First try reloading
      this.handleReload();
    }
  };

  render() {
    if (this.state.hasError) {
      const isInfiniteLoop = this.state.reloadCount >= 2;

      if (isInfiniteLoop) {
        // Show a simple error state without reload option
        return (
          <div className="min-h-screen bg-stone-50 flex items-center justify-center p-8">
            <div className="text-center max-w-md">
              <h2 className="text-xl font-semibold text-stone-900 mb-2">
                Something went wrong
              </h2>
              <p className="text-stone-600 mb-4">
                {this.state.error?.message || 'An unexpected error occurred'}
              </p>
              <Button
                onClick={() => {
                  sessionStorage.removeItem('error-boundary-last-reload');
                  this.setState({ hasError: false, error: null, errorInfo: null, reloadCount: 0 });
                }}
                variant="outline"
              >
                Clear Error and Continue
              </Button>
            </div>
          </div>
        );
      }

      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 max-w-md">
            <AlertTriangle className="h-12 w-12 text-red-600 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-red-900 mb-2">
              Something went wrong
            </h2>
            <p className="text-red-700 mb-4">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <div className="flex gap-2 justify-center">
              <Button
                onClick={this.handleReload}
                variant="outline"
                className="bg-white hover:bg-red-50"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Reload Page
              </Button>
              <Button
                onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
                variant="outline"
                className="bg-white"
              >
                Try Again
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

interface AsyncErrorBoundaryProps {
  children: ReactNode;
  loader?: ReactNode;
}

interface AsyncErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export function AsyncErrorBoundary({ children, loader }: AsyncErrorBoundaryProps) {
  const [reloadCount, setReloadCount] = useState(0);

  const handleRetry = useCallback(() => {
    setReloadCount((prev) => {
      const newCount = prev + 1;
      if (newCount >= 2) {
        // Already tried twice, show different state
        return newCount;
      }
      // First retry attempt - reload once
      if (typeof window !== 'undefined') {
        const reloadKey = 'async-error-reload';
        const lastReload = sessionStorage.getItem(reloadKey);
        const now = Date.now();
        if (!lastReload || now - parseInt(lastReload) >= 2000) {
          sessionStorage.setItem(reloadKey, now.toString());
          window.location.reload();
        }
      }
      return newCount;
    });
  }, []);

  const handleClearError = useCallback(() => {
    setReloadCount(0);
    sessionStorage.removeItem('async-error-reload');
  }, []);

  const isInfiniteLoop = reloadCount >= 2;

  return (
    <ErrorBoundary
      fallback={
        isInfiniteLoop ? (
          <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 max-w-md">
              <AlertTriangle className="h-12 w-12 text-amber-600 mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-amber-900 mb-2">
                Service temporarily unavailable
              </h2>
              <p className="text-amber-700 mb-4">
                Unable to load data. Please try again later.
              </p>
              <Button
                onClick={handleClearError}
                variant="outline"
                className="bg-white hover:bg-amber-50"
              >
                Clear and Continue
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 max-w-md">
              <AlertTriangle className="h-12 w-12 text-amber-600 mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-amber-900 mb-2">
                Service temporarily unavailable
              </h2>
              <p className="text-amber-700 mb-4">
                Unable to load data. The service may be experiencing issues.
              </p>
              <Button
                onClick={handleRetry}
                variant="outline"
                className="bg-white hover:bg-amber-50"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Try Again
              </Button>
            </div>
          </div>
        )
      }
    >
      {loader ? (
        <div className="animate-pulse">
          {loader}
        </div>
      ) : null}
      {children}
    </ErrorBoundary>
  );
}
