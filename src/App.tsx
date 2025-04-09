import { Routes, Route, useRoutes } from "react-router-dom";
import routes from "tempo-routes";
import Claude from "./components/Claude";

function Home() {
  return (
    <div
      style={{
        padding: "2rem",
        textAlign: "center",
        backgroundColor: "#f5f5f5",
        minHeight: "100vh",
      }}
    >
      <h1>Claude App</h1>
      <p>Meet your friendly AI assistant</p>
      <div style={{ marginTop: "2rem" }}>
        <Claude name="Claude" color="#6366f1" />
      </div>
    </div>
  );
}

function App() {
  // Use the useRoutes hook to render tempo routes
  const tempoRoutes = import.meta.env.VITE_TEMPO ? useRoutes(routes) : null;

  return (
    <div className="app">
      {/* For the tempo routes */}
      {tempoRoutes}

      <Routes>
        <Route path="/" element={<Home />} />

        {/* Add this before the catchall route */}
        {import.meta.env.VITE_TEMPO && (
          <Route path="/tempobook/*" element={null} />
        )}

        <Route path="*" element={<Home />} />
      </Routes>
    </div>
  );
}

export default App;
