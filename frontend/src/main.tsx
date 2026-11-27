import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./sheet.css";
import "./styles.css";
import "./theme.css";

import "@fontsource/alegreya-sans-sc/500.css";
import "@fontsource/alegreya-sans/400.css";
import "@fontsource/alegreya-sans/500.css";
import "@fontsource/alegreya-sans/700.css";
import "@fontsource/alegreya/400-italic.css";
// Alegreya (OFL) з власного сервера: кирилиця з ґ/ї/є без звернень до Google.
// Лише накреслення, які справді вживає theme.css; підмножини вантажаться за unicode-range.
import "@fontsource/alegreya/400.css";
import "@fontsource/alegreya/700.css";

const container = document.getElementById("root");
if (!container) throw new Error("Немає #root у index.html");

ReactDOM.createRoot(container).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
