<script lang="ts">
  import { promptSuggestions, promptSuggestionsLoading, userContext } from '$lib/stores/chat';
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { t } from '$lib/stores/i18n';

  const dispatch = createEventDispatcher();
  
  let showDropdown = false;
  let selectedPrompt = '';
  let dropdownRef: HTMLDivElement;

  function selectPrompt(prompt: string) {
    selectedPrompt = prompt;
    showDropdown = false;
    dispatch('select', {
      prompt,
      context: $userContext
    });
  }

  function toggleDropdown() {
    showDropdown = !showDropdown;
  }

  // Use event delegation for better performance
  function handleClickOutside(event: MouseEvent) {
    if (showDropdown && dropdownRef && !dropdownRef.contains(event.target as Node)) {
      showDropdown = false;
    }
  }

  // Only add listener when dropdown is shown
  $: if (showDropdown) {
    document.addEventListener('click', handleClickOutside, { passive: true, capture: true });
  } else {
    document.removeEventListener('click', handleClickOutside, { capture: true });
  }
  
  onDestroy(() => {
    document.removeEventListener('click', handleClickOutside, { capture: true });
  });

  // Icons for suggestions - frozen array
  const icons = Object.freeze(['💡', '🔍', '📝', '🎯', '⚡']);
  
  // Pre-computed values
  $: useDropdown = $promptSuggestions.length > 3;
  $: hasSuggestions = $promptSuggestions.length > 0;
</script>

{#if $promptSuggestionsLoading}
  <!-- Elegant Loading State -->
  <div class="flex gap-2 overflow-x-auto pb-1 hide-scrollbar">
    <div class="liquid-card flex items-center gap-3 px-4 py-2.5 min-w-[240px] relative overflow-hidden border-blue-200/50 dark:border-blue-700/30">
      <!-- Subtle Animated Background -->
      <div class="absolute inset-0 bg-gradient-to-r from-blue-50/0 via-blue-50/50 dark:via-blue-900/20 to-blue-50/0 animate-shimmer-slide"></div>
      
      <!-- Icon with Pulse -->
      <div class="relative flex-shrink-0">
        <div class="absolute inset-0 bg-blue-400/20 rounded-full animate-ping"></div>
        <div class="relative z-10 text-lg">✨</div>
      </div>
      
      <!-- Text & Dots -->
      <div class="flex items-center gap-1 z-10">
        <span class="text-sm font-medium text-gray-700 dark:text-gray-200">
          {$t.chat.promptSuggestions.loading}
        </span>
        <div class="flex gap-1 items-center mt-1">
          <span class="w-1 h-1 bg-gray-500 dark:bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
          <span class="w-1 h-1 bg-gray-500 dark:bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
          <span class="w-1 h-1 bg-gray-500 dark:bg-gray-400 rounded-full animate-bounce"></span>
        </div>
      </div>
    </div>
  </div>
{:else if hasSuggestions}
  {#if useDropdown}
    <!-- Dropdown version for many suggestions -->
    <div class="relative" bind:this={dropdownRef}>
      <button
        on:click={toggleDropdown}
        class="flex items-center gap-2 px-3 py-2 liquid-card w-full text-left hover:bg-white/60 dark:hover:bg-gray-800/60"
      >
        <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <span class="text-sm text-gray-700 dark:text-gray-300 flex-1">
          {selectedPrompt || $t.chat.promptSuggestions.select}
        </span>
        <svg class="w-4 h-4 text-gray-400 transition-transform {showDropdown ? '' : 'rotate-180'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      {#if showDropdown}
        <div class="absolute bottom-full mb-1 left-0 right-0 bg-white/90 dark:bg-gray-900/90 border border-white/40 dark:border-white/10 rounded-xl shadow-xl z-50 max-h-60 overflow-y-auto animate-slideUp backdrop-blur-xl">
          {#each $promptSuggestions as suggestion, i}
            <button
              on:click={() => selectPrompt(suggestion.text)}
              class="flex items-center gap-2 px-3 py-2.5 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors w-full text-left border-b border-gray-100/50 dark:border-gray-800/50 last:border-0"
            >
              <span class="text-base">{icons[i % icons.length]}</span>
              <span class="text-sm font-medium text-gray-800 dark:text-gray-200">
                {suggestion.text}
              </span>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <!-- Card version for few suggestions -->
    <div class="flex gap-2 overflow-x-auto pb-1" style="scrollbar-width: none; -ms-overflow-style: none;">
      {#each $promptSuggestions as suggestion, i}
        <button
          on:click={() => selectPrompt(suggestion.text)}
          class="group flex items-center gap-2 px-3 py-2 liquid-card hover:bg-white/60 dark:hover:bg-gray-800/60 hover:shadow-md transition-all whitespace-nowrap flex-shrink-0"
        >
          <span class="text-base">{icons[i % icons.length]}</span>
          <span class="text-xs text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100">
            {suggestion.text}
          </span>
        </button>
      {/each}
    </div>
  {/if}
{/if}

<style>
  /* Hide scrollbar for Chrome, Safari and Opera */
  div::-webkit-scrollbar {
    display: none;
  }

  @keyframes shimmer-slide {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }

  .animate-shimmer-slide {
    animation: shimmer-slide 2s infinite linear;
  }
</style>