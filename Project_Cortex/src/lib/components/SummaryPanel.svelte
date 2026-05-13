<script lang="ts">
  import { summaryFeed, summaryLoading, type Task } from '$lib/stores/summary';
  import { t } from '$lib/stores/i18n';
  import { marked } from 'marked';

  function sanitizeImageSrcs(html: string): string {
    return html.replace(/<img\s+([^>]*?)src="([^"]*)"([^>]*)>/g, (match, pre, src, post) => {
      if (!src || src === 'undefined' || src === 'null') {
        const altMatch = (pre + post).match(/alt="([^"]*)"/);
        return altMatch?.[1] ? `[Image: ${altMatch[1]}]` : '';
      }
      return match;
    });
  }

  // Memoize markdown parsing to avoid re-parsing on every render
  let lastInsights = '';
  let cachedHtml = '';
  
  function toggleTask(taskId: string) {
    summaryFeed.update(feed => {
      if (!feed) return feed;
      
      return {
        ...feed,
        tasks: feed.tasks.map(task =>
          task.id === taskId ? { ...task, completed: !task.completed } : task
        )
      };
    });
  }

  // Only re-parse when insights actually change
  $: {
    const newInsights = $summaryFeed?.insights || '';
    if (newInsights !== lastInsights) {
      lastInsights = newInsights;
      cachedHtml = newInsights ? sanitizeImageSrcs(marked(newInsights) as string) : '';
    }
  }
  
  $: insightsHtml = cachedHtml;
  $: hasTasks = $summaryFeed?.tasks?.length > 0;
</script>

<div class="flex flex-col h-full">
  <!-- Header -->
  <div class="panel-header">
    <div class="flex items-center gap-2">
      <div class="p-1.5 bg-purple-50 dark:bg-purple-900/20 rounded-lg text-purple-600 dark:text-purple-400">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <h2 class="text-base font-semibold text-gray-900 dark:text-white tracking-tight">{$t.summary.title}</h2>
    </div>
  </div>

  <!-- Content -->
  <div class="flex-1 overflow-y-auto p-5 space-y-6 hide-scrollbar">
    {#if $summaryLoading}
      <!-- Skeleton Loading State -->
      <div class="space-y-6 animate-fade-in">
        <!-- Header Skeleton -->
        <div class="flex items-center justify-between mb-4">
          <div class="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded-full skeleton-loading"></div>
          <div class="h-4 w-4 bg-gray-200 dark:bg-gray-700 rounded-full skeleton-loading"></div>
        </div>
        
        <!-- Content Skeleton Blocks -->
        <div class="space-y-3">
          <div class="h-20 w-full bg-gray-100/50 dark:bg-gray-800/50 rounded-xl skeleton-loading"></div>
          <div class="h-32 w-full bg-gray-100/50 dark:bg-gray-800/50 rounded-xl skeleton-loading"></div>
          <div class="h-24 w-full bg-gray-100/50 dark:bg-gray-800/50 rounded-xl skeleton-loading"></div>
        </div>

        <!-- Loading Status -->
        <div class="flex flex-col items-center justify-center py-8 text-center">
          <div class="relative mb-3">
            <div class="w-10 h-10 border-2 border-blue-100 dark:border-blue-900 rounded-full"></div>
            <div class="absolute inset-0 w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
          <p class="text-xs text-gray-400 dark:text-gray-500 animate-pulse">{$t.summary.loading}</p>
        </div>
      </div>
    {:else if $summaryFeed}
      <!-- Insights Section -->
      <div class="animate-fade-in" style="animation-delay: 0.1s">
        <div class="flex items-center gap-2 mb-3">
          <div class="h-px flex-1 bg-gray-100 dark:bg-gray-800"></div>
          <span class="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest">{$t.summary.keyInsights}</span>
          <div class="h-px flex-1 bg-gray-100 dark:bg-gray-800"></div>
        </div>
        
        <div class="liquid-card p-4">
          <div class="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-li:marker:text-gray-400 break-words">
            {@html insightsHtml}
          </div>
        </div>
      </div>

      <!-- Tasks Section -->
      {#if hasTasks}
        <div class="animate-fade-in" style="animation-delay: 0.2s">
          <div class="flex items-center gap-2 mb-3">
            <div class="h-px flex-1 bg-gray-100 dark:bg-gray-800"></div>
            <span class="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest">{$t.summary.todoItems}</span>
            <div class="h-px flex-1 bg-gray-100 dark:bg-gray-800"></div>
          </div>
          
          <div class="space-y-2">
            {#each $summaryFeed.tasks as task}
              <label class="group flex items-start gap-3 p-3 liquid-card hover:bg-white/60 dark:hover:bg-gray-800/60 transition-all cursor-pointer">
                <div class="relative flex items-center justify-center pt-0.5">
                  <input
                    type="checkbox"
                    checked={task.completed}
                    on:change={() => toggleTask(task.id)}
                    class="peer appearance-none w-4 h-4 border-2 border-gray-300 dark:border-gray-600 rounded bg-transparent checked:bg-blue-600 checked:border-blue-600 transition-all cursor-pointer"
                  />
                  <svg class="absolute w-2.5 h-2.5 text-white opacity-0 peer-checked:opacity-100 transition-opacity pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-gray-700 dark:text-gray-200 leading-snug transition-colors {task.completed ? 'line-through text-gray-400 dark:text-gray-600' : ''}">
                    {task.text}
                  </p>
                </div>
              </label>
            {/each}
          </div>
        </div>
      {/if}
    {:else}
      <div class="flex flex-col items-center justify-center py-12 text-center">
        <div class="relative mb-4">
          <div class="absolute inset-0 bg-blue-100 dark:bg-blue-900/20 rounded-full animate-ping opacity-75"></div>
          <div class="relative w-16 h-16 rounded-full bg-white/20 dark:bg-white/5 flex items-center justify-center border border-white/20 dark:border-white/10 backdrop-blur-sm">
            <svg class="w-8 h-8 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
        </div>
        <h3 class="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">{$t.summary.waitingTitle}</h3>
        <p class="text-xs text-gray-500 dark:text-gray-400 max-w-[200px]">
          {$t.summary.waitingDesc}
        </p>
      </div>
    {/if}
  </div>
</div>

<style>
  /* Fix for long strings in markdown content */
  :global(.prose code) {
    word-break: break-all;
    white-space: pre-wrap;
  }
  
  /* Ensure links also wrap */
  :global(.prose a) {
    word-break: break-all;
  }
</style>
