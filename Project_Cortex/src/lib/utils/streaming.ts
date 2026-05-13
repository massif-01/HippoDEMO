import type { FileAttachment } from '$lib/stores/chat';

export interface StreamChunk {
  content?: string;
  thought?: string;
  done?: boolean;
  conversationId?: string;
  messageId?: string;
}

export interface DifyFile {
  type: string;
  transfer_method: string;
  upload_file_id?: string;
  url?: string;
}

// Shared abort controller for cancelling streams
let currentStreamController: AbortController | null = null;

// Reusable decoder - avoid creating new one for each stream
const sharedDecoder = new TextDecoder();

export function cancelCurrentStream() {
  if (currentStreamController) {
    currentStreamController.abort();
    currentStreamController = null;
  }
}

/**
 * Upload a file to Dify for use in chat conversations
 */
export async function uploadFileToDify(file: File): Promise<{ id: string; name: string; size: number; type: string }> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('user', 'default-user');
  
  const response = await fetch('http://localhost:8000/api/dify/files/upload', {
    method: 'POST',
    body: formData
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`File upload failed: ${errorText}`);
  }
  
  return response.json();
}

/**
 * Stream chat with Dify hippo_chat API
 */
export async function* streamDifyChat(
  query: string,
  options: {
    files?: FileAttachment[];
    conversationId?: string | null;
    context?: string;
  } = {}
): AsyncGenerator<StreamChunk> {
  // Cancel any existing stream
  cancelCurrentStream();
  currentStreamController = new AbortController();
  
  console.log('Streaming Dify chat:', { 
    queryLength: query.length,
    filesCount: options.files?.length || 0,
    conversationId: options.conversationId,
    hasContext: !!options.context
  });

  // Build query with context if available
  let fullQuery = query;
  if (options.context) {
    fullQuery = `Context:\n${options.context}\n\nUser Query:\n${query}`;
  }

  // Build files array for Dify
  const difyFiles: DifyFile[] = [];
  if (options.files) {
    for (const file of options.files) {
      if (file.uploadFileId && file.status === 'uploaded') {
        // Determine file type based on mime type
        let fileType = 'document';
        if (file.type.startsWith('image/')) {
          fileType = 'image';
        }
        
        difyFiles.push({
          type: fileType,
          transfer_method: 'local_file',
          upload_file_id: file.uploadFileId
        });
      }
    }
  }

  const requestBody: {
    query: string;
    conversation_id?: string;
    files?: DifyFile[];
    user: string;
    response_mode: string;
  } = {
    query: fullQuery,
    user: 'default-user',
    response_mode: 'streaming'
  };

  if (options.conversationId) {
    requestBody.conversation_id = options.conversationId;
  }

  if (difyFiles.length > 0) {
    requestBody.files = difyFiles;
  }

  const response = await fetch('http://localhost:8000/api/dify/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requestBody),
    signal: currentStreamController.signal
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('Dify chat error:', response.status, errorText);
    throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
  }

  const reader = response.body?.getReader();

  if (!reader) {
    throw new Error('Response body is not readable');
  }

  let buffer = '';
  const DATA_PREFIX = 'data: ';
  const DATA_PREFIX_LEN = DATA_PREFIX.length;

  try {
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) break;

      buffer += sharedDecoder.decode(value, { stream: true });
      
      // Process lines more efficiently
      let newlineIdx: number;
      while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, newlineIdx);
        buffer = buffer.slice(newlineIdx + 1);
        
        if (line.length > DATA_PREFIX_LEN && line.startsWith(DATA_PREFIX)) {
          const data = line.slice(DATA_PREFIX_LEN).trim();
          
          if (data === '[DONE]') {
            yield { done: true };
            return;
          }

          try {
            const chunk = JSON.parse(data);
            if (chunk.error) {
              throw new Error(chunk.error);
            }
            if (chunk.content) {
              yield { content: chunk.content };
            }
            if (chunk.thought) {
              yield { thought: chunk.thought };
            }
            if (chunk.done) {
              yield { 
                done: true, 
                conversationId: chunk.conversation_id,
                messageId: chunk.message_id
              };
              return;
            }
          } catch (e) {
            if (!(e instanceof SyntaxError)) {
              throw e;
            }
            // Silently ignore JSON parsing errors
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
    currentStreamController = null;
  }
}

/**
 * Legacy streaming chat function for direct OpenAI API calls
 * Kept for backwards compatibility
 */
export async function* streamChat(
  messages: Array<{ role: string; content: string }>,
  apiConfig: { endpoint: string; apiKey: string; model: string }
): AsyncGenerator<StreamChunk> {
  // Cancel any existing stream
  cancelCurrentStream();
  currentStreamController = new AbortController();
  
  console.log('Streaming chat with config:', { 
    endpoint: apiConfig.endpoint, 
    model: apiConfig.model,
    hasApiKey: !!apiConfig.apiKey 
  });

  const response = await fetch('http://localhost:8000/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages,
      model: apiConfig.model,
      api_key: apiConfig.apiKey,
      api_endpoint: apiConfig.endpoint,
      stream: true
    }),
    signal: currentStreamController.signal
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('Stream chat error:', response.status, errorText);
    throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
  }

  const reader = response.body?.getReader();

  if (!reader) {
    throw new Error('Response body is not readable');
  }

  let buffer = '';
  const DATA_PREFIX = 'data: ';
  const DATA_PREFIX_LEN = DATA_PREFIX.length;

  try {
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) break;

      buffer += sharedDecoder.decode(value, { stream: true });
      
      // Process lines more efficiently
      let newlineIdx: number;
      while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, newlineIdx);
        buffer = buffer.slice(newlineIdx + 1);
        
        if (line.length > DATA_PREFIX_LEN && line.startsWith(DATA_PREFIX)) {
          const data = line.slice(DATA_PREFIX_LEN).trim();
          
          if (data === '[DONE]') {
            yield { done: true };
            return;
          }

          try {
            const chunk = JSON.parse(data);
            if (chunk.error) {
              throw new Error(chunk.error);
            }
            if (chunk.content) {
              yield { content: chunk.content };
            }
          } catch (e) {
            if (!(e instanceof SyntaxError)) {
              throw e;
            }
            // Silently ignore JSON parsing errors
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
    currentStreamController = null;
  }
}
