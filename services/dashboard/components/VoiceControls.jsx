import React, { useState, useRef, useEffect } from 'react';

const VoiceControls = ({ onCommand = () => {}, apiUrl = '/api/voice' }) => {
  const [state, setState] = useState('idle'); // idle, listening, processing
  const [transcript, setTranscript] = useState('');
  const [hotkey, setHotkey] = useState('`'); // backtick
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const hotkeyPressedRef = useRef(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === hotkey && !hotkeyPressedRef.current && state === 'idle') {
        hotkeyPressedRef.current = true;
        startRecording();
      }
    };

    const handleKeyUp = (e) => {
      if (e.key === hotkey && hotkeyPressedRef.current) {
        hotkeyPressedRef.current = false;
        stopRecording();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [state, hotkey]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        await sendToTranscribe(audioBlob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorderRef.current.start();
      setState('listening');
      setTranscript('Listening...');
    } catch (error) {
      console.error('Microphone access denied:', error);
      setTranscript('Microphone access denied');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && state === 'listening') {
      mediaRecorderRef.current.stop();
      setState('processing');
      setTranscript('Processing...');
    }
  };

  const sendToTranscribe = async (audioBlob) => {
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.wav');

      const response = await fetch(`${apiUrl}/transcribe`, {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();
      setTranscript(result.text || 'No speech detected');
      setState('idle');

      if (result.text) {
        onCommand(result.text);
      }
    } catch (error) {
      console.error('Transcription failed:', error);
      setTranscript('Transcription failed');
      setState('idle');
    }
  };

  return (
    <div className="voice-controls p-4 bg-sp-grey rounded border border-sp-grey-mid">
      <div className="flex items-center gap-3">
        <button
          className={`voice-btn w-12 h-12 rounded-full flex items-center justify-center text-2xl transition ${
            state === 'listening'
              ? 'bg-sp-red animate-pulse'
              : state === 'processing'
              ? 'bg-yellow-500'
              : 'bg-sp-grey-mid hover:bg-sp-red'
          }`}
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          disabled={state === 'processing'}
        >
          {state === 'listening' ? '🎙️' : state === 'processing' ? '⏳' : '🎤'}
        </button>
        <div className="flex-1">
          <div className="text-sm text-sp-white-muted">
            {state === 'idle' && `Press & hold ${hotkey} or click to speak`}
            {state === 'listening' && 'Release to stop recording'}
            {state === 'processing' && 'Processing audio...'}
          </div>
          {transcript && (
            <div className="text-sm text-sp-white mt-1 font-mono">{transcript}</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default VoiceControls;
