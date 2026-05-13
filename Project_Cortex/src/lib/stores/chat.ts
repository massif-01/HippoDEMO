import { writable } from 'svelte/store';

export interface FileAttachment {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadFileId?: string; // ID from Dify after upload
  status: 'pending' | 'uploading' | 'uploaded' | 'error';
  error?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  context?: string;
  files?: FileAttachment[];
  conversationId?: string;
  messageId?: string;
}

export interface PromptSuggestion {
  id: string;
  text: string;
}

export interface RecordingContext {
  id: string;
  content: string;
  timestamp: Date;
  selected: boolean;
}

export const messages = writable<Message[]>([]);
export const promptSuggestions = writable<PromptSuggestion[]>([]);
export const promptSuggestionsLoading = writable<boolean>(false);
export const userContext = writable<string>('');
export const recordingContexts = writable<RecordingContext[]>([]);
export const currentConversationId = writable<string | null>(null);
export const pendingFiles = writable<FileAttachment[]>([]);
