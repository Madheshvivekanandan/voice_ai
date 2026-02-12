import { useRef, useState } from "react";

const WS_URL = "ws://localhost:8000/ws/audio";
const SAMPLE_RATE = 16000; // 🔥 Best for browser testing

function App() {
  const [status, setStatus] = useState("Disconnected");
  const [log, setLog] = useState([]);

  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micStreamRef = useRef(null);
  const processorRef = useRef(null);

  const addLog = (msg) => {
    setLog((prev) => [
      ...prev,
      `${new Date().toLocaleTimeString()} — ${msg}`,
    ]);
  };

  // ===============================
  // CONNECT WEBSOCKET
  // ===============================
  const handleConnect = () => {
    if (wsRef.current) wsRef.current.close();

    setStatus("Connecting...");
    setLog([]);

    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    audioCtxRef.current = new (window.AudioContext ||
      window.webkitAudioContext)({
      sampleRate: SAMPLE_RATE,
    });

    ws.onopen = () => {
      setStatus("Connected");
      addLog("WebSocket connected");
    };

    // ===============================
    // RECEIVE PCM16 AUDIO
    // ===============================
    ws.onmessage = (event) => {
      if (!(event.data instanceof ArrayBuffer)) return;

      const audioCtx = audioCtxRef.current;
      if (!audioCtx) return;

      const pcmData = new Int16Array(event.data);
      const floatData = new Float32Array(pcmData.length);

      for (let i = 0; i < pcmData.length; i++) {
        floatData[i] = pcmData[i] / 32768;
      }

      const buffer = audioCtx.createBuffer(
        1,
        floatData.length,
        SAMPLE_RATE
      );

      buffer.copyToChannel(floatData, 0);

      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      source.connect(audioCtx.destination);
      source.start();

      addLog(`Playing chunk (${event.data.byteLength} bytes)`);
    };

    ws.onclose = () => {
      setStatus("Disconnected");
      addLog("WebSocket closed");
      stopMic();
    };

    ws.onerror = () => {
      addLog("WebSocket error");
    };
  };

  // ===============================
  // START MICROPHONE STREAMING
  // ===============================
  const startMic = async () => {
    if (!audioCtxRef.current) return;

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: SAMPLE_RATE,
        channelCount: 1,
      },
    });

    micStreamRef.current = stream;

    const source =
      audioCtxRef.current.createMediaStreamSource(stream);

    const processor =
      audioCtxRef.current.createScriptProcessor(1024, 1, 1);

    processorRef.current = processor;

    source.connect(processor);
    processor.connect(audioCtxRef.current.destination);

    processor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0);

      const pcmBuffer = new ArrayBuffer(inputData.length * 2);
      const view = new DataView(pcmBuffer);

      for (let i = 0; i < inputData.length; i++) {
        let s = Math.max(-1, Math.min(1, inputData[i]));
        view.setInt16(i * 2, s * 32767, true);
      }

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(pcmBuffer);
      }
    };

    addLog("Microphone streaming (PCM 16kHz)");
  };

  // ===============================
  // STOP MICROPHONE
  // ===============================
  const stopMic = () => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (micStreamRef.current) {
      micStreamRef.current
        .getTracks()
        .forEach((track) => track.stop());
      micStreamRef.current = null;
    }

    addLog("Microphone stopped");
  };

  const handleDisconnect = () => {
    stopMic();
    if (wsRef.current) wsRef.current.close();
  };

  return (
    <div
      style={{
        padding: 32,
        fontFamily: "monospace",
        maxWidth: 700,
      }}
    >
      <h2>Voice AI Browser Tester (16kHz PCM)</h2>

      <p>
        Status: <strong>{status}</strong>
      </p>

      <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
        <button
          onClick={handleConnect}
          disabled={status === "Connected"}
        >
          Connect
        </button>

        <button
          onClick={startMic}
          disabled={status !== "Connected"}
        >
          Start Talking
        </button>

        <button onClick={handleDisconnect}>
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
        {log.map((entry, i) => (
          <div key={i}>{entry}</div>
        ))}
      </div>
    </div>
  );
}

export default App;
