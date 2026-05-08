import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import App from "./App.jsx";
import "./index.css";

// Apply theme as early as possible to avoid flash.
(() => {
  try {
    const saved = window.localStorage.getItem("nexus.ui-theme") || "dark";
    document.documentElement.classList.add(saved === "light" ? "light" : "dark");
  } catch {
    document.documentElement.classList.add("dark");
  }
})();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
      <Toaster
        position="bottom-right"
        toastOptions={{
          className:
            "!bg-nexus-surface !text-nexus-text !border !border-nexus-border !rounded-xl",
          style: { fontSize: "14px" },
        }}
      />
    </BrowserRouter>
  </React.StrictMode>
);
