import React from "react";

interface ClaudeProps {
  name?: string;
  color?: string;
}

const Claude = ({ name = "Claude", color = "#6366f1" }: ClaudeProps) => {
  return (
    <div
      style={{
        padding: "2rem",
        backgroundColor: "white",
        borderRadius: "8px",
        boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
        textAlign: "center",
        maxWidth: "400px",
        margin: "0 auto",
      }}
    >
      <div
        style={{
          width: "100px",
          height: "100px",
          borderRadius: "50%",
          backgroundColor: color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: "0 auto 1rem auto",
          color: "white",
          fontSize: "2rem",
          fontWeight: "bold",
        }}
      >
        {name.charAt(0)}
      </div>
      <h2 style={{ marginBottom: "0.5rem" }}>{name}</h2>
      <p style={{ color: "#666" }}>A friendly AI assistant</p>
    </div>
  );
};

export default Claude;
