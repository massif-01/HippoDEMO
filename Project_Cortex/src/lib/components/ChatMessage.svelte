<script lang="ts">
  import type { Message, FileAttachment } from '$lib/stores/chat';
  import { messages } from '$lib/stores/chat';
  import { apiConfig } from '$lib/stores/config';
  import { marked } from 'marked';
  import { t } from '$lib/stores/i18n';
  
  export let message: Message;
  export let isStreaming: boolean = false;

  function sanitizeImageSrcs(html: string): string {
    return html.replace(/<img\s+([^>]*?)src="([^"]*)"([^>]*)>/g, (match, pre, src, post) => {
      if (!src || src === 'undefined' || src === 'null') {
        const altMatch = (pre + post).match(/alt="([^"]*)"/);
        return altMatch?.[1] ? `[Image: ${altMatch[1]}]` : '';
      }
      return match;
    });
  }

  let lastContent = '';
  let cachedHtml = '';
  
  // Only re-parse markdown when content actually changes
  $: if (message.content !== lastContent) {
    lastContent = message.content;
    cachedHtml = message.content ? sanitizeImageSrcs(marked(message.content) as string) : '';
  }
  
  $: htmlContent = cachedHtml;
  $: isCurrentlyStreaming = isStreaming && message.role === 'assistant' && message.content === '';

  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(message.content);
      console.log('Copied to clipboard');
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }

  function retryMessage() {
    const messageIndex = $messages.findIndex(m => m.id === message.id);
    if (messageIndex > 0) {
      const previousMessage = $messages[messageIndex - 1];
      if (previousMessage.role === 'user') {
        messages.update(msgs => msgs.filter(m => m.id !== message.id));
        console.log('Retry message:', previousMessage.content);
      }
    }
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
</script>

<div class="group relative mb-6 animate-fade-in">
  <div class="flex gap-4 {message.role === 'user' ? 'flex-row-reverse' : ''}">
    <!-- Avatar -->
    <div class="flex-shrink-0 mt-1">
      {#if message.role === 'user'}
        <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-gray-900 to-black dark:from-white dark:to-gray-200 flex items-center justify-center text-white dark:text-black text-xs font-bold shadow-lg shadow-black/10">
          U
        </div>
      {:else}
        <div class="w-8 h-8 rounded-xl bg-white/50 dark:bg-white/10 border border-white/20 dark:border-white/10 flex items-center justify-center shadow-sm backdrop-blur-sm">
          <svg class="w-5 h-5 text-gray-700 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
      {/if}
    </div>

    <!-- Message Content -->
    <div class="flex-1 max-w-[85%] min-w-0">
      <!-- Name and Time -->
      <div class="flex items-center gap-2 mb-1 {message.role === 'user' ? 'justify-end' : ''}">
        <span class="text-xs font-semibold text-gray-900 dark:text-gray-100">
          {message.role === 'user' ? $t.chat.message.you : $apiConfig.model || $t.chat.message.assistant}
        </span>
        <span class="text-[10px] text-gray-400">
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
      
      <!-- Bubble -->
      <div class="relative group/bubble">
        <div class="
          px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm backdrop-blur-md
          {message.role === 'user' 
            ? 'bg-gradient-to-br from-blue-600 to-blue-700 text-white rounded-tr-sm shadow-blue-500/20' 
            : 'liquid-card text-gray-900 dark:text-gray-100 rounded-tl-sm'}
        ">
          <!-- File Attachments -->
          {#if message.files && message.files.length > 0}
            <div class="mb-2 pb-2 border-b border-white/20">
              <div class="flex flex-wrap gap-1.5">
                {#each message.files as file}
                  <div class="flex items-center gap-1.5 px-2 py-1 bg-white/10 rounded-lg text-xs">
                    <span>{getFileIcon(file.type)}</span>
                    <span class="max-w-[100px] truncate">{file.name}</span>
                    <span class="opacity-70">({formatFileSize(file.size)})</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Context Indicator -->
          {#if message.context}
            <div class="mb-2 pb-2 border-b border-white/20 text-xs flex items-center gap-1.5 opacity-90">
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
              {$t.chat.message.usingContext}
            </div>
          {/if}

          <!-- Message Text -->
          {#if message.content}
            <div class="prose prose-sm dark:prose-invert max-w-none {message.role === 'user' ? 'prose-invert' : ''}" 
                 style="will-change: contents; contain: layout style;">
              {@html htmlContent}
            </div>
          {:else if message.role === 'assistant' && isStreaming}
            <div class="flex items-center gap-2">
              <div class="flex space-x-1">
                <div class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0s"></div>
                <div class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                <div class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
              </div>
            </div>
          {/if}
        </div>

        <!-- Action Buttons (Floating) -->
        {#if message.role === 'assistant' && message.content && !isStreaming}
          <div class="absolute -bottom-6 left-0 flex items-center gap-1 opacity-0 group-hover/bubble:opacity-100 transition-all duration-200">
            <button 
              on:click={copyToClipboard}
              class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors" 
              title={$t.chat.message.copy}
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </button>
            <button 
              on:click={retryMessage}
              class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors" 
              title={$t.chat.message.retry}
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>