import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, File, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { apiService } from '../api/api';

export default function Upload() {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  const [uploadState, setUploadState] = useState('idle'); // idle | uploading | processing | success | error
  const [logMessages, setLogMessages] = useState([]);
  const [errorMessage, setErrorMessage] = useState('');

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === "application/pdf") {
        setFile(droppedFile);
      } else {
        setErrorMessage("Only PDF pitch decks are accepted.");
        setUploadState('error');
      }
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.type === "application/pdf") {
        setFile(selectedFile);
      } else {
        setErrorMessage("Only PDF pitch decks are accepted.");
        setUploadState('error');
      }
    }
  };

  const startIngestion = async () => {
    if (!file) return;

    setErrorMessage('');
    setUploadState('uploading');
    setLogMessages(['Uploading document payload to backend server...']);

    try {
      // Simulate progress timeline for a more premium user experience
      setTimeout(() => {
        setLogMessages(prev => [...prev, 'Reading PDF layers and extracting semantic text segments...']);
        setUploadState('processing');
      }, 2000);

      setTimeout(() => {
        setLogMessages(prev => [...prev, 'Deploying LLM service to compile vector embeddings...']);
      }, 4000);

      setTimeout(() => {
        setLogMessages(prev => [...prev, 'Storing indexes in ChromaDB vector space...']);
      }, 6000);

      // Trigger the real backend API call
      const response = await apiService.uploadPitchDeck(file);

      // Add delay to align success state with logs
      setTimeout(() => {
        setLogMessages(prev => [...prev, `Ingestion complete! Context registered under source: ${response.filename}`]);
        setUploadState('success');
      }, 8000);

    } catch (err) {
      console.error(err);
      setErrorMessage(
        err.response?.data?.detail || 
        'VentureMind AI failed to index this pitch deck. Please check PDF content format.'
      );
      setUploadState('error');
    }
  };

  const resetUploader = () => {
    setFile(null);
    setUploadState('idle');
    setLogMessages([]);
    setErrorMessage('');
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-display font-extrabold text-white">Ingest Pitch Deck Context</h2>
        <p className="text-xs text-gray-500 mt-1">Upload a PDF pitch deck to embed its financials, founders, and goals into our AI RAG memory.</p>
      </div>

      <div className="glass-card p-8 bg-[#0c0c0e]/95 relative overflow-hidden">
        {/* Upload State Controller */}
        <AnimatePresence mode="wait">
          
          {/* 1. IDLE STATE */}
          {uploadState === 'idle' && (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center"
            >
              <div 
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                className={`w-full border-2 border-dashed rounded-2xl p-12 text-center flex flex-col items-center justify-center cursor-pointer transition-all duration-300 ${
                  dragActive 
                    ? 'border-purple-500 bg-purple-500/5' 
                    : 'border-[#1e1e24] bg-black/20 hover:bg-black/30 hover:border-purple-500/20'
                }`}
              >
                <input
                  type="file"
                  id="pitch-file"
                  className="hidden"
                  accept=".pdf"
                  onChange={handleFileInput}
                />
                
                <label htmlFor="pitch-file" className="cursor-pointer flex flex-col items-center">
                  <div className="p-4 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-400 mb-4 animate-bounce">
                    <UploadCloud className="w-8 h-8" />
                  </div>
                  <h3 className="font-display font-semibold text-white text-sm">Drag and drop your pitch deck</h3>
                  <p className="text-xs text-gray-500 mt-1">Accepts PDF format (Max 25MB)</p>
                  
                  <span className="mt-6 px-4 py-2 bg-gradient-to-r from-purple-950/40 to-indigo-950/20 border border-purple-500/30 text-purple-300 text-xs font-semibold rounded-lg hover:bg-purple-950/60 transition-all">
                    Choose File
                  </span>
                </label>
              </div>

              {file && (
                <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-6 w-full p-4 border border-purple-500/20 bg-purple-500/5 rounded-xl flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <File className="w-5 h-5 text-purple-400" />
                    <div className="text-left">
                      <p className="text-xs font-semibold text-white">{file.name}</p>
                      <p className="text-[10px] text-gray-500">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                  </div>
                  <button
                    onClick={startIngestion}
                    className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-medium transition-colors"
                  >
                    Ingest Deck
                  </button>
                </motion.div>
              )}
            </motion.div>
          )}

          {/* 2. INGESTING / PROCESSING STATES */}
          {(uploadState === 'uploading' || uploadState === 'processing') && (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="py-6 flex flex-col items-center justify-center text-center"
            >
              <Loader2 className="w-10 h-10 text-purple-500 animate-spin mb-4" />
              <h3 className="text-sm font-semibold text-white">RAG Embeddings Ingress in Progress</h3>
              <p className="text-[11px] text-gray-500 mt-0.5">Please wait, analyzing document layers...</p>
              
              {/* Stepper logs */}
              <div className="w-full bg-[#121216] border border-[#1e1e24] rounded-xl p-4 mt-8 font-mono text-[10px] text-left text-gray-400 space-y-2 h-44 overflow-y-auto">
                {logMessages.map((msg, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-purple-500 font-semibold">{`>`}</span>
                    <span className={i === logMessages.length - 1 ? "text-purple-300 font-semibold" : ""}>{msg}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* 3. SUCCESS STATE */}
          {uploadState === 'success' && (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="py-8 flex flex-col items-center justify-center text-center"
            >
              <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mb-4">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <h3 className="font-display font-extrabold text-white text-lg">Stored in AI Memory</h3>
              <p className="text-xs text-gray-400 max-w-sm mt-2 leading-relaxed">
                The pitch deck payload has been compiled into embeddings and registered inside ChromaDB. The agents will automatically load these context profiles on startup analysis.
              </p>

              <button
                onClick={resetUploader}
                className="mt-8 px-6 py-2.5 bg-black/40 border border-[#1c1c22] text-xs text-gray-300 hover:text-white rounded-lg hover:bg-black/60 transition-colors"
              >
                Ingest Another File
              </button>
            </motion.div>
          )}

          {/* 4. ERROR STATE */}
          {uploadState === 'error' && (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="py-8 flex flex-col items-center justify-center text-center"
            >
              <div className="w-16 h-16 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center mb-4 animate-pulse">
                <AlertCircle className="w-8 h-8" />
              </div>
              <h3 className="font-display font-extrabold text-white text-lg">Ingestion Failure</h3>
              <p className="text-xs text-rose-400 max-w-md mt-2 leading-relaxed">
                {errorMessage}
              </p>

              <button
                onClick={resetUploader}
                className="mt-8 px-6 py-2.5 bg-black/40 border border-[#1c1c22] text-xs text-gray-300 hover:text-white rounded-lg hover:bg-black/60 transition-colors"
              >
                Reset Uploader
              </button>
            </motion.div>
          )}

        </AnimatePresence>
      </div>
    </div>
  );
}
