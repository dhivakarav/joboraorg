import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info?.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center p-8 bg-surface">
          <div className="card p-8 max-w-md w-full space-y-4 text-center">
            <h1 className="text-xl font-bold text-ink">Something went wrong</h1>
            <p className="text-sm text-muted">
              An unexpected error occurred. Refreshing the page usually fixes this.
            </p>
            <p className="text-xs text-muted font-mono break-all">
              {this.state.error?.message || "Unknown error"}
            </p>
            <button
              className="btn-primary w-full"
              onClick={() => window.location.reload()}>
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
