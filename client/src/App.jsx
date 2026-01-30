import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { useLaunchParams } from "@telegram-apps/sdk-react";
import HomePage from "./components/HomePage";
import ResultPage from "./components/ResultPage";
import PaymentPage from "./components/PaymentPage"; // <--- 1. Импортируем компонент
import AdminPage from "./components/AdminDashboard";
import "./index.css";

function App() {
  const launchParams = useLaunchParams();
  console.log("Launch params:", launchParams);

  return (
    <Router>
      <div className="app">
        <Routes>
          <Route path="/home" element={<HomePage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route
            path="/result"
            element={<ResultPage launchParams={launchParams} />}
          />
          <Route path="/payment" element={<PaymentPage />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
