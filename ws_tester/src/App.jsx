import { useRef, useState } from "react";

const WS_URL = "ws://localhost:8000/ws/audio";

function App() {
  const [status, setStatus] = useState("Disconnected");
  const [log, setLog] = useState([]);

  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micStreamRef = useRef(null);
  const processorRef = useRef(null);
  const silentGainRef = useRef(null);

  const addLog = (msg) => {
    setLog((prev) => [
      ...prev,
      `${new Date().toLocaleTimeString()} — ${msg}`,
    ]);
  };

  // ===============================
  // DOWNSAMPLE 48kHz → 16kHz
  // ===============================
  function downsampleBuffer(buffer, inputRate, outputRate) {
    if (outputRate === inputRate) return buffer;

    const sampleRateRatio = inputRate / outputRate;
    const newLength = Math.round(buffer.length / sampleRateRatio);
    const result = new Float32Array(newLength);

    let offsetResult = 0;
    let offsetBuffer = 0;

    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
      let accum = 0;
      let count = 0;

      for (
        let i = offsetBuffer;
        i < nextOffsetBuffer && i < buffer.length;
        i++
      ) {
        accum += buffer[i];
        count++;
      }

      result[offsetResult] = accum / count;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }

    return result;
  }

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

    const audioCtx = new (window.AudioContext ||
      window.webkitAudioContext)();
    audioCtxRef.current = audioCtx;

    addLog("Actual AudioContext sample rate: " + audioCtx.sampleRate);

    ws.onopen = () => {
      setStatus("Connected");
      addLog("WebSocket connected");
      startMic();
    };

    // ===============================
    // RECEIVE TTS AUDIO (16kHz PCM)
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
        16000
      );

      buffer.copyToChannel(floatData, 0);

      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      source.connect(audioCtx.destination);
      source.start();

      addLog(`Playing audio chunk (${event.data.byteLength} bytes)`);
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
  // START MICROPHONE (WITH RESAMPLING)
  // ===============================
  const startMic = async () => {
    try {
      const audioCtx = audioCtxRef.current;
      if (!audioCtx) return;

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      micStreamRef.current = stream;

      const source = audioCtx.createMediaStreamSource(stream);

      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      const silentGain = audioCtx.createGain();
      silentGain.gain.value = 0;
      silentGainRef.current = silentGain;

      source.connect(processor);
      processor.connect(silentGain);
      silentGain.connect(audioCtx.destination);

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);

        // 🔥 Downsample to 16kHz
        const downsampled = downsampleBuffer(
          inputData,
          audioCtx.sampleRate,
          16000
        );

        const pcmBuffer = new ArrayBuffer(downsampled.length * 2);
        const view = new DataView(pcmBuffer);

        for (let i = 0; i < downsampled.length; i++) {
          let s = Math.max(-1, Math.min(1, downsampled[i]));
          view.setInt16(i * 2, s * 32767, true);
        }

        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(pcmBuffer);
        }
      };

      addLog("Microphone streaming started (16kHz resampled)");
    } catch (err) {
      addLog("Microphone access denied");
      console.error(err);
    }
  };

  // ===============================
  // STOP MICROPHONE
  // ===============================
  const stopMic = () => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (silentGainRef.current) {
      silentGainRef.current.disconnect();
      silentGainRef.current = null;
    }

    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }

    addLog("Microphone stopped");
  };

  const handleDisconnect = () => {
    stopMic();

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }

    setStatus("Disconnected");
  };

  return (
    <div
      style={{
        padding: 32,
        fontFamily: "monospace",
        maxWidth: 700,
      }}
    >
      <h2>Voice AI Browser Tester</h2>

      <p>
        Status: <strong>{status}</strong>
      </p>

      <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
        <button onClick={handleConnect} disabled={status === "Connected"}>
          Connect
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
