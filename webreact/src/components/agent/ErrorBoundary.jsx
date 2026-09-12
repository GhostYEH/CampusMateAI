import { Component } from "react";

/**
 * Agent 工作台错误边界：捕获子组件渲染异常，显示友好错误摘要 + 重试。
 * 不暴露原始堆栈给用户。保留可访问性：role="alert" + 语义按钮。
 */
export default class AgentErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || "渲染异常" };
  }

  componentDidCatch(error, info) {
    if (typeof console !== "undefined") {
      console.warn("[agent:error-boundary]", error?.message || error, info?.componentStack || "");
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, message: "" });
    this.props.onRetry?.();
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="agent-error-boundary state-card error-state" role="alert" aria-live="assertive">
        <h3>该区域显示异常</h3>
        <p>{this.state.message}</p>
        <button className="button button-secondary" type="button" onClick={this.handleRetry}>
          重试
        </button>
      </div>
    );
  }
}