import React, { useState } from 'react';
import { Info } from 'lucide-react';
import { INFO_TOPICS } from '../../services/infoRegistry';
import { InfoModal } from './InfoModal';

interface InfoButtonProps {
  topicKey: keyof typeof INFO_TOPICS | string;
  className?: string;
  size?: 'sm' | 'md';
}

export const InfoButton: React.FC<InfoButtonProps> = ({ topicKey, className = '', size = 'sm' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const topic = INFO_TOPICS[topicKey];

  if (!topic) return null;

  const iconSize = size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4';

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(true);
        }}
        className={`inline-flex items-center justify-center rounded-full text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 p-1 ${className}`}
        title={`Learn more about ${topic.title}`}
        aria-label={`Information on ${topic.title}`}
      >
        <Info className={iconSize} />
      </button>

      <InfoModal topic={topic} isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
};
