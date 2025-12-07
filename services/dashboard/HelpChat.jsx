/**
 * HelpChat Component
 * Persistent side-panel chat with LLM-powered help
 * Context-aware and maintains conversation history
 */

import React, { useState, useEffect, useRef } from 'react';

const HelpChat = ({ 
  isOpen = false, 
  onClose, 
  currentPage = 'dashboard',
  context = {} 
}) => {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      // Add welcome message
      setMessages([{
        role: 'assistant',
        content: `👋 Hi! I'm your AI assistant for StrikePackageGPT. I can help you with:

• Understanding security tools and commands
• Interpreting scan results
• Writing nmap, nikto, and other tool commands
• Navigating the platform
• Security best practices

What would you like help with?`,
        timestamp: new Date()
      }]);
    }
  }, [isOpen]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async () => {
    if (!inputText.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: inputText,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsLoading(true);

    try {
      // Build context string
      const contextString = `User is on ${currentPage} page. ${JSON.stringify(context)}`;

      const response = await fetch('/api/llm/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: inputText,
          session_id: sessionId,
          context: contextString
        })
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const data = await response.json();
      const assistantMessage = {
        role: 'assistant',
        content: data.message || data.content || 'I apologize, I had trouble processing that request.',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '❌ Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
        isError: true
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      // Could show a toast notification here
      console.log('Copied to clipboard');
    });
  };

  const clearChat = () => {
    if (window.confirm('Clear all chat history?')) {
      setMessages([{
        role: 'assistant',
        content: 'Chat history cleared. How can I help you?',
        timestamp: new Date()
      }]);
    }
  };

  const renderMessage = (message, index) => {
    const isUser = message.role === 'user';
    const isError = message.isError;

    // Check if message contains code blocks
    const hasCode = message.content.includes('```');
    let renderedContent;

    if (hasCode) {
      // Simple code block rendering
      const parts = message.content.split(/(```[\s\S]*?```)/g);
      renderedContent = parts.map((part, i) => {
        if (part.startsWith('```')) {
          const code = part.slice(3, -3).trim();
          const [lang, ...codeLines] = code.split('\n');
          const codeText = codeLines.join('\n');
          
          return (
            <div key={i} style={{ 
              backgroundColor: '#f5f5f5', 
              padding: '10px',
              borderRadius: '4px',
              margin: '10px 0',
              position: 'relative',
              fontFamily: 'monospace',
              fontSize: '13px',
              overflowX: 'auto'
            }}>
              <div style={{ 
                fontSize: '11px', 
                color: '#666', 
                marginBottom: '5px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <span>{lang || 'code'}</span>
                <button 
                  onClick={() => copyToClipboard(codeText)}
                  style={{
                    padding: '4px 8px',
                    fontSize: '11px',
                    border: 'none',
                    backgroundColor: '#ddd',
                    borderRadius: '3px',
                    cursor: 'pointer'
                  }}
                >
                  📋 Copy
                </button>
              </div>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                <code>{codeText}</code>
              </pre>
            </div>
          );
        }
        return <div key={i} style={{ whiteSpace: 'pre-wrap' }}>{part}</div>;
      });
    } else {
      renderedContent = <div style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>;
    }

    return (
      <div
        key={index}
        style={{
          display: 'flex',
          justifyContent: isUser ? 'flex-end' : 'flex-start',
          marginBottom: '15px'
        }}
      >
        <div
          style={{
            maxWidth: '80%',
            padding: '12px 16px',
            borderRadius: '12px',
            backgroundColor: isError ? '#FCE4E4' : isUser ? '#3498DB' : '#ECF0F1',
            color: isError ? '#E74C3C' : isUser ? 'white' : '#2C3E50',
            fontSize: '14px',
            lineHeight: '1.5',
            boxShadow: '0 2px 5px rgba(0,0,0,0.1)'
          }}
        >
          {renderedContent}
          <div
            style={{
              fontSize: '11px',
              color: isUser ? 'rgba(255,255,255,0.7)' : '#95A5A6',
              marginTop: '5px',
              textAlign: 'right'
            }}
          >
            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>
    );
  };

  const quickActions = [
    { label: '📝 Write nmap command', prompt: 'How do I write an nmap command to scan a network?' },
    { label: '🔍 Interpret results', prompt: 'Help me understand these scan results' },
    { label: '🛠️ Use sqlmap', prompt: 'How do I use sqlmap to test for SQL injection?' },
    { label: '📊 Generate report', prompt: 'How do I generate a security assessment report?' }
  ];

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        right: 0,
        top: 0,
        bottom: 0,
        width: '400px',
        backgroundColor: 'white',
        boxShadow: '-4px 0 15px rgba(0,0,0,0.1)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 9998
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '20px',
          backgroundColor: '#3498DB',
          color: 'white',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '2px solid #2980B9'
        }}
      >
        <div>
          <h3 style={{ margin: '0 0 5px 0', fontSize: '18px' }}>💬 AI Assistant</h3>
          <div style={{ fontSize: '12px', opacity: 0.9 }}>
            Ask me anything about security testing
          </div>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={clearChat}
            style={{
              background: 'none',
              border: 'none',
              color: 'white',
              cursor: 'pointer',
              fontSize: '18px',
              padding: '5px'
            }}
            title="Clear chat"
          >
            🗑️
          </button>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'white',
              cursor: 'pointer',
              fontSize: '24px',
              padding: '0'
            }}
            title="Close"
          >
            ×
          </button>
        </div>
      </div>

      {/* Messages area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
          backgroundColor: '#FAFAFA'
        }}
      >
        {messages.map((message, index) => renderMessage(message, index))}
        
        {isLoading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#95A5A6' }}>
            <div>⏳</div>
            <div>Thinking...</div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Quick actions */}
      {messages.length <= 1 && (
        <div
          style={{
            padding: '15px',
            backgroundColor: '#F8F9FA',
            borderTop: '1px solid #ddd'
          }}
        >
          <div style={{ fontSize: '12px', color: '#666', marginBottom: '10px' }}>
            Quick actions:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {quickActions.map((action, i) => (
              <button
                key={i}
                onClick={() => {
                  setInputText(action.prompt);
                  inputRef.current?.focus();
                }}
                style={{
                  padding: '6px 12px',
                  fontSize: '12px',
                  border: '1px solid #ddd',
                  backgroundColor: 'white',
                  borderRadius: '16px',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = '#E8F4F8';
                  e.target.style.borderColor = '#3498DB';
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'white';
                  e.target.style.borderColor = '#ddd';
                }}
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div
        style={{
          padding: '15px',
          borderTop: '2px solid #ECF0F1',
          backgroundColor: 'white'
        }}
      >
        <div style={{ display: 'flex', gap: '10px' }}>
          <textarea
            ref={inputRef}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question... (Enter to send)"
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '8px',
              fontSize: '14px',
              resize: 'none',
              minHeight: '60px',
              maxHeight: '120px',
              fontFamily: 'inherit'
            }}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputText.trim() || isLoading}
            style={{
              padding: '10px 20px',
              border: 'none',
              backgroundColor: !inputText.trim() || isLoading ? '#95A5A6' : '#3498DB',
              color: 'white',
              borderRadius: '8px',
              cursor: !inputText.trim() || isLoading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            {isLoading ? '⏳' : '📤'}
          </button>
        </div>
        <div style={{ fontSize: '11px', color: '#95A5A6', marginTop: '8px' }}>
          Shift+Enter for new line
        </div>
      </div>
    </div>
  );
};

export default HelpChat;
