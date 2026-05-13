<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy, tick } from 'svelte';
  import { fade, scale, fly } from 'svelte/transition';
  import { cubicOut, backOut } from 'svelte/easing';
  import { browser } from '$app/environment';
  import { t } from '$lib/stores/i18n';
  import { summaryFeed } from '$lib/stores/summary';
  import { learnedSkills } from '$lib/stores/skills';
  import type { LearnedSkill } from '$lib/stores/skills';

  export let open = false;
  
  const dispatch = createEventDispatcher();
  
  // Hippo Agent API Configuration - Agent type app using chat-messages endpoint
  const HIPPO_API_URL = 'https://difyapp.aoseo.com/v1/chat-messages';
  const HIPPO_API_KEY = import.meta.env.VITE_DIFY_HIPPO_AGENT_KEY || '';
  const BACKEND_URL = 'http://localhost:8000';
  
  // State
  let inputValue = '';
  let inputElement: HTMLInputElement;
  let chatInputElement: HTMLInputElement;
  let chatContainerElement: HTMLDivElement;
  let conversationId: string | null = null;
  let userId: string = 'hippo-user-local';
  
  // File upload state
  interface UploadedFile {
    id: string;
    name: string;
    size: number;
    type: string;
    uploadFileId?: string; // ID from Dify upload
  }
  let uploadedFiles: UploadedFile[] = [];
  let fileInputElement: HTMLInputElement;
  let isUploadingFile = false;
  
  // Context state
  let currentContext: string | null = null;
  
  // Subscribe to summaryFeed for context
  $: currentContext = $summaryFeed?.insights || null;

  // Skill selection state
  let showSkillDropdown = false;
  let skillSearchQuery = '';
  let selectedSkill: LearnedSkill | null = null;
  let skillDropdownIndex = 0;

  $: availableSkills = $learnedSkills;
  $: filteredSkills = skillSearchQuery
    ? availableSkills.filter(s => s.name.toLowerCase().includes(skillSearchQuery.toLowerCase()))
    : availableSkills;

  function detectSkillTrigger(value: string) {
    const atIndex = value.lastIndexOf('@');
    if (atIndex === -1) {
      showSkillDropdown = false;
      skillSearchQuery = '';
      return;
    }
    const afterAt = value.substring(atIndex + 1);
    if (afterAt.includes(' ') && showSkillDropdown) {
      showSkillDropdown = false;
      skillSearchQuery = '';
      return;
    }
    if (!afterAt.includes(' ')) {
      showSkillDropdown = true;
      skillSearchQuery = afterAt;
      skillDropdownIndex = 0;
    }
  }

  function selectSkill(skill: LearnedSkill) {
    selectedSkill = skill;
    const atIndex = inputValue.lastIndexOf('@');
    if (atIndex !== -1) {
      inputValue = inputValue.substring(0, atIndex) + `@${skill.name} `;
    } else {
      inputValue += `@${skill.name} `;
    }
    showSkillDropdown = false;
    skillSearchQuery = '';
  }

  function removeSelectedSkill() {
    if (!selectedSkill) return;
    inputValue = inputValue.replace(`@${selectedSkill.name}`, '').trim();
    selectedSkill = null;
  }

  $: detectSkillTrigger(inputValue);
  
  // Agent step state (tool calls & intermediate process)
  interface AgentStep {
    id: string;
    position: number;
    thought: string;
    tool: string;
    toolInput: string;
    observation: string;
    status: 'thinking' | 'calling' | 'done';
  }

  // Chat state
  interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    isStreaming?: boolean;
    agentSteps?: AgentStep[];
  }
  
  let messages: ChatMessage[] = [];
  let isStreaming = false;
  let streamingError: string | null = null;
  let abortController: AbortController | null = null;
  let hasStartedChat = false;
  let expandedSteps: Set<string> = new Set();

  function toggleStep(stepId: string) {
    if (expandedSteps.has(stepId)) {
      expandedSteps.delete(stepId);
    } else {
      expandedSteps.add(stepId);
    }
    expandedSteps = expandedSteps; // trigger reactivity
  }
  
  // Note: conversation_id should be empty string for new conversation
  // Dify will return the actual conversation_id in its response
  
  // Check if query mentions context
  function queryMentionsContext(query: string): boolean {
    const contextKeywords = ['上下文', 'context', '背景', '刚才的', '之前的', '录音', 'recording'];
    const lowerQuery = query.toLowerCase();
    return contextKeywords.some(keyword => lowerQuery.includes(keyword.toLowerCase()));
  }
  
  // Upload file to backend/Dify
  async function uploadFile(file: File): Promise<UploadedFile | null> {
    try {
      isUploadingFile = true;
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user', userId);
      
      const response = await fetch(`${BACKEND_URL}/api/dify/files/upload`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('File upload failed:', errorText);
        throw new Error(`Upload failed: ${response.status}`);
      }
      
      const result = await response.json();
      console.log('%c[File Upload] Success', 'color: #10b981; font-weight: bold', result);
      
      return {
        id: crypto.randomUUID(),
        name: result.name || file.name,
        size: result.size || file.size,
        type: result.type || file.type,
        uploadFileId: result.id
      };
    } catch (error) {
      console.error('Error uploading file:', error);
      return null;
    } finally {
      isUploadingFile = false;
    }
  }
  
  // Handle file selection
  async function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    
    for (const file of Array.from(input.files)) {
      const uploaded = await uploadFile(file);
      if (uploaded) {
        uploadedFiles = [...uploadedFiles, uploaded];
      }
    }
    
    // Reset input
    input.value = '';
  }
  
  // Remove uploaded file
  function removeFile(fileId: string) {
    uploadedFiles = uploadedFiles.filter(f => f.id !== fileId);
  }
  
  // Open file picker
  function openFilePicker() {
    fileInputElement?.click();
  }
  
  // Format file size
  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  
  // Reset state when closing
  function resetState() {
    messages = [];
    conversationId = null;
    hasStartedChat = false;
    inputValue = '';
    isStreaming = false;
    streamingError = null;
    uploadedFiles = [];
    selectedSkill = null;
    showSkillDropdown = false;
    skillSearchQuery = '';
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
  }
  
  // Close the palette
  function close() {
    open = false;
    resetState();
    dispatch('close');
  }
  
  // Handle keyboard shortcuts
  function handleGlobalKeydown(event: KeyboardEvent) {
    // Cmd/Ctrl + K to toggle
    if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
      event.preventDefault();
      if (!open) {
        open = true;
        // Start with null - Dify will return actual conversation_id
        conversationId = null;
        setTimeout(() => inputElement?.focus(), 50);
      } else {
        close();
      }
    }
    
    // Escape to close
    if (event.key === 'Escape' && open) {
      event.preventDefault();
      close();
    }
  }
  
  // Handle input keydown
  function handleInputKeydown(event: KeyboardEvent) {
    if (showSkillDropdown && filteredSkills.length > 0) {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        skillDropdownIndex = Math.min(skillDropdownIndex + 1, filteredSkills.length - 1);
        return;
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        skillDropdownIndex = Math.max(skillDropdownIndex - 1, 0);
        return;
      }
      if (event.key === 'Enter' || event.key === 'Tab') {
        event.preventDefault();
        selectSkill(filteredSkills[skillDropdownIndex]);
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        showSkillDropdown = false;
        return;
      }
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }
  
  // Parse SSE data
  function parseSSEData(data: string): any {
    try {
      return JSON.parse(data);
    } catch {
      return null;
    }
  }
  
  // Send message to Hippo Agent
  async function sendMessage() {
    const query = inputValue.trim();
    if (!query || isStreaming) return;
    
    // Start chat mode
    if (!hasStartedChat) {
      hasStartedChat = true;
    }
    
    // Add user message
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
      timestamp: new Date()
    };
    messages = [...messages, userMessage];
    inputValue = '';
    
    // Scroll to bottom
    await tick();
    scrollToBottom();
    
    // Focus the chat input after first message
    setTimeout(() => {
      chatInputElement?.focus();
    }, 100);
    
    // Create assistant message placeholder
    const assistantMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
      agentSteps: []
    };
    messages = [...messages, assistantMessage];
    
    isStreaming = true;
    streamingError = null;
    abortController = new AbortController();
    
    const includeContext = queryMentionsContext(query) && currentContext;
    const attachedSkill = selectedSkill;

    // Strip @skillName from the user-visible query for the API
    let cleanQuery = query;
    if (attachedSkill) {
      cleanQuery = query.replace(`@${attachedSkill.name}`, '').trim();
    }

    const skillInput = attachedSkill?.content || '';
    const contextInput = includeContext ? (currentContext || '') : '';

    if (attachedSkill) {
      console.log('%c[Skill] Passing skill as input:', 'color: #10b981; font-weight: bold', attachedSkill.name);
    }
    if (includeContext) {
      console.log('%c[Context] Passing recording context as input', 'color: #8b5cf6; font-weight: bold');
    }

    // Build files array for request
    const files = uploadedFiles
      .filter(f => f.uploadFileId)
      .map(f => ({
        type: f.type.startsWith('image/') ? 'image' : 'document',
        transfer_method: 'local_file',
        upload_file_id: f.uploadFileId
      }));
    
    // Build request payload — skill and context passed as separate inputs
    const requestPayload = {
      inputs: {
        skill: skillInput,
        context: contextInput
      },
      query: cleanQuery,
      response_mode: 'streaming',
      conversation_id: conversationId || '',
      user: userId,
      files: files
    };
    
    // Clear uploaded files after sending
    if (files.length > 0) {
      console.log('%c[Files] Including files in request', 'color: #f59e0b; font-weight: bold', files);
      uploadedFiles = [];
    }
    
    // Log request details
    console.log('%c[Hippo Agent] API Request', 'color: #3b82f6; font-weight: bold');
    console.log('URL:', HIPPO_API_URL);
    console.log('API Key:', HIPPO_API_KEY.slice(0, 10) + '...');
    console.log('Payload:', JSON.stringify(requestPayload, null, 2));
    console.log('Timestamp:', new Date().toISOString());
    
    try {
      // Call Hippo Agent API directly
      const response = await fetch(HIPPO_API_URL, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${HIPPO_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestPayload),
        signal: abortController.signal
      });
      
      // Log response status
      console.log('%c[Hippo Agent] Response Status', 'color: #10b981; font-weight: bold');
      console.log('Status:', response.status, response.statusText);
      console.log('Headers:', Object.fromEntries(response.headers.entries()));
      
      if (!response.ok) {
        // Try to get error details from response body
        let errorBody = '';
        try {
          errorBody = await response.text();
          console.error('%c[Hippo Agent] Error Response Body', 'color: #ef4444; font-weight: bold');
          console.error(errorBody);
        } catch (e) {
          console.error('Could not read error response body');
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}${errorBody ? ` - ${errorBody}` : ''}`);
      }
      
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }
      
      const decoder = new TextDecoder();
      let buffer = '';
      let fullContent = '';
      let eventCount = 0;
      
      console.log('%c[Hippo Agent] Starting SSE Stream', 'color: #8b5cf6; font-weight: bold');
      
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          console.log('%c[Hippo Agent] Stream Complete', 'color: #10b981; font-weight: bold');
          console.log('Total events received:', eventCount);
          console.log('Total content length:', fullContent.length);
          break;
        }
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            
            if (data === '[DONE]') {
              console.log('%c[Hippo Agent] Received [DONE]', 'color: #6b7280');
              continue;
            }
            
            const parsed = parseSSEData(data);
            if (!parsed) {
              console.warn('%c[Hippo Agent] Failed to parse SSE data:', 'color: #f59e0b', data);
              continue;
            }
            
            eventCount++;
            
            // Log each event type (throttled for message events)
            if (parsed.event !== 'message' && parsed.event !== 'agent_message') {
              console.log(`%c[Hippo Agent] Event: ${parsed.event}`, 'color: #8b5cf6', parsed);
            }
            
            // Handle different event types from Dify
            if (parsed.event === 'message' || parsed.event === 'agent_message') {
              const answer = parsed.answer || '';
              fullContent += answer;
              
              // Update conversation_id if returned
              if (parsed.conversation_id && !conversationId) {
                conversationId = parsed.conversation_id;
                console.log('%c[Hippo Agent] Conversation ID set:', 'color: #10b981', conversationId);
              }
              
              // Update the streaming message
              messages = messages.map(m => 
                m.id === assistantMessage.id 
                  ? { ...m, content: fullContent }
                  : m
              );
              
              await tick();
              scrollToBottom();
            } else if (parsed.event === 'message_end') {
              // Update conversation_id from message_end event
              if (parsed.conversation_id) {
                conversationId = parsed.conversation_id;
              }
              console.log('%c[Hippo Agent] Message End', 'color: #10b981', {
                conversation_id: parsed.conversation_id,
                message_id: parsed.message_id,
                metadata: parsed.metadata
              });
            } else if (parsed.event === 'error') {
              console.error('%c[Hippo Agent] Error Event', 'color: #ef4444; font-weight: bold', parsed);
              throw new Error(parsed.message || 'Unknown error from Dify');
            } else if (parsed.event === 'agent_thought') {
              const stepId = parsed.id || `step-${parsed.position}`;
              const toolName = parsed.tool || '';
              const toolInput = parsed.tool_input || '';
              const observation = parsed.observation || '';
              const thought = parsed.thought || '';

              // Dify sends multiple agent_thought events for the same id,
              // progressively filling in tool → observation → thought
              const currentSteps = messages.find(m => m.id === assistantMessage.id)?.agentSteps || [];
              const existingIdx = currentSteps.findIndex(s => s.id === stepId);

              let status: 'thinking' | 'calling' | 'done' = 'thinking';
              if (toolName && !observation) status = 'calling';
              else if (observation || thought) status = 'done';

              const stepData: AgentStep = {
                id: stepId,
                position: parsed.position || 0,
                thought: thought,
                tool: toolName,
                toolInput: toolInput,
                observation: observation,
                status
              };

              let updatedSteps: AgentStep[];
              if (existingIdx >= 0) {
                updatedSteps = [...currentSteps];
                // Merge: keep non-empty values from either old or new
                updatedSteps[existingIdx] = {
                  ...updatedSteps[existingIdx],
                  ...Object.fromEntries(Object.entries(stepData).filter(([_, v]) => v !== '' && v !== 0))
                };
              } else {
                updatedSteps = [...currentSteps, stepData];
              }

              messages = messages.map(m =>
                m.id === assistantMessage.id
                  ? { ...m, agentSteps: updatedSteps }
                  : m
              );

              await tick();
              scrollToBottom();

              console.log('%c[Hippo Agent] Agent Thought', 'color: #f59e0b', { tool: toolName, status, position: parsed.position });
            } else if (parsed.event === 'tool_call') {
              console.log('%c[Hippo Agent] Tool Call', 'color: #ec4899', parsed);
            }
          }
        }
      }
      
      // Mark streaming as complete
      messages = messages.map(m => 
        m.id === assistantMessage.id 
          ? { ...m, isStreaming: false }
          : m
      );
      
      console.log('%c[Hippo Agent] Final Response', 'color: #10b981; font-weight: bold');
      console.log('Content preview:', fullContent.slice(0, 200) + (fullContent.length > 200 ? '...' : ''));
      
      // Check for completion phrases (optional auto-close)
      const completionPhrases = ['done', 'completed', 'here is your result', '完成', '已完成'];
      const lowerContent = fullContent.toLowerCase();
      const isCompleted = completionPhrases.some(phrase => lowerContent.includes(phrase));
      
      if (isCompleted) {
        dispatch('agentCompleted', { query, response: fullContent, conversationId });
      }
      
    } catch (error) {
      console.error('%c[Hippo Agent] Error', 'color: #ef4444; font-weight: bold');
      console.error('Error type:', error instanceof Error ? error.constructor.name : typeof error);
      console.error('Error message:', error instanceof Error ? error.message : String(error));
      if (error instanceof Error && error.stack) {
        console.error('Stack trace:', error.stack);
      }
      
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('%c[Hippo Agent] Stream aborted by user', 'color: #f59e0b');
        // User stopped the stream
        messages = messages.map(m => 
          m.id === assistantMessage.id 
            ? { ...m, isStreaming: false, content: m.content || $t.commandPalette?.agent?.stopped || 'Stopped' }
            : m
        );
      } else {
        streamingError = error instanceof Error ? error.message : 'Unknown error';
        // Remove the empty assistant message on error
        messages = messages.filter(m => m.id !== assistantMessage.id);
      }
    } finally {
      isStreaming = false;
      abortController = null;
      console.log('%c[Hippo Agent] Request finished', 'color: #6b7280');
    }
  }
  
  // Stop streaming
  function stopStreaming() {
    if (abortController) {
      abortController.abort();
    }
  }
  
  // Regenerate last response
  async function regenerate() {
    if (messages.length < 2) return;
    
    // Get the last user message
    const lastUserMessageIndex = messages.map(m => m.role).lastIndexOf('user');
    if (lastUserMessageIndex === -1) return;
    
    const lastUserMessage = messages[lastUserMessageIndex];
    
    // Remove all messages after and including the last assistant response
    messages = messages.slice(0, lastUserMessageIndex + 1);
    
    // Re-send the message
    inputValue = lastUserMessage.content;
    messages = messages.slice(0, lastUserMessageIndex);
    await sendMessage();
  }
  
  // Scroll chat to bottom
  function scrollToBottom() {
    if (chatContainerElement) {
      chatContainerElement.scrollTop = chatContainerElement.scrollHeight;
    }
  }
  
  // Format markdown content - Enhanced markdown renderer
  function formatMarkdown(text: string): string {
    if (!text) return '';
    
    // Store code blocks temporarily to prevent processing their content
    const codeBlocks: string[] = [];
    const inlineCodes: string[] = [];
    
    // Extract code blocks first (preserve them)
    let formatted = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const index = codeBlocks.length;
      const escapedCode = code.trim()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      codeBlocks.push(`<pre class="code-block"><div class="code-header"><span class="code-lang">${lang || 'text'}</span><button class="copy-code-btn" onclick="navigator.clipboard.writeText(this.parentElement.nextElementSibling.textContent)">Copy</button></div><code class="language-${lang || 'text'}">${escapedCode}</code></pre>`);
      return `__CODEBLOCK_${index}__`;
    });
    
    // Extract inline code
    formatted = formatted.replace(/`([^`]+)`/g, (_, code) => {
      const index = inlineCodes.length;
      const escapedCode = code
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      inlineCodes.push(`<code class="inline-code">${escapedCode}</code>`);
      return `__INLINECODE_${index}__`;
    });
    
    // Now escape HTML in the rest of the content
    formatted = formatted
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    
    // Horizontal rules
    formatted = formatted.replace(/^(-{3,}|_{3,}|\*{3,})$/gm, '<hr class="my-4 border-gray-300 dark:border-gray-600">');
    
    // Blockquotes
    formatted = formatted.replace(/^&gt;\s?(.*)$/gm, '<blockquote class="border-l-4 border-blue-400 pl-4 my-2 text-gray-600 dark:text-gray-400 italic">$1</blockquote>');
    
    // Headers (process in order from h6 to h1)
    formatted = formatted.replace(/^###### (.+)$/gm, '<h6 class="font-semibold text-xs mt-3 mb-1 text-gray-700 dark:text-gray-300">$1</h6>');
    formatted = formatted.replace(/^##### (.+)$/gm, '<h5 class="font-semibold text-xs mt-3 mb-1 text-gray-700 dark:text-gray-300">$1</h5>');
    formatted = formatted.replace(/^#### (.+)$/gm, '<h4 class="font-semibold text-sm mt-3 mb-1 text-gray-700 dark:text-gray-300">$1</h4>');
    formatted = formatted.replace(/^### (.+)$/gm, '<h3 class="font-semibold text-base mt-4 mb-2 text-gray-800 dark:text-gray-200">$1</h3>');
    formatted = formatted.replace(/^## (.+)$/gm, '<h2 class="font-bold text-lg mt-4 mb-2 text-gray-900 dark:text-gray-100">$1</h2>');
    formatted = formatted.replace(/^# (.+)$/gm, '<h1 class="font-bold text-xl mt-4 mb-3 text-gray-900 dark:text-gray-100">$1</h1>');
    
    // Task lists (checkboxes)
    formatted = formatted.replace(/^[-*] \[x\] (.+)$/gim, '<li class="task-item ml-4 flex items-start gap-2"><span class="task-checkbox checked">✓</span><span class="line-through text-gray-500">$1</span></li>');
    formatted = formatted.replace(/^[-*] \[ \] (.+)$/gm, '<li class="task-item ml-4 flex items-start gap-2"><span class="task-checkbox">○</span><span>$1</span></li>');
    
    // Tables (basic support)
    formatted = formatted.replace(/^\|(.+)\|$/gm, (match, content) => {
      const cells = content.split('|').map((cell: string) => cell.trim());
      // Check if it's a separator row
      if (cells.every((cell: string) => /^[-:]+$/.test(cell))) {
        return '__TABLE_SEP__';
      }
      const cellsHtml = cells.map((cell: string) => `<td class="border border-gray-300 dark:border-gray-600 px-3 py-2">${cell}</td>`).join('');
      return `<tr>${cellsHtml}</tr>`;
    });
    
    // Wrap table rows
    formatted = formatted.replace(/(<tr>.*?<\/tr>[\n]*)+/gs, (match) => {
      const rows = match.replace(/__TABLE_SEP__\n?/g, '').trim();
      if (rows) {
        return `<div class="overflow-x-auto my-3"><table class="min-w-full border-collapse border border-gray-300 dark:border-gray-600 text-sm">${rows}</table></div>`;
      }
      return match;
    });
    
    // Bold and Italic combined
    formatted = formatted.replace(/\*\*\*([^*]+)\*\*\*/g, '<strong><em>$1</em></strong>');
    
    // Bold
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    
    // Italic
    formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    formatted = formatted.replace(/_([^_]+)_/g, '<em>$1</em>');
    
    // Strikethrough
    formatted = formatted.replace(/~~([^~]+)~~/g, '<del class="text-gray-500">$1</del>');
    
    // Images (must be processed BEFORE links to prevent link regex from consuming ![alt](url))
    formatted = formatted.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, url) => {
      const trimmedUrl = url?.trim();
      if (!trimmedUrl || trimmedUrl === 'undefined' || trimmedUrl === 'null' || !trimmedUrl.match(/^https?:\/\/|^\//)) {
        return alt ? `[Image: ${alt}]` : '';
      }
      return `<img src="${trimmedUrl}" alt="${alt || ''}" class="max-w-full h-auto rounded-lg my-2">`;
    });
    
    // Links with title
    formatted = formatted.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]+)")?\)/g, (_, text, url, title) => {
      const trimmedUrl = url?.trim();
      if (!trimmedUrl || trimmedUrl === 'undefined' || trimmedUrl === 'null') {
        return text;
      }
      const titleAttr = title ? ` title="${title}"` : '';
      return `<a href="${trimmedUrl}" target="_blank" rel="noopener noreferrer" class="text-blue-500 hover:text-blue-600 hover:underline"${titleAttr}>${text}</a>`;
    });
    
    // Unordered lists - wrap consecutive items
    formatted = formatted.replace(/^[-*+] (.+)$/gm, '<li class="ml-4 list-disc">$1</li>');
    formatted = formatted.replace(/(<li class="ml-4 list-disc">.*?<\/li>\n?)+/gs, (match) => {
      return `<ul class="my-2 space-y-1">${match}</ul>`;
    });
    
    // Ordered lists - wrap consecutive items
    formatted = formatted.replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>');
    formatted = formatted.replace(/(<li class="ml-4 list-decimal">.*?<\/li>\n?)+/gs, (match) => {
      return `<ol class="my-2 space-y-1">${match}</ol>`;
    });
    
    // Paragraphs - double newlines create paragraph breaks
    formatted = formatted.replace(/\n\n+/g, '</p><p class="my-2">');
    
    // Single line breaks within paragraphs
    formatted = formatted.replace(/\n/g, '<br>');
    
    // Restore code blocks
    codeBlocks.forEach((block, index) => {
      formatted = formatted.replace(`__CODEBLOCK_${index}__`, block);
    });
    
    // Restore inline code
    inlineCodes.forEach((code, index) => {
      formatted = formatted.replace(`__INLINECODE_${index}__`, code);
    });
    
    // Wrap in paragraph if not already wrapped
    if (!formatted.startsWith('<')) {
      formatted = `<p class="my-2">${formatted}</p>`;
    }
    
    return formatted;
  }
  
  // Copy message content
  function copyContent(content: string) {
    if (browser) {
      navigator.clipboard.writeText(content);
    }
  }
  
  // Open palette programmatically
  export function openPalette() {
    open = true;
    conversationId = null; // Start fresh - Dify will return actual conversation_id
    setTimeout(() => inputElement?.focus(), 50);
  }
  
  onMount(() => {
    if (browser) {
      window.addEventListener('keydown', handleGlobalKeydown);
      // Generate user ID from localStorage or create new
      const storedUserId = localStorage.getItem('hippo-user-id');
      if (storedUserId) {
        userId = storedUserId;
      } else {
        userId = `hippo-user-${crypto.randomUUID().slice(0, 8)}`;
        localStorage.setItem('hippo-user-id', userId);
      }
    }
  });
  
  onDestroy(() => {
    if (browser) {
      window.removeEventListener('keydown', handleGlobalKeydown);
    }
    if (abortController) {
      abortController.abort();
    }
  });
</script>

{#if open}
  <!-- Backdrop -->
  <div 
    class="fixed inset-0 z-[100] backdrop-overlay"
    transition:fade={{ duration: 200 }}
    on:click={close}
    on:keydown={(e) => e.key === 'Escape' && close()}
    role="button"
    tabindex="-1"
    aria-label="Close command palette"
  />
  
  <!-- Command Palette Container -->
  <div 
    class="fixed inset-0 z-[101] flex items-start justify-center pt-[12vh] pointer-events-none"
  >
    <div 
      class="command-palette pointer-events-auto"
      class:chat-mode={hasStartedChat}
      transition:scale={{ duration: 250, start: 0.96, easing: backOut }}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <!-- Hidden file input -->
      <input
        bind:this={fileInputElement}
        type="file"
        multiple
        accept="image/*,.pdf,.doc,.docx,.txt,.md,.json,.csv,.xlsx,.xls"
        on:change={handleFileSelect}
        class="hidden-file-input"
      />
      
      <!-- Initial Search View -->
      {#if !hasStartedChat}
        <div class="search-container" transition:fade={{ duration: 150 }}>
          <!-- Search Icon -->
          <div class="search-icon">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          
          <!-- Input -->
          <input
            bind:this={inputElement}
            bind:value={inputValue}
            on:keydown={handleInputKeydown}
            type="text"
            placeholder={$t.commandPalette?.agentPlaceholder || "Ask anything or run a command…"}
            class="search-input"
            autocomplete="off"
            autocorrect="off"
            autocapitalize="off"
            spellcheck="false"
          />
          
          <!-- File Upload Button -->
          <button 
            class="attach-btn"
            on:click={openFilePicker}
            disabled={isUploadingFile}
            title={$t.commandPalette?.attachFile || 'Attach file'}
          >
            {#if isUploadingFile}
              <svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            {:else}
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            {/if}
          </button>
          
          <!-- Keyboard Hint -->
          <div class="keyboard-hints">
            <kbd class="kbd">↵</kbd>
            <span class="hint-text">{$t.commandPalette?.send || 'Send'}</span>
          </div>
        </div>

        <!-- Skill Dropdown (initial view) -->
        {#if showSkillDropdown && !hasStartedChat && filteredSkills.length > 0}
          <div class="skill-dropdown" transition:fly={{ y: -8, duration: 150 }}>
            <div class="skill-dropdown-header">
              <svg class="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <span>{$t.skills?.selectHint || 'Select a skill'}</span>
            </div>
            {#each filteredSkills as skill, i (skill.id)}
              <button
                class="skill-dropdown-item {i === skillDropdownIndex ? 'active' : ''}"
                on:click={() => selectSkill(skill)}
                on:mouseenter={() => skillDropdownIndex = i}
              >
                <div class="skill-dropdown-icon">
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <span class="skill-dropdown-name">{skill.name}</span>
              </button>
            {/each}
          </div>
        {/if}

        <!-- Selected Skill Chip (initial view) -->
        {#if selectedSkill && !hasStartedChat}
          <div class="selected-skill-bar" transition:fly={{ y: -10, duration: 200 }}>
            <div class="selected-skill-chip">
              <svg class="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <span class="text-xs font-medium text-emerald-700 dark:text-emerald-300">{selectedSkill.name}</span>
              <button class="remove-skill-btn" on:click={removeSelectedSkill}>
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        {/if}
        
        <!-- Uploaded Files Display -->
        {#if uploadedFiles.length > 0}
          <div class="uploaded-files" transition:fly={{ y: -10, duration: 200 }}>
            {#each uploadedFiles as file (file.id)}
              <div class="file-chip" transition:scale={{ duration: 150 }}>
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span class="file-name">{file.name}</span>
                <span class="file-size">{formatFileSize(file.size)}</span>
                <button class="remove-file-btn" on:click={() => removeFile(file.id)} title="Remove">
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            {/each}
          </div>
        {/if}
        
        <!-- Context Indicator -->
        {#if currentContext}
          <div class="context-indicator" transition:fade={{ duration: 150 }}>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{$t.commandPalette?.contextAvailable || 'Recording context available'}</span>
            <span class="context-hint">{$t.commandPalette?.contextHint || 'Mention "上下文" or "context" to include it'}</span>
          </div>
        {/if}
        
        <!-- Helper Text -->
        <div class="helper-section">
          <div class="helper-icon">
            <svg class="w-12 h-12 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <p class="helper-title">{$t.commandPalette?.helperTitle || 'AI-Powered Assistant'}</p>
          <p class="helper-desc">{$t.commandPalette?.helperDesc || 'Ask questions, run commands, or let AI help you with any task'}</p>
        </div>
        
        <!-- Footer -->
        <div class="palette-footer">
          <div class="footer-hint">
            <kbd class="kbd-small">Esc</kbd>
            <span>{$t.commandPalette?.close || 'Close'}</span>
          </div>
          <div class="footer-hint">
            <span class="text-xs text-gray-400">Powered by Hippo Agent</span>
          </div>
        </div>
      {/if}
      
      <!-- Chat View -->
      {#if hasStartedChat}
        <div class="chat-container" transition:fade={{ duration: 200 }}>
          <!-- Chat Header -->
          <div class="chat-header">
            <div class="header-left">
              <div class="agent-avatar">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div class="header-info">
                <span class="header-title">{$t.commandPalette?.agent?.title || 'Hippo Agent'}</span>
                {#if isStreaming}
                  <span class="status-streaming">
                    <span class="status-dot"></span>
                    {$t.commandPalette?.agent?.thinking || 'Thinking…'}
                  </span>
                {:else}
                  <span class="status-ready">{$t.commandPalette?.agent?.ready || 'Ready'}</span>
                {/if}
              </div>
            </div>
            <button class="close-btn" on:click={close} aria-label="Close">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <!-- Messages -->
          <div class="messages-container" bind:this={chatContainerElement}>
            {#each messages as message (message.id)}
              <div 
                class="message {message.role}"
                transition:fly={{ y: 10, duration: 200 }}
              >
                {#if message.role === 'user'}
                  <div class="message-content user-message">
                    <p>{message.content}</p>
                  </div>
                {:else}
                  <div class="message-content assistant-message">
                    {#if message.agentSteps && message.agentSteps.length > 0}
                      <!-- Render each agent step as an independent unit in position order -->
                      {#each message.agentSteps as step, stepIdx (step.id)}
                        {#if step.tool}
                          <!-- Tool call card -->
                          <div class="agent-step-card" class:expanded={expandedSteps.has(step.id)}>
                            <button
                              class="agent-step-header"
                              on:click={() => toggleStep(step.id)}
                            >
                              <div class="agent-step-icon" class:spinning={step.status === 'calling'}>
                                {#if step.status === 'calling'}
                                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                  </svg>
                                {:else}
                                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                  </svg>
                                {/if}
                              </div>
                              <span class="agent-step-tool-name">
                                {step.status === 'calling' ? '正在使用' : '已使用'} {step.tool}
                              </span>
                              <svg
                                class="agent-step-chevron w-3.5 h-3.5"
                                class:rotated={expandedSteps.has(step.id)}
                                fill="none" stroke="currentColor" viewBox="0 0 24 24"
                              >
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                              </svg>
                            </button>
                            {#if expandedSteps.has(step.id)}
                              <div class="agent-step-detail" transition:fly={{ y: -5, duration: 150 }}>
                                {#if step.toolInput}
                                  <div class="step-section">
                                    <span class="step-label">Input</span>
                                    <pre class="step-content">{step.toolInput}</pre>
                                  </div>
                                {/if}
                                {#if step.observation}
                                  <div class="step-section">
                                    <span class="step-label">Result</span>
                                    <pre class="step-content">{step.observation.length > 500 ? step.observation.slice(0, 500) + '...' : step.observation}</pre>
                                  </div>
                                {/if}
                              </div>
                            {/if}
                          </div>
                          <!-- Thought text after this tool call (intermediate reasoning) -->
                          {#if step.thought}
                            <div class="agent-step-thought">
                              {@html formatMarkdown(step.thought)}
                            </div>
                          {/if}
                        {:else if step.thought}
                          <!-- Non-tool step: pure thought/reasoning text -->
                          <div class="agent-step-thought">
                            {@html formatMarkdown(step.thought)}
                          </div>
                        {/if}
                      {/each}

                      <!-- Final answer from agent_message, only if it differs from the last step's thought -->
                      {#if message.content && message.content !== message.agentSteps[message.agentSteps.length - 1]?.thought}
                        <div class="markdown-content">
                          {@html formatMarkdown(message.content)}
                        </div>
                      {/if}
                    {:else}
                      <!-- Non-agent response: plain text -->
                      {#if message.content}
                        <div class="markdown-content">
                          {@html formatMarkdown(message.content)}
                        </div>
                      {/if}
                    {/if}

                    {#if message.isStreaming && !message.content && !(message.agentSteps && message.agentSteps.length > 0)}
                      <div class="typing-dots">
                        <span class="dot"></span>
                        <span class="dot"></span>
                        <span class="dot"></span>
                      </div>
                    {/if}
                    {#if message.isStreaming && message.content}
                      <span class="streaming-cursor">▋</span>
                    {/if}
                  </div>
                  
                  <!-- Message Actions -->
                  {#if !message.isStreaming && message.content}
                    <div class="message-actions">
                      <button 
                        class="action-btn"
                        on:click={() => copyContent(message.content)}
                        title={$t.commandPalette?.agent?.copy || 'Copy'}
                      >
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      </button>
                    </div>
                  {/if}
                {/if}
              </div>
            {/each}
            
            <!-- Error Message -->
            {#if streamingError}
              <div class="error-message" transition:fade={{ duration: 150 }}>
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{streamingError}</span>
                <button class="retry-btn" on:click={regenerate}>
                  {$t.commandPalette?.agent?.retry || 'Retry'}
                </button>
              </div>
            {/if}
          </div>
          
          <!-- Chat Input -->
          <div class="chat-input-container">
            <!-- Uploaded Files in Chat -->
            {#if uploadedFiles.length > 0}
              <div class="chat-uploaded-files" transition:fly={{ y: 10, duration: 200 }}>
                {#each uploadedFiles as file (file.id)}
                  <div class="file-chip small" transition:scale={{ duration: 150 }}>
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span class="file-name">{file.name}</span>
                    <button class="remove-file-btn" on:click={() => removeFile(file.id)} title="Remove">
                      <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                {/each}
              </div>
            {/if}
            
            {#if isStreaming}
              <button class="stop-btn" on:click={stopStreaming}>
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                </svg>
                <span>{$t.commandPalette?.agent?.stop || 'Stop'}</span>
              </button>
            {:else}
              <!-- Skill Dropdown (chat mode) -->
              {#if showSkillDropdown && hasStartedChat && filteredSkills.length > 0}
                <div class="skill-dropdown chat-skill-dropdown" transition:fly={{ y: 8, duration: 150 }}>
                  <div class="skill-dropdown-header">
                    <svg class="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <span>{$t.skills?.selectHint || 'Select a skill'}</span>
                  </div>
                  {#each filteredSkills as skill, i (skill.id)}
                    <button
                      class="skill-dropdown-item {i === skillDropdownIndex ? 'active' : ''}"
                      on:click={() => selectSkill(skill)}
                      on:mouseenter={() => skillDropdownIndex = i}
                    >
                      <div class="skill-dropdown-icon">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                      </div>
                      <span class="skill-dropdown-name">{skill.name}</span>
                    </button>
                  {/each}
                </div>
              {/if}

              <!-- Selected Skill Chip (chat mode) -->
              {#if selectedSkill && hasStartedChat}
                <div class="chat-selected-skill" transition:fly={{ y: 10, duration: 200 }}>
                  <div class="selected-skill-chip">
                    <svg class="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <span class="text-xs font-medium text-emerald-700 dark:text-emerald-300">{selectedSkill.name}</span>
                    <button class="remove-skill-btn" on:click={removeSelectedSkill}>
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              {/if}

              <div class="input-wrapper">
                <!-- Attach File Button -->
                <button 
                  class="attach-btn-small"
                  on:click={openFilePicker}
                  disabled={isUploadingFile}
                  title={$t.commandPalette?.attachFile || 'Attach file'}
                >
                  {#if isUploadingFile}
                    <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  {:else}
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                    </svg>
                  {/if}
                </button>
                
                <input
                  bind:this={chatInputElement}
                  bind:value={inputValue}
                  on:keydown={handleInputKeydown}
                  type="text"
                  placeholder={$t.commandPalette?.agent?.inputPlaceholder || "Type your message…"}
                  class="chat-input"
                  autocomplete="off"
                />
                <button 
                  class="send-btn"
                  on:click={sendMessage}
                  disabled={!inputValue.trim() && uploadedFiles.length === 0}
                  aria-label="Send message"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </div>
              
              <!-- Context Available Hint (in chat mode) -->
              {#if currentContext}
                <div class="chat-context-hint" transition:fade={{ duration: 150 }}>
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>{$t.commandPalette?.contextHintShort || 'Say "上下文" to include recording context'}</span>
                </div>
              {/if}
              
              <!-- Regenerate Button -->
              {#if messages.length >= 2 && !isStreaming}
                <button class="regenerate-btn" on:click={regenerate}>
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <span>{$t.commandPalette?.agent?.regenerate || 'Regenerate'}</span>
                </button>
              {/if}
            {/if}
          </div>
          
          <!-- Chat Footer -->
          <div class="chat-footer">
            <kbd class="kbd-small">↵</kbd>
            <span>{$t.commandPalette?.send || 'Send'}</span>
            <span class="footer-divider">•</span>
            <kbd class="kbd-small">Esc</kbd>
            <span>{$t.commandPalette?.close || 'Close'}</span>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  /* Backdrop */
  .backdrop-overlay {
    background: rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }
  
  :global(.dark) .backdrop-overlay {
    background: rgba(0, 0, 0, 0.6);
  }
  
  /* Command Palette */
  .command-palette {
    width: 100%;
    max-width: 640px;
    margin: 0 16px;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 16px;
    border: 1px solid rgba(0, 0, 0, 0.08);
    box-shadow: 
      0 24px 80px -12px rgba(0, 0, 0, 0.25),
      0 0 0 1px rgba(255, 255, 255, 0.5) inset;
    overflow: hidden;
    transition: all 0.2s ease;
  }
  
  :global(.dark) .command-palette {
    background: rgba(28, 28, 30, 0.95);
    border-color: rgba(255, 255, 255, 0.1);
    box-shadow: 
      0 24px 80px -12px rgba(0, 0, 0, 0.5),
      0 0 0 1px rgba(255, 255, 255, 0.1) inset;
  }
  
  .command-palette.chat-mode {
    max-height: 70vh;
    display: flex;
    flex-direction: column;
  }
  
  /* Search Container */
  .search-container {
    display: flex;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    gap: 12px;
  }
  
  :global(.dark) .search-container {
    border-bottom-color: rgba(255, 255, 255, 0.08);
  }
  
  .search-icon {
    flex-shrink: 0;
    color: #9ca3af;
  }
  
  :global(.dark) .search-icon {
    color: #6b7280;
  }
  
  .search-input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    font-size: 17px;
    font-weight: 400;
    color: #1f2937;
    letter-spacing: -0.01em;
  }
  
  .search-input::placeholder {
    color: #9ca3af;
  }
  
  :global(.dark) .search-input {
    color: #f3f4f6;
  }
  
  :global(.dark) .search-input::placeholder {
    color: #6b7280;
  }
  
  .keyboard-hints {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }
  
  .kbd {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    height: 24px;
    padding: 0 6px;
    font-size: 12px;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
    font-weight: 500;
    color: #6b7280;
    background: rgba(0, 0, 0, 0.05);
    border-radius: 6px;
    border: 1px solid rgba(0, 0, 0, 0.08);
  }
  
  :global(.dark) .kbd {
    color: #9ca3af;
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.1);
  }
  
  .hint-text {
    font-size: 12px;
    color: #9ca3af;
  }
  
  /* Helper Section */
  .helper-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    text-align: center;
  }
  
  .helper-icon {
    margin-bottom: 16px;
    opacity: 0.5;
  }
  
  .helper-title {
    font-size: 15px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 4px;
  }
  
  :global(.dark) .helper-title {
    color: #e5e7eb;
  }
  
  .helper-desc {
    font-size: 13px;
    color: #9ca3af;
    max-width: 300px;
  }
  
  /* Palette Footer */
  .palette-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    border-top: 1px solid rgba(0, 0, 0, 0.06);
    background: rgba(0, 0, 0, 0.02);
  }
  
  :global(.dark) .palette-footer {
    border-top-color: rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.02);
  }
  
  .footer-hint {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: #9ca3af;
  }
  
  .kbd-small {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 18px;
    padding: 0 5px;
    font-size: 10px;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
    font-weight: 500;
    color: #9ca3af;
    background: rgba(0, 0, 0, 0.05);
    border-radius: 4px;
    border: 1px solid rgba(0, 0, 0, 0.08);
  }
  
  :global(.dark) .kbd-small {
    color: #6b7280;
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.1);
  }
  
  /* Chat Container */
  .chat-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    max-height: 70vh;
  }
  
  /* Chat Header */
  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    background: rgba(255, 255, 255, 0.5);
    flex-shrink: 0;
  }
  
  :global(.dark) .chat-header {
    border-bottom-color: rgba(255, 255, 255, 0.08);
    background: rgba(0, 0, 0, 0.2);
  }
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  
  .agent-avatar {
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
  }
  
  .header-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  
  .header-title {
    font-size: 14px;
    font-weight: 600;
    color: #1f2937;
  }
  
  :global(.dark) .header-title {
    color: #f3f4f6;
  }
  
  .status-streaming {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: #10b981;
  }
  
  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #10b981;
    animation: pulse 1.5s ease-in-out infinite;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(0.8); }
  }
  
  .status-ready {
    font-size: 11px;
    color: #9ca3af;
  }
  
  .close-btn {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #9ca3af;
    transition: all 0.15s ease;
  }
  
  .close-btn:hover {
    background: rgba(0, 0, 0, 0.05);
    color: #6b7280;
  }
  
  :global(.dark) .close-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #d1d5db;
  }
  
  /* Messages Container */
  .messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 200px;
  }
  
  /* Messages */
  .message {
    display: flex;
    flex-direction: column;
    max-width: 85%;
  }
  
  .message.user {
    align-self: flex-end;
  }
  
  .message.assistant {
    align-self: flex-start;
  }
  
  .message-content {
    padding: 10px 14px;
    border-radius: 16px;
    font-size: 14px;
    line-height: 1.5;
  }
  
  .user-message {
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    color: white;
    border-bottom-right-radius: 4px;
  }
  
  .assistant-message {
    background: rgba(0, 0, 0, 0.04);
    color: #374151;
    border-bottom-left-radius: 4px;
  }
  
  :global(.dark) .assistant-message {
    background: rgba(255, 255, 255, 0.08);
    color: #e5e7eb;
  }

  /* Agent Steps */
  .agent-step-card {
    margin-bottom: 6px;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 10px;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.6);
    transition: border-color 0.15s ease;
  }

  .agent-step-card:hover {
    border-color: rgba(0, 0, 0, 0.15);
  }

  .agent-step-card.expanded {
    border-color: rgba(59, 130, 246, 0.3);
  }

  :global(.dark) .agent-step-card {
    border-color: rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.04);
  }

  :global(.dark) .agent-step-card:hover {
    border-color: rgba(255, 255, 255, 0.2);
  }

  :global(.dark) .agent-step-card.expanded {
    border-color: rgba(96, 165, 250, 0.3);
  }

  .agent-step-header {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 13px;
    color: #6b7280;
    text-align: left;
    transition: background 0.1s ease;
  }

  .agent-step-header:hover {
    background: rgba(0, 0, 0, 0.03);
  }

  :global(.dark) .agent-step-header {
    color: #9ca3af;
  }

  :global(.dark) .agent-step-header:hover {
    background: rgba(255, 255, 255, 0.05);
  }

  .agent-step-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 5px;
    background: rgba(59, 130, 246, 0.1);
    color: #3b82f6;
    flex-shrink: 0;
  }

  .agent-step-icon.spinning svg {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .agent-step-tool-name {
    flex: 1;
    font-weight: 500;
    color: #374151;
  }

  :global(.dark) .agent-step-tool-name {
    color: #d1d5db;
  }

  .agent-step-chevron {
    flex-shrink: 0;
    color: #9ca3af;
    transition: transform 0.2s ease;
  }

  .agent-step-chevron.rotated {
    transform: rotate(90deg);
  }

  .agent-step-detail {
    padding: 0 12px 10px;
    border-top: 1px solid rgba(0, 0, 0, 0.05);
  }

  :global(.dark) .agent-step-detail {
    border-top-color: rgba(255, 255, 255, 0.06);
  }

  .step-section {
    margin-top: 8px;
  }

  .step-label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9ca3af;
    margin-bottom: 4px;
  }

  .step-content {
    font-size: 12px;
    line-height: 1.5;
    color: #6b7280;
    background: rgba(0, 0, 0, 0.03);
    border-radius: 6px;
    padding: 8px 10px;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 200px;
    overflow-y: auto;
  }

  .step-content.thought {
    font-style: italic;
    background: rgba(59, 130, 246, 0.05);
  }

  :global(.dark) .step-content {
    color: #9ca3af;
    background: rgba(255, 255, 255, 0.04);
  }

  :global(.dark) .step-content.thought {
    background: rgba(96, 165, 250, 0.08);
  }

  .agent-step-thought {
    font-size: 13px;
    line-height: 1.6;
    color: #4b5563;
    padding: 4px 2px 8px;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }

  :global(.dark) .agent-step-thought {
    color: #d1d5db;
  }

  /* Markdown Content */
  .markdown-content {
    word-wrap: break-word;
    overflow-wrap: break-word;
  }
  
  .markdown-content :global(p) {
    margin: 0.5rem 0;
  }
  
  .markdown-content :global(p:first-child) {
    margin-top: 0;
  }
  
  .markdown-content :global(p:last-child) {
    margin-bottom: 0;
  }
  
  /* Code blocks with header */
  .markdown-content :global(pre.code-block) {
    background: rgba(0, 0, 0, 0.06);
    border-radius: 8px;
    margin: 12px 0;
    overflow: hidden;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, monospace;
    font-size: 12px;
    line-height: 1.6;
  }
  
  :global(.dark) .markdown-content :global(pre.code-block) {
    background: rgba(0, 0, 0, 0.4);
  }
  
  .markdown-content :global(.code-header) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 12px;
    background: rgba(0, 0, 0, 0.04);
    border-bottom: 1px solid rgba(0, 0, 0, 0.08);
    font-size: 11px;
  }
  
  :global(.dark) .markdown-content :global(.code-header) {
    background: rgba(255, 255, 255, 0.05);
    border-bottom-color: rgba(255, 255, 255, 0.1);
  }
  
  .markdown-content :global(.code-lang) {
    color: #6b7280;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  :global(.dark) .markdown-content :global(.code-lang) {
    color: #9ca3af;
  }
  
  .markdown-content :global(.copy-code-btn) {
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 500;
    color: #6b7280;
    background: rgba(0, 0, 0, 0.05);
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  
  .markdown-content :global(.copy-code-btn:hover) {
    background: rgba(0, 0, 0, 0.1);
    color: #374151;
  }
  
  :global(.dark) .markdown-content :global(.copy-code-btn) {
    color: #9ca3af;
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.1);
  }
  
  :global(.dark) .markdown-content :global(.copy-code-btn:hover) {
    background: rgba(255, 255, 255, 0.1);
    color: #e5e7eb;
  }
  
  .markdown-content :global(pre.code-block code) {
    display: block;
    padding: 12px;
    overflow-x: auto;
  }
  
  /* Inline code */
  .markdown-content :global(code.inline-code) {
    background: rgba(0, 0, 0, 0.08);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, monospace;
    font-size: 0.875em;
    color: #e11d48;
  }
  
  :global(.dark) .markdown-content :global(code.inline-code) {
    background: rgba(255, 255, 255, 0.1);
    color: #fb7185;
  }
  
  /* Headers */
  .markdown-content :global(h1),
  .markdown-content :global(h2),
  .markdown-content :global(h3),
  .markdown-content :global(h4),
  .markdown-content :global(h5),
  .markdown-content :global(h6) {
    font-weight: 600;
    line-height: 1.3;
  }
  
  /* Blockquotes */
  .markdown-content :global(blockquote) {
    margin: 12px 0;
    padding: 8px 16px;
    background: rgba(59, 130, 246, 0.05);
    border-left: 4px solid #3b82f6;
    border-radius: 0 8px 8px 0;
  }
  
  :global(.dark) .markdown-content :global(blockquote) {
    background: rgba(59, 130, 246, 0.1);
  }
  
  /* Lists */
  .markdown-content :global(ul),
  .markdown-content :global(ol) {
    margin: 8px 0;
    padding-left: 8px;
  }
  
  .markdown-content :global(li) {
    margin: 4px 0;
    line-height: 1.5;
  }
  
  /* Task items */
  .markdown-content :global(.task-item) {
    list-style: none;
  }
  
  .markdown-content :global(.task-checkbox) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 2px solid #d1d5db;
    font-size: 10px;
    flex-shrink: 0;
    margin-top: 3px;
  }
  
  .markdown-content :global(.task-checkbox.checked) {
    background: #10b981;
    border-color: #10b981;
    color: white;
  }
  
  :global(.dark) .markdown-content :global(.task-checkbox) {
    border-color: #4b5563;
  }
  
  /* Tables */
  .markdown-content :global(table) {
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 13px;
  }
  
  .markdown-content :global(th),
  .markdown-content :global(td) {
    padding: 8px 12px;
    border: 1px solid rgba(0, 0, 0, 0.12);
    text-align: left;
  }
  
  .markdown-content :global(th) {
    background: rgba(0, 0, 0, 0.04);
    font-weight: 600;
  }
  
  :global(.dark) .markdown-content :global(th),
  :global(.dark) .markdown-content :global(td) {
    border-color: rgba(255, 255, 255, 0.12);
  }
  
  :global(.dark) .markdown-content :global(th) {
    background: rgba(255, 255, 255, 0.05);
  }
  
  /* Horizontal rule */
  .markdown-content :global(hr) {
    margin: 16px 0;
    border: none;
    height: 1px;
    background: rgba(0, 0, 0, 0.12);
  }
  
  :global(.dark) .markdown-content :global(hr) {
    background: rgba(255, 255, 255, 0.12);
  }
  
  /* Links */
  .markdown-content :global(a) {
    color: #3b82f6;
    text-decoration: none;
    transition: color 0.15s ease;
  }
  
  .markdown-content :global(a:hover) {
    color: #2563eb;
    text-decoration: underline;
  }
  
  :global(.dark) .markdown-content :global(a) {
    color: #60a5fa;
  }
  
  :global(.dark) .markdown-content :global(a:hover) {
    color: #93c5fd;
  }
  
  /* Images */
  .markdown-content :global(img) {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    margin: 8px 0;
  }
  
  /* Strong and emphasis */
  .markdown-content :global(strong) {
    font-weight: 600;
  }
  
  .markdown-content :global(em) {
    font-style: italic;
  }
  
  .markdown-content :global(del) {
    text-decoration: line-through;
    opacity: 0.7;
  }
  
  /* Typing Dots */
  .typing-dots {
    display: flex;
    gap: 4px;
    padding: 4px 0;
  }
  
  .typing-dots .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #9ca3af;
    animation: typing-bounce 1.4s ease-in-out infinite both;
  }
  
  .typing-dots .dot:nth-child(1) { animation-delay: -0.32s; }
  .typing-dots .dot:nth-child(2) { animation-delay: -0.16s; }
  .typing-dots .dot:nth-child(3) { animation-delay: 0s; }
  
  @keyframes typing-bounce {
    0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
    40% { transform: scale(1); opacity: 1; }
  }
  
  /* Streaming Cursor */
  .streaming-cursor {
    animation: blink 1s step-end infinite;
    color: #3b82f6;
  }
  
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }
  
  /* Message Actions */
  .message-actions {
    display: flex;
    gap: 4px;
    margin-top: 4px;
    opacity: 0;
    transition: opacity 0.15s ease;
  }
  
  .message:hover .message-actions {
    opacity: 1;
  }
  
  .action-btn {
    width: 24px;
    height: 24px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #9ca3af;
    transition: all 0.15s ease;
  }
  
  .action-btn:hover {
    background: rgba(0, 0, 0, 0.05);
    color: #6b7280;
  }
  
  :global(.dark) .action-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #d1d5db;
  }
  
  /* Error Message */
  .error-message {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 10px;
    font-size: 13px;
    color: #dc2626;
  }
  
  :global(.dark) .error-message {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.3);
    color: #fca5a5;
  }
  
  .retry-btn {
    margin-left: auto;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 500;
    color: #dc2626;
    background: rgba(239, 68, 68, 0.1);
    border-radius: 6px;
    transition: all 0.15s ease;
  }
  
  .retry-btn:hover {
    background: rgba(239, 68, 68, 0.2);
  }
  
  /* Chat Input Container */
  .chat-input-container {
    padding: 12px 16px;
    border-top: 1px solid rgba(0, 0, 0, 0.06);
    background: rgba(0, 0, 0, 0.02);
    flex-shrink: 0;
  }
  
  :global(.dark) .chat-input-container {
    border-top-color: rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.02);
  }
  
  .input-wrapper {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 12px;
    transition: all 0.15s ease;
  }
  
  .input-wrapper:focus-within {
    border-color: rgba(59, 130, 246, 0.5);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
  
  :global(.dark) .input-wrapper {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.1);
  }
  
  :global(.dark) .input-wrapper:focus-within {
    border-color: rgba(59, 130, 246, 0.5);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
  }
  
  .chat-input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    font-size: 14px;
    color: #1f2937;
  }
  
  .chat-input::placeholder {
    color: #9ca3af;
  }
  
  :global(.dark) .chat-input {
    color: #f3f4f6;
  }
  
  :global(.dark) .chat-input::placeholder {
    color: #6b7280;
  }
  
  .send-btn {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #3b82f6, #2563eb);
    color: white;
    transition: all 0.15s ease;
    flex-shrink: 0;
  }
  
  .send-btn:hover:not(:disabled) {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  }
  
  .send-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .stop-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    padding: 10px;
    font-size: 13px;
    font-weight: 500;
    color: #dc2626;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 10px;
    transition: all 0.15s ease;
  }
  
  .stop-btn:hover {
    background: rgba(239, 68, 68, 0.15);
  }
  
  .regenerate-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    margin-top: 8px;
    padding: 8px;
    font-size: 12px;
    font-weight: 500;
    color: #6b7280;
    background: transparent;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 8px;
    transition: all 0.15s ease;
  }
  
  .regenerate-btn:hover {
    background: rgba(0, 0, 0, 0.03);
    border-color: rgba(0, 0, 0, 0.12);
  }
  
  :global(.dark) .regenerate-btn {
    border-color: rgba(255, 255, 255, 0.1);
    color: #9ca3af;
  }
  
  :global(.dark) .regenerate-btn:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.15);
  }
  
  /* Chat Footer */
  .chat-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 16px;
    font-size: 11px;
    color: #9ca3af;
    border-top: 1px solid rgba(0, 0, 0, 0.04);
    flex-shrink: 0;
  }
  
  :global(.dark) .chat-footer {
    border-top-color: rgba(255, 255, 255, 0.06);
  }
  
  .footer-divider {
    opacity: 0.5;
  }
  
  /* Scrollbar */
  .messages-container::-webkit-scrollbar {
    width: 6px;
  }
  
  .messages-container::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .messages-container::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.15);
    border-radius: 10px;
  }
  
  :global(.dark) .messages-container::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
  }
  
  /* Hidden File Input */
  .hidden-file-input {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  
  /* Attach Button */
  .attach-btn {
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #6b7280;
    transition: all 0.15s ease;
  }
  
  .attach-btn:hover:not(:disabled) {
    background: rgba(0, 0, 0, 0.05);
    color: #3b82f6;
  }
  
  .attach-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  :global(.dark) .attach-btn {
    color: #9ca3af;
  }
  
  :global(.dark) .attach-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    color: #60a5fa;
  }
  
  .attach-btn-small {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #9ca3af;
    transition: all 0.15s ease;
  }
  
  .attach-btn-small:hover:not(:disabled) {
    background: rgba(0, 0, 0, 0.05);
    color: #3b82f6;
  }
  
  .attach-btn-small:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  :global(.dark) .attach-btn-small:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    color: #60a5fa;
  }
  
  /* Uploaded Files */
  .uploaded-files {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 8px 16px;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  }
  
  :global(.dark) .uploaded-files {
    border-bottom-color: rgba(255, 255, 255, 0.08);
  }
  
  .chat-uploaded-files {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
  }
  
  .file-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 8px;
    font-size: 12px;
    color: #3b82f6;
    transition: all 0.15s ease;
  }
  
  .file-chip.small {
    padding: 4px 8px;
    font-size: 11px;
    border-radius: 6px;
  }
  
  :global(.dark) .file-chip {
    background: rgba(59, 130, 246, 0.15);
    border-color: rgba(59, 130, 246, 0.3);
    color: #60a5fa;
  }
  
  .file-name {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 500;
  }
  
  .file-size {
    color: #9ca3af;
    font-size: 10px;
  }
  
  .remove-file-btn {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #9ca3af;
    transition: all 0.15s ease;
    margin-left: 2px;
  }
  
  .remove-file-btn:hover {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
  }
  
  /* Context Indicator */
  .context-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.08), rgba(59, 130, 246, 0.08));
    border-bottom: 1px solid rgba(139, 92, 246, 0.1);
    font-size: 12px;
    color: #7c3aed;
  }
  
  :global(.dark) .context-indicator {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(59, 130, 246, 0.12));
    border-bottom-color: rgba(139, 92, 246, 0.2);
    color: #a78bfa;
  }
  
  .context-hint {
    color: #9ca3af;
    font-size: 11px;
    margin-left: auto;
  }
  
  :global(.dark) .context-hint {
    color: #6b7280;
  }
  
  .chat-context-hint {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
    font-size: 11px;
    color: #8b5cf6;
    opacity: 0.8;
  }
  
  :global(.dark) .chat-context-hint {
    color: #a78bfa;
  }
  
  /* Spin Animation */
  .animate-spin {
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  /* Skill Dropdown */
  .skill-dropdown {
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    max-height: 200px;
    overflow-y: auto;
  }
  :global(.dark) .skill-dropdown {
    border-bottom-color: rgba(255, 255, 255, 0.08);
  }
  .chat-skill-dropdown {
    border-bottom: none;
    border-top: 1px solid rgba(0, 0, 0, 0.06);
    margin-bottom: 8px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid rgba(0, 0, 0, 0.08);
  }
  :global(.dark) .chat-skill-dropdown {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.1);
  }

  .skill-dropdown-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px 4px 14px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #9ca3af;
  }

  .skill-dropdown-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 14px;
    font-size: 13px;
    text-align: left;
    transition: background 0.1s ease;
    cursor: pointer;
  }
  .skill-dropdown-item:hover,
  .skill-dropdown-item.active {
    background: rgba(16, 185, 129, 0.08);
  }
  :global(.dark) .skill-dropdown-item:hover,
  :global(.dark) .skill-dropdown-item.active {
    background: rgba(16, 185, 129, 0.12);
  }

  .skill-dropdown-icon {
    width: 24px;
    height: 24px;
    border-radius: 6px;
    background: linear-gradient(135deg, #10b981, #14b8a6);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;
  }

  .skill-dropdown-name {
    font-weight: 500;
    color: #1f2937;
  }
  :global(.dark) .skill-dropdown-name {
    color: #f3f4f6;
  }

  /* Selected Skill Bar / Chip */
  .selected-skill-bar {
    padding: 6px 16px;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  }
  :global(.dark) .selected-skill-bar {
    border-bottom-color: rgba(255, 255, 255, 0.08);
  }

  .chat-selected-skill {
    margin-bottom: 8px;
  }

  .selected-skill-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-radius: 8px;
  }
  :global(.dark) .selected-skill-chip {
    background: rgba(16, 185, 129, 0.15);
    border-color: rgba(16, 185, 129, 0.3);
  }

  .remove-skill-btn {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #9ca3af;
    transition: all 0.15s ease;
    margin-left: 2px;
  }
  .remove-skill-btn:hover {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
  }
</style>
