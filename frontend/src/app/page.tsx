'use client';

import Image from 'next/image';
import { useState, useRef } from 'react';

export default function Home() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [messages, setMessages] = useState<{ user: string; assistant: string; audio?: string }[]>([]);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = async () => {
        setIsProcessing(true); // Start loading animation
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.wav');

        try {
          const response = await fetch('http://localhost:8000/process-audio', {
            method: 'POST',
            body: formData,
          });
          const data = await response.json();

          if (data.error) {
            console.error('Backend error:', data.error);
            setIsProcessing(false); // Stop loading animation
            return;
          }

          setMessages((prev) => [
            ...prev,
            { user: data.user_text, assistant: data.response_text, audio: data.audio },
          ]);

          if (data.audio) {
            try {
              // Decode hex to binary
              const binaryString = Buffer.from(data.audio, 'hex').toString('binary');
              const audioData = new Uint8Array(binaryString.length);
              for (let i = 0; i < binaryString.length; i++) {
                audioData[i] = binaryString.charCodeAt(i);
              }
              const audioBlob = new Blob([audioData], { type: 'audio/wav' });
              const audioUrl = URL.createObjectURL(audioBlob);
              const audio = new Audio(audioUrl);
              audio.play().catch((e) => console.error('Audio playback error:', e));
            } catch (e) {
              console.error('Error decoding audio data:', e, 'Audio data:', data.audio);
            }
          } else {
            console.error('No audio data in response');
          }
        } catch (error) {
          console.error('Error sending audio:', error);
        } finally {
          setIsProcessing(false); // Stop loading animation
        }
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
    } catch (error) {
      console.error('Error starting recording:', error);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-4 bg-gray-100">
      <div className="w-full max-w-2xl bg-white rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold mb-4 text-center">Voice Assistant</h1>
        <div className="flex justify-center mb-4">
          <button
            onClick={isRecording ? stopRecording : startRecording}
            className={`p-4 rounded-full ${isRecording ? 'bg-red-500' : 'bg-blue-500'} hover:${isRecording ? 'bg-red-600' : 'bg-blue-600'}`}
            disabled={isProcessing}
          >
            <Image
              src={isRecording ? '/stop.svg' : '/mic.svg'}
              alt={isRecording ? 'Stop' : 'Record'}
              width={24}
              height={24}
            />
          </button>
        </div>
        {isProcessing && (
          <div className="flex justify-center mb-4">
            <div className="loader ease-linear rounded-full border-4 border-t-4 border-gray-200 h-12 w-12"></div>
          </div>
        )}
        <div className="space-y-4">
          {messages.map((msg, index) => (
            <div key={index} className="border-t pt-2">
              <p><strong>You:</strong> {msg.user}</p>
              <p><strong>Assistant:</strong> {msg.assistant}</p>
            </div>
          ))}
        </div>
      </div>
      <style jsx>{`
        .loader {
          border-top-color: #3498db;
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </main>
  );
}