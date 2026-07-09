import React from 'react';
import { motion } from 'framer-motion';
import { Cpu } from 'lucide-react';

export default function ReportCard({ title, agent, content, icon: Icon = Cpu }) {
  
  // A helper function to parse simple markdown to clean HTML
  const parseMarkdown = (text) => {
    if (!text) return '';
    
    // Split into lines
    const lines = text.split('\n');
    let inList = false;
    const parsedElements = [];

    lines.forEach((line, index) => {
      const trimmed = line.trim();
      
      // Handle Headings
      if (trimmed.startsWith('### ')) {
        if (inList) { parsedElements.push('</ul>'); inList = false; }
        parsedElements.push(`<h4 class="text-sm font-semibold text-white mt-4 mb-2 font-display">${trimmed.slice(4)}</h4>`);
      } else if (trimmed.startsWith('## ')) {
        if (inList) { parsedElements.push('</ul>'); inList = false; }
        parsedElements.push(`<h3 class="text-base font-bold text-purple-300 mt-5 mb-3 font-display border-b border-[#1a1a22] pb-1.5">${trimmed.slice(3)}</h3>`);
      } else if (trimmed.startsWith('# ')) {
        if (inList) { parsedElements.push('</ul>'); inList = false; }
        parsedElements.push(`<h2 class="text-lg font-extrabold text-white mt-6 mb-4 font-display">${trimmed.slice(2)}</h2>`);
      }
      
      // Handle List Items
      else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        if (!inList) {
          parsedElements.push('<ul class="list-disc list-inside space-y-1.5 my-3 text-gray-300 text-xs pl-2">');
          inList = true;
        }
        const itemContent = trimmed.slice(2);
        parsedElements.push(`<li class="leading-relaxed">${parseBoldAndItalic(itemContent)}</li>`);
      } 
      
      // Handle Empty Lines
      else if (trimmed === '') {
        if (inList) {
          parsedElements.push('</ul>');
          inList = false;
        }
      }
      
      // Handle Regular Paragraphs
      else {
        if (inList) { parsedElements.push('</ul>'); inList = false; }
        parsedElements.push(`<p class="text-xs text-gray-400 leading-relaxed mb-3">${parseBoldAndItalic(trimmed)}</p>`);
      }
    });

    if (inList) {
      parsedElements.push('</ul>');
    }

    return parsedElements.join('');
  };

  // Replace markdown bold (**text**) and bullet formats
  const parseBoldAndItalic = (text) => {
    let formatted = text
      .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
      .replace(/\*(.*?)\*/g, '<em class="text-gray-200">$1</em>');
    return formatted;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-6 h-full relative"
    >
      {/* Card Header */}
      <div className="flex items-center justify-between border-b border-[#1a1a22] pb-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <Icon className="w-4.5 h-4.5" />
          </div>
          <div>
            <h3 className="font-display font-semibold text-sm text-white tracking-wide">{title}</h3>
            <span className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">{agent}</span>
          </div>
        </div>
      </div>

      {/* Render Parsed Content */}
      <div 
        className="report-content prose prose-invert max-w-none"
        dangerouslySetInnerHTML={{ __html: parseMarkdown(content) }}
      />
    </motion.div>
  );
}
