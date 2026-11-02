import "@fontsource-variable/inter";
import "./index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "@/App";
import Login from "@/pages/Login";

// O servidor entrega a mesma casca em /login e em /app/...; a tela de entrada fica fora do roteador do app.
const isLogin = window.location.pathname === "/login";

createRoot(document.getElementById("root")!).render(<StrictMode>{isLogin ? <Login /> : <App />}</StrictMode>);
