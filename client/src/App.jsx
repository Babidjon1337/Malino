import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { useLaunchParams } from "@telegram-apps/sdk-react";
import HomePage from "./components/HomePage";
import ResultPage from "./components/ResultPage";

import "./index.css";

function App() {
  const launchParams = useLaunchParams();
  console.log("Launch params:", launchParams);

  return (
    <Router>
      <div className="app">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route
            path="/result"
            element={<ResultPage launchParams={launchParams} />}
          />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
