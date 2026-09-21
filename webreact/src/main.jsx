import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./styles.css";
import "./styles/counselor-reference.css";
import "./styles/asset-pages.css";
import "./styles/home-classic.css";
import "./styles/floating-layout.css";
import "./styles/study-summer.css";
import "./styles/sylva-home.css";
import "./styles/button-effects.css";
import "./styles/learning-state.css";
import "./styles/prediction.css";
import "./styles/agent-workspaces.css";
import "./styles/agent-ops.css";
import "./styles/interactive-classroom.css";
import "./styles/magicclass-workbench.css";
import "./styles/magicclass-classroom.css";
import "./styles/learning-space.css";
// 必须最后引入：这是移植自参考项目的 Tailwind + 设计令牌层，只作用于
// `.maic-root` 作用域内。放最后可让工具类在与既有手写 CSS 的优先级打平时胜出。
import "./styles/maic.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
