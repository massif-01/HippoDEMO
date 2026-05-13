<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import { generatedPrompt } from '$lib/stores/userProfile';
  import { t } from '$lib/stores/i18n';
  
  export let open = false;
  
  let promptContent = '';
  let copySuccess = false;
  
  // Subscribe to the generated prompt
  generatedPrompt.subscribe(value => {
    promptContent = value;
  });
  
  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(promptContent);
      copySuccess = true;
      setTimeout(() => copySuccess = false, 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }
  
  function handleClose() {
    open = false;
  }

  function handleBackdropKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      handleClose();
    }
  }
</script>

{#if open && promptContent}
  <div 
    class="fixed inset-0 z-[60] flex items-center justify-center p-4"
    transition:fade={{ duration: 300 }}
  >
    <!-- Backdrop -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div 
      class="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
      on:click={handleClose}
      on:keydown={handleBackdropKeyDown}
      role="button"
      tabindex="-1"
      aria-label="Close modal"
    />
    
    <!-- Modal -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div 
      class="liquid-modal relative max-w-4xl w-full max-h-[85vh] overflow-hidden animate-fade-in"
      on:click|stopPropagation
    >
      <!-- Header -->
      <div class="px-8 py-6 border-b border-gray-200/50 dark:border-gray-800/50 backdrop-blur-md bg-white/20 dark:bg-black/20 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <div class="p-3 bg-white/60 dark:bg-white/10 rounded-2xl backdrop-blur-md shadow-sm">
            <svg class="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300">
              {$t.tasks.promptDisplay.title}
            </h2>
            <p class="mt-1 text-sm text-gray-600 dark:text-gray-400 font-medium">
              {$t.tasks.promptDisplay.subtitle}
            </p>
          </div>
        </div>
        
        <!-- Close button -->
        <button
          on:click={handleClose}
          class="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-black/5 dark:hover:bg-white/10 rounded-xl transition-all duration-200 active:scale-95"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      
      <!-- Content -->
      <div class="px-8 py-8 overflow-y-auto max-h-[60vh] space-y-6">
        <div class="p-6 bg-white/60 dark:bg-black/30 rounded-2xl border border-white/40 dark:border-white/5 backdrop-blur-md shadow-inner">
          <pre class="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 font-mono leading-relaxed">{promptContent}</pre>
        </div>
        
        <!-- Info box -->
        <div class="p-4 bg-blue-50/80 dark:bg-blue-900/20 border border-blue-200/50 dark:border-blue-800/50 rounded-xl backdrop-blur-sm">
          <div class="flex items-start gap-3">
            <div class="p-1.5 bg-blue-100 dark:bg-blue-900/50 rounded-lg">
              <svg class="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            </div>
            <div class="text-sm text-blue-700 dark:text-blue-300 pt-1">
              <p class="font-bold mb-2">{$t.tasks.promptDisplay.howToUse}</p>
              <ul class="space-y-1.5 text-xs font-medium opacity-90">
                <li class="flex items-center gap-2">
                  <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                  {$t.tasks.promptDisplay.step1}
                </li>
                <li class="flex items-center gap-2">
                  <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                  {$t.tasks.promptDisplay.step2}
                </li>
                <li class="flex items-center gap-2">
                  <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                  {$t.tasks.promptDisplay.step3}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Footer -->
      <div class="px-8 py-6 border-t border-gray-200/50 dark:border-gray-800/50 flex justify-between items-center backdrop-blur-md bg-white/20 dark:bg-black/20">
        <button
          on:click={copyToClipboard}
          class="px-5 py-2.5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-xl transition-colors flex items-center gap-2 font-medium text-sm border border-transparent hover:border-blue-100 dark:hover:border-blue-800"
        >
          {#if copySuccess}
            <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            <span class="text-green-600">{$t.tasks.promptDisplay.copied}</span>
          {:else}
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            {$t.tasks.promptDisplay.copy}
          {/if}
        </button>
        
        <button
          on:click={handleClose}
          class="btn-primary px-8 py-2.5 shadow-lg shadow-blue-500/30"
        >
          {$t.tasks.promptDisplay.start}
        </button>
      </div>
    </div>
  </div>
{:else if open && !promptContent}
  <!-- Loading state -->
  <div 
    class="fixed inset-0 z-[60] flex items-center justify-center p-4"
    transition:fade={{ duration: 300 }}
  >
    <div class="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity" />
    <div class="liquid-modal relative p-8 animate-fade-in">
      <div class="flex flex-col items-center gap-6">
        <div class="relative">
          <div class="w-16 h-16 rounded-full border-4 border-blue-100 dark:border-blue-900/30"></div>
          <div class="absolute inset-0 w-16 h-16 rounded-full border-4 border-blue-600 border-t-transparent animate-spin"></div>
        </div>
        <p class="text-lg font-medium text-gray-700 dark:text-gray-300">{$t.tasks.promptDisplay.loading}</p>
      </div>
    </div>
  </div>
{/if}
