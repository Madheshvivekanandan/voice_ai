import { useState, useRef, useCallback } from "react";

const WS_URL = "ws://localhost:8000/ws/audio";

function App() {
  const [status, setStatus] = useState("Disconnected");
  const [log, setLog] = useState([]);
  const wsRef = useRef(null);
  const chunksRef = useRef([]);

  const addLog = useCallback((msg) => {
    setLog((prev) => [...prev, `${new Date().toLocaleTimeString()} — ${msg}`]);
  }, []);

  const handleConnect = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setStatus("Connecting…");
    setLog([]);
    chunksRef.current = [];

    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("Connected");
      addLog("WebSocket connected");
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        const size = event.data.byteLength;
        chunksRef.current.push(event.data);
        addLog(`Received audio chunk: ${size} bytes`);
      }
    };

    ws.onerror = (err) => {
      addLog(`Error: ${err.message || "WebSocket error"}`);
    };

    ws.onclose = () => {
      setStatus("Disconnected");
      addLog("WebSocket closed");
    };
  };

  const handlePlay = () => {
    const chunks = chunksRef.current;
    if (chunks.length === 0) {
      addLog("No audio data to play");
      return;
    }

    const totalLength = chunks.reduce((sum, c) => sum + c.byteLength, 0);
    addLog(`Playing ${chunks.length} chunks (${totalLength} bytes)`);

    const sampleRate = 16000;
    const numSamples = totalLength / 2;

    const wavHeader = new ArrayBuffer(44);
    const view = new DataView(wavHeader);
    const writeStr = (offset, str) => {
      for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
    };

    writeStr(0, "RIFF");
    view.setUint32(4, 36 + totalLength, true);
    writeStr(8, "WAVE");
    writeStr(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(36, "data");
    view.setUint32(40, totalLength, true);

    const blob = new Blob([wavHeader, ...chunks], { type: "audio/wav" });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    audio.play().catch((e) => addLog(`Playback error: ${e.message}`));
  };

  const handleDisconnect = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  };

  return (
    <div style={{ padding: 32, fontFamily: "monospace", maxWidth: 600 }}>
      <h2>WS Audio Tester</h2>
      <p>
        Status: <strong>{status}</strong>
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button onClick={handleConnect} disabled={status === "Connected"}>
          Connect
        </button>
        <button onClick={handlePlay} disabled={chunksRef.current?.length === 0}>
          Play Audio
        </button>
        <button onClick={handleDisconnect} disabled={status === "Disconnected"}>
          Disconnect
        </button>
      </div>

      <div
        style={{
          background: "#111",
          color: "#0f0",
          padding: 12,
          borderRadius: 4,
          height: 300,
          overflowY: "auto",
          fontSize: 13,
        }}
      >
        {log.length === 0 ? (
          <span style={{ color: "#555" }}>Logs will appear here…</span>
        ) : (
          log.map((entry, i) => <div key={i}>{entry}</div>)
        )}
      </div>
    </div>
  );
}

export default App;
