import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { init } from "@telegram-apps/sdk";

// Initialize Telegram SDK
init();

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
