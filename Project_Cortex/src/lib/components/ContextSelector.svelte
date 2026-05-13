<script lang="ts">
  import { recordingContexts, userContext, type RecordingContext } from '$lib/stores/chat';
  import { onMount } from 'svelte';
  import { t } from '$lib/stores/i18n';
  
  let showContextMenu = false;
  
  function toggleContext(contextId: string) {
    recordingContexts.update(contexts => 
      contexts.map(ctx => 
        ctx.id === contextId ? { ...ctx, selected: !ctx.selected } : ctx
      )
    );
    updateCombinedContext();
  }
  
  function selectAllContexts() {
    recordingContexts.update(contexts => 
      contexts.map(ctx => ({ ...ctx, selected: true }))
    );
    updateCombinedContext();
  }
  
  function clearAllContexts() {
    recordingContexts.update(contexts => 
      contexts.map(ctx => ({ ...ctx, selected: false }))
    );
    updateCombinedContext();
  }
  
  function updateCombinedContext() {
    const selected = $recordingContexts.filter(ctx => ctx.selected);
    if (selected.length === 0) {
      $userContext = '';
    } else if (selected.length === 1) {
      $userContext = selected[0].content;
    } else {
      // Combine multiple contexts
      $userContext = selected
        .map((ctx, i) => `## 录制 ${i + 1} - ${ctx.timestamp.toLocaleString()}\n\n${ctx.content}`)
        .join('\n\n---\n\n');
    }
  }
  
  function deleteContext(contextId: string) {
    recordingContexts.update(contexts => 
      contexts.filter(ctx => ctx.id !== contextId)
    );
    updateCombinedContext();
  }
  
  $: selectedCount = $recordingContexts.filter(ctx => ctx.selected).length;
  $: hasContexts = $recordingContexts.length > 0;
</script>

{#if hasContexts}
  <div class="relative">
    <button
      on:click={() => showContextMenu = !showContextMenu}
      class="flex items-center gap-2 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <span class="font-medium">
        {selectedCount}
      </span>
      <svg class="w-3 h-3 transition-transform {showContextMenu ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>
    
    {#if showContextMenu}
      <div class="absolute bottom-full mb-2 left-0 w-72 bg-white/90 dark:bg-gray-900/90 border border-white/40 dark:border-white/10 rounded-xl shadow-xl z-50 backdrop-blur-xl animate-slideUp">
        <div class="p-3 border-b border-gray-200/50 dark:border-gray-700/50">
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{$t.chat.contextSelector.title}</h3>
            <button
              on:click={() => showContextMenu = false}
              class="p-1 hover:bg-black/5 dark:hover:bg-white/10 rounded transition-colors"
            >
              <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="flex gap-2">
            <button
              on:click={selectAllContexts}
              class="text-xs px-2 py-1 bg-blue-100/80 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors font-medium"
            >
              {$t.chat.contextSelector.selectAll}
            </button>
            <button
              on:click={clearAllContexts}
              class="text-xs px-2 py-1 bg-gray-100/80 dark:bg-gray-700/50 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors font-medium"
            >
              {$t.chat.contextSelector.clearAll}
            </button>
          </div>
        </div>
        
        <div class="max-h-60 overflow-y-auto p-2 hide-scrollbar">
          {#each $recordingContexts as context}
            <div class="flex items-start gap-2 p-2 hover:bg-black/5 dark:hover:bg-white/10 rounded transition-colors group">
              <input
                type="checkbox"
                checked={context.selected}
                on:change={() => toggleContext(context.id)}
                class="mt-0.5 w-4 h-4 text-blue-600 bg-transparent border-gray-400 rounded focus:ring-blue-500 cursor-pointer"
              />
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-medium text-gray-700 dark:text-gray-200">
                    {context.timestamp.toLocaleString()}
                  </span>
                  <button
                    on:click={() => deleteContext(context.id)}
                    class="p-0.5 hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-600 dark:hover:text-red-400 rounded transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
                <p class="text-xs text-gray-600 dark:text-gray-400 truncate mt-1" title={context.content}>
                  {context.content.substring(0, 60)}{context.content.length > 60 ? '...' : ''}
                </p>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
{/if}
