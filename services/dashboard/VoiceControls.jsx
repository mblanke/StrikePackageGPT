/**
 * VoiceControls Component
 * Microphone button with hotkey support for voice commands
 * Visual feedback for listening, processing, and speaking states
 */

import React, { useState, useEffect, useRef } from 'react';

const VoiceControls = ({ onCommand, hotkey = ' ' }) => {
  const [state, setState] = useState('idle'); // idle, listening, processing, speaking
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState(null);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const hotkeyPressedRef = useRef(false);

  useEffect(() => {
    // Check if browser supports MediaRecorder
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError('Voice control not supported in this browser');
      return;
    }

    // Request microphone permission
    requestMicrophonePermission();

    // Setup hotkey listener
    const handleKeyDown = (e) => {
      if (e.key === hotkey && !hotkeyPressedRef.current && state === 'idle') {
        hotkeyPressedRef.current = true;
        startListening();
      }
    };

    const handleKeyUp = (e) => {
      if (e.key === hotkey && hotkeyPressedRef.current) {
        hotkeyPressedRef.current = false;
        if (state === 'listening') {
          stopListening();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      if (mediaRecorderRef.current && state === 'listening') {
        mediaRecorderRef.current.stop();
      }
    };
  }, [hotkey, state]);

  const requestMicrophonePermission = async () => {
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      setPermissionGranted(true);
    } catch (err) {
      setError('Microphone permission denied');
      setPermissionGranted(false);
    }
  };

  const startListening = async () => {
    if (!permissionGranted) {
      await requestMicrophonePermission();
      if (!permissionGranted) return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await processAudio(audioBlob);
        
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setState('listening');
      setTranscript('');
      setError(null);
    } catch (err) {
      console.error('Error starting recording:', err);
      setError('Failed to start recording: ' + err.message);
    }
  };

  const stopListening = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  const processAudio = async (audioBlob) => {
    setState('processing');
    
    try {
      // Send audio to backend for transcription
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');

      const response = await fetch('/api/voice/transcribe', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error('Transcription failed');
      }

      const data = await response.json();
      const transcribedText = data.text || '';
      
      setTranscript(transcribedText);

      if (transcribedText) {
        // Parse and route the voice command
        await routeCommand(transcribedText);
      } else {
        setError('No speech detected');
        setState('idle');
      }
    } catch (err) {
      console.error('Error processing audio:', err);
      setError('Failed to process audio: ' + err.message);
      setState('idle');
    }
  };

  const routeCommand = async (text) => {
    try {
      const response = await fetch('/api/voice/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });

      if (!response.ok) {
        throw new Error('Command routing failed');
      }

      const commandResult = await response.json();
      
      // Call parent callback with command result
      if (onCommand) {
        onCommand(commandResult);
      }

      // Check if TTS response is available
      if (commandResult.speak_response) {
        await speakResponse(commandResult.speak_response);
      } else {
        setState('idle');
      }
    } catch (err) {
      console.error('Error routing command:', err);
      setError('Failed to execute command: ' + err.message);
      setState('idle');
    }
  };

  const speakResponse = async (text) => {
    setState('speaking');

    try {
      // Try to get TTS audio from backend
      const response = await fetch('/api/voice/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });

      if (response.ok) {
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        
        audio.onended = () => {
          setState('idle');
          URL.revokeObjectURL(audioUrl);
        };

        audio.play();
      } else {
        // Fallback to browser TTS
        if ('speechSynthesis' in window) {
          const utterance = new SpeechSynthesisUtterance(text);
          utterance.onend = () => setState('idle');
          window.speechSynthesis.speak(utterance);
        } else {
          setState('idle');
        }
      }
    } catch (err) {
      console.error('Error speaking response:', err);
      setState('idle');
    }
  };

  const getStateColor = () => {
    switch (state) {
      case 'listening': return '#27AE60';
      case 'processing': return '#F39C12';
      case 'speaking': return '#3498DB';
      default: return '#95A5A6';
    }
  };

  const getStateIcon = () => {
    switch (state) {
      case 'listening': return '🎤';
      case 'processing': return '⏳';
      case 'speaking': return '🔊';
      default: return '🎙️';
    }
  };

  return (
    <div 
      className="voice-controls"
      style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: '10px'
      }}
    >
      {/* Transcript display */}
      {transcript && (
        <div 
          style={{
            backgroundColor: 'white',
            padding: '10px 15px',
            borderRadius: '8px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
            maxWidth: '300px',
            fontSize: '14px',
            color: '#333'
          }}
        >
          <strong>You said:</strong> {transcript}
        </div>
      )}

      {/* Error display */}
      {error && (
        <div 
          style={{
            backgroundColor: '#E74C3C',
            color: 'white',
            padding: '10px 15px',
            borderRadius: '8px',
            maxWidth: '300px',
            fontSize: '14px'
          }}
        >
          {error}
        </div>
      )}

      {/* Mic button */}
      <button
        onClick={state === 'idle' ? startListening : stopListening}
        disabled={state === 'processing' || state === 'speaking'}
        style={{
          width: '60px',
          height: '60px',
          borderRadius: '50%',
          border: 'none',
          backgroundColor: getStateColor(),
          color: 'white',
          fontSize: '24px',
          cursor: state === 'idle' || state === 'listening' ? 'pointer' : 'not-allowed',
          boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.3s ease',
          transform: state === 'listening' ? 'scale(1.1)' : 'scale(1)',
          opacity: state === 'processing' || state === 'speaking' ? 0.7 : 1
        }}
        title={`Voice command (hold ${hotkey === ' ' ? 'Space' : hotkey})`}
      >
        {getStateIcon()}
      </button>

      {/* Pulsing animation for listening state */}
      {state === 'listening' && (
        <div
          style={{
            position: 'absolute',
            bottom: '0',
            right: '0',
            width: '60px',
            height: '60px',
            borderRadius: '50%',
            border: '3px solid #27AE60',
            animation: 'pulse 1.5s infinite',
            pointerEvents: 'none'
          }}
        />
      )}

      {/* Hotkey hint */}
      <div
        style={{
          fontSize: '12px',
          color: '#666',
          textAlign: 'center'
        }}
      >
        Hold {hotkey === ' ' ? 'Space' : hotkey} to talk
      </div>

      <style>{`
        @keyframes pulse {
          0% {
            transform: scale(1);
            opacity: 1;
          }
          50% {
            transform: scale(1.3);
            opacity: 0.5;
          }
          100% {
            transform: scale(1.6);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
};

export default VoiceControls;
