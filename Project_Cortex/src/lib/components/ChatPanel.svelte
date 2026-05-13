<script lang="ts">
  import { messages, userContext, promptSuggestions, currentConversationId, pendingFiles, type Message, type FileAttachment } from '$lib/stores/chat';
  import { apiConfig } from '$lib/stores/config';
  import { streamDifyChat, uploadFileToDify } from '$lib/utils/streaming';
  import { throttle, rafDebounce } from '$lib/utils/debounce';
  import RecordButton from './RecordButton.svelte';
  import HighlightButton from './HighlightButton.svelte';
  import PromptSuggestions from './PromptSuggestions.svelte';
  import ChatMessage from './ChatMessage.svelte';
  import ContextSelector from './ContextSelector.svelte';
  import { onMount, onDestroy, tick } from 'svelte';
  import { t } from '$lib/stores/i18n';

  let inputValue = '';
  let chatContainer: HTMLDivElement;
  let isStreaming = false;
  let lastScrollTop = 0;
  let isContextRowVisible = true;
  let isOverflowVisible = true;
  let overflowTimeout: ReturnType<typeof setTimeout>;
  let scrollRAF: number | null = null;
  let fileInput: HTMLInputElement;
  let isUploadingFiles = false;

  // Manage overflow visibility based on row visibility - debounced
  $: if (isContextRowVisible) {
    clearTimeout(overflowTimeout);
    overflowTimeout = setTimeout(() => {
      isOverflowVisible = true;
    }, 300);
  } else {
    clearTimeout(overflowTimeout);
    isOverflowVisible = false;
  }

  // Cleanup on destroy
  onDestroy(() => {
    clearTimeout(overflowTimeout);
    if (scrollRAF) cancelAnimationFrame(scrollRAF);
  });

  // Handle file selection
  async function handleFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    const files = target.files;
    if (!files || files.length === 0) return;

    isUploadingFiles = true;

    for (const file of Array.from(files)) {
      const attachment: FileAttachment = {
        id: crypto.randomUUID(),
        name: file.name,
        size: file.size,
        type: file.type,
        status: 'uploading'
      };

      // Add to pending files
      pendingFiles.update(f => [...f, attachment]);

      try {
        // Upload to Dify
        const result = await uploadFileToDify(file);
        
        // Update with upload ID
        pendingFiles.update(f => 
          f.map(pf => 
            pf.id === attachment.id 
              ? { ...pf, uploadFileId: result.id, status: 'uploaded' as const }
              : pf
          )
        );
      } catch (error) {
        console.error('File upload error:', error);
        pendingFiles.update(f => 
          f.map(pf => 
            pf.id === attachment.id 
              ? { ...pf, status: 'error' as const, error: error instanceof Error ? error.message : 'Upload failed' }
              : pf
          )
        );
      }
    }

    isUploadingFiles = false;
    // Reset file input
    target.value = '';
  }

  // Remove a pending file
  function removeFile(fileId: string) {
    pendingFiles.update(f => f.filter(pf => pf.id !== fileId));
  }

  // Get file icon based on type
  function getFileIcon(type: string): string {
    if (type.startsWith('image/')) return '🖼️';
    if (type.includes('pdf')) return '📄';
    if (type.includes('word') || type.includes('document')) return '📝';
    if (type.includes('excel') || type.includes('spreadsheet')) return '📊';
    if (type.includes('text/')) return '📃';
    return '📎';
  }

  // Format file size
  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  async function sendMessage(content: string, context?: string) {
    if (!content.trim() || isStreaming) return;

    // Get current pending files and clear them
    const filesToSend = $pendingFiles.filter(f => f.status === 'uploaded');
    
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: new Date(),
      context,
      files: filesToSend.length > 0 ? [...filesToSend] : undefined
    };

    messages.update(msgs => [...msgs, userMessage]);
    inputValue = '';
    pendingFiles.set([]); // Clear pending files after adding to message
    isStreaming = true;

    // Create assistant message placeholder
    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date()
    };

    messages.update(msgs => [...msgs, assistantMessage]);

    try {
      let accumulatedContent = '';
      
      // Create a throttled update function to reduce render frequency
      // This updates at most every 50ms to prevent glitching
      const updateMessage = throttle(async (content: string) => {
        messages.update(msgs => 
          msgs.map(msg => 
            msg.id === assistantMessage.id 
              ? { ...msg, content }
              : msg
          )
        );
        await tick();
        scrollToBottom();
      }, 50);
      
      // Use the new Dify chat API
      for await (const chunk of streamDifyChat(content, {
        files: filesToSend,
        conversationId: $currentConversationId,
        context: $userContext || undefined
      })) {
        if (chunk.done) {
          // Update conversation ID if returned
          if (chunk.conversationId) {
            currentConversationId.set(chunk.conversationId);
          }
          // Update assistant message with conversation metadata
          messages.update(msgs => 
            msgs.map(msg => 
              msg.id === assistantMessage.id 
                ? { 
                    ...msg, 
                    content: accumulatedContent,
                    conversationId: chunk.conversationId,
                    messageId: chunk.messageId
                  }
                : msg
            )
          );
          break;
        }
        
        if (chunk.content) {
          accumulatedContent += chunk.content;
          updateMessage(accumulatedContent);
        }
      }
      
      // Final update to ensure all content is displayed
      messages.update(msgs => 
        msgs.map(msg => 
          msg.id === assistantMessage.id 
            ? { ...msg, content: accumulatedContent }
            : msg
        )
      );
      scrollToBottom();
    } catch (error) {
      console.error('Chat error:', error);
      
      let errorMessage = $t.chat.error.default;
      if (error instanceof Error) {
        if (error.message.includes('401') || error.message.includes('403')) errorMessage = $t.chat.error.auth;
        else if (error.message.includes('404')) errorMessage = $t.chat.error.notFound;
        else if (error.message.includes('429')) errorMessage = $t.chat.error.rateLimit;
        else if (error.message.includes('Failed to fetch')) errorMessage = $t.chat.error.network;
        else errorMessage = `${$t.chat.error.general}: ${error.message}`;
      }
      
      messages.update(msgs =>  
        msgs.map(msg => 
          msg.id === assistantMessage.id 
            ? { ...msg, content: errorMessage }
            : msg
        )
      );
    } finally {
      isStreaming = false;
    }

    await tick();
    scrollToBottom();
  }

  function handlePromptSelect(event: CustomEvent) {
    const { prompt, context } = event.detail;
    sendMessage(prompt, context);
  }

  function scrollToBottom() {
    if (!chatContainer) return;
    
    // Use RAF for smooth scrolling without blocking
    if (scrollRAF) cancelAnimationFrame(scrollRAF);
    scrollRAF = requestAnimationFrame(() => {
      const isNearBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 100;
      if (isNearBottom) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
      }
      scrollRAF = null;
    });
  }

  // Throttled scroll handler to reduce callback frequency
  const handleScroll = throttle(() => {
    if (!chatContainer) return;
    const currentScrollTop = chatContainer.scrollTop;
    const distanceFromBottom = chatContainer.scrollHeight - currentScrollTop - chatContainer.clientHeight;

    if (distanceFromBottom < 50) {
      isContextRowVisible = true;
    } else if (currentScrollTop < lastScrollTop) {
      isContextRowVisible = false;
    } else {
      isContextRowVisible = true;
    }
    
    lastScrollTop = Math.max(0, currentScrollTop);
  }, 50);

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey && !isStreaming) {
      event.preventDefault();
      sendMessage(inputValue, $userContext || undefined);
    }
  }

  onMount(() => {
    scrollToBottom();
  });
</script>

<div class="flex flex-col h-full relative">
  <!-- Messages Area -->
  <div
    bind:this={chatContainer}
    on:scroll={handleScroll}
    class="flex-1 overflow-y-auto pb-48 hide-scrollbar"
  >
    <div class="w-full max-w-3xl mx-auto px-6 py-6">
      {#if $messages.length === 0}
        <div class="flex flex-col items-center justify-center h-[60vh] opacity-50">
          <div class="w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center mb-4">
            <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <p class="text-lg font-medium text-gray-900 dark:text-gray-100">{$t.chat.howCanIHelp}</p>
          <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{$t.chat.startPrompt}</p>
          
          <!-- Command Palette Hint -->
          <div class="mt-6 flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-500/10 to-purple-500/10 dark:from-blue-500/20 dark:to-purple-500/20 rounded-xl border border-blue-200/50 dark:border-blue-500/30">
            <svg class="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span class="text-sm text-gray-600 dark:text-gray-300">
              {$t.chat.quickCommand?.hint || 'Press'}
              <kbd class="mx-1 px-1.5 py-0.5 text-xs bg-gray-200 dark:bg-gray-700 rounded font-mono">⌘K</kbd>
              {$t.chat.quickCommand?.hintSuffix || 'to quickly create tasks'}
            </span>
          </div>
        </div>
      {/if}

      {#each $messages as message}
        <ChatMessage {message} {isStreaming} />
      {/each}
    </div>
  </div>

  <!-- Floating Input Area -->
  <div class="absolute bottom-0 left-0 right-0 p-6 pt-20 bg-gradient-to-t from-white/50 via-white/20 to-transparent pointer-events-none">
    <div class="max-w-3xl mx-auto space-y-3 pointer-events-auto transition-all duration-300 ease-in-out">
      <!-- Context/Suggestions Row -->
      <div class="transition-all duration-300 ease-in-out {isContextRowVisible ? 'max-h-20 opacity-100 mb-0' : 'max-h-0 opacity-0 -mb-3'} {isOverflowVisible ? 'overflow-visible' : 'overflow-hidden'}">
        <div class="flex items-center gap-3 px-1 min-h-[2rem]">
          <!-- Context Selector -->
          <div class="flex-shrink-0">
            <ContextSelector />
          </div>

          <!-- Prompt Suggestions -->
          {#if $userContext}
            <div class="flex-1 min-w-0 animate-fade-in">
              <PromptSuggestions on:select={handlePromptSelect} />
            </div>
          {/if}
        </div>
      </div>
      
      <!-- Pending Files Preview -->
      {#if $pendingFiles.length > 0}
        <div class="flex flex-wrap gap-2 px-1 mb-2 animate-fade-in">
          {#each $pendingFiles as file (file.id)}
            <div class="flex items-center gap-2 px-3 py-1.5 bg-white/80 dark:bg-gray-800/80 rounded-lg border border-gray-200 dark:border-gray-700 text-sm">
              <span>{getFileIcon(file.type)}</span>
              <span class="max-w-[150px] truncate text-gray-700 dark:text-gray-300">{file.name}</span>
              <span class="text-xs text-gray-500 dark:text-gray-400">({formatFileSize(file.size)})</span>
              {#if file.status === 'uploading'}
                <svg class="w-4 h-4 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              {:else if file.status === 'uploaded'}
                <svg class="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
              {:else if file.status === 'error'}
                <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              {/if}
              <button 
                on:click={() => removeFile(file.id)}
                class="ml-1 p-0.5 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
              >
                <svg class="w-3 h-3 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          {/each}
        </div>
      {/if}

      <!-- Input Bar -->
      <div class="relative backdrop-blur-xl bg-white/60 dark:bg-gray-900/60 border border-white/40 dark:border-white/10 rounded-2xl shadow-lg transition-all focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-500/50">
        <div class="flex items-end gap-2 p-2">
          <!-- Hidden file input -->
          <input
            bind:this={fileInput}
            type="file"
            multiple
            accept="image/*,.pdf,.doc,.docx,.txt,.md,.csv,.xls,.xlsx"
            on:change={handleFileSelect}
            class="hidden"
          />
          
          <!-- File Upload Button -->
          <button
            on:click={() => fileInput?.click()}
            disabled={isStreaming || isUploadingFiles}
            class="p-2 rounded-xl transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Upload files"
          >
            {#if isUploadingFiles}
              <svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            {:else}
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            {/if}
          </button>

          <textarea
            bind:value={inputValue}
            on:keydown={handleKeydown}
            placeholder={isStreaming ? $t.chat.thinking : $t.chat.inputPlaceholder}
            disabled={isStreaming}
            class="flex-1 max-h-32 min-h-[44px] py-2.5 px-2 bg-transparent border-none resize-none text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 text-sm focus:outline-none focus:ring-0"
            rows="1"
            style="height: 44px;"
          />
          
          <div class="flex items-center gap-2 pb-1 pr-1">
            <!-- Record Button -->
            <RecordButton />
            <HighlightButton />

            <!-- Send Button -->
            <button
              on:click={() => sendMessage(inputValue, $userContext || undefined)}
              disabled={!inputValue.trim() || isStreaming}
              class="p-2 rounded-xl transition-all duration-300 {inputValue.trim() && !isStreaming ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-500/30 transform hover:scale-105' : 'bg-black/5 dark:bg-white/5 text-gray-400 dark:text-gray-500 cursor-not-allowed'}"
            >
              {#if isStreaming}
                <svg class="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              {:else}
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              {/if}
            </button>
          </div>
        </div>
      </div>
      
      <div class="text-center">
        <p class="text-[10px] text-gray-400 dark:text-gray-500">
          {$t.chat.aiWarning}
        </p>
      </div>
    </div>
  </div>
</div>