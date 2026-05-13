<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { 
    userProfile, 
    contentBgOptions, 
    infoSourceOptions, 
    occupationTypeOptions, 
    summaryModeOptions,
    onboardingCompleted,
    generatedPrompt,
    type UserProfile
  } from '$lib/stores/userProfile';
  import { t, toggleLanguage, currentLanguage, translateProfileForBackend } from '$lib/stores/i18n';
  
  export let open = false;
  
  let profile: UserProfile = {
    content_bg: '',
    info_source: '',
    occupation_type: '',
    personal_focus: '',
    summary_mode: ''
  };
  
  let loading = false;
  let error = '';
  let showPromptModal = false;
  let promptTemplate = '';
  let copySuccess = false;
  
  // Subscribe to userProfile store
  userProfile.subscribe(value => {
    profile = value;
  });
  
  // Subscribe to generated prompt
  let previousPromptLength = 0;
  generatedPrompt.subscribe(value => {
    promptTemplate = value;
    
    // Auto-show modal if a new prompt is generated (not on initial load)
    if (value && value.length > 0 && previousPromptLength === 0 && !showPromptModal) {
      showPromptModal = true;
    }
    previousPromptLength = value ? value.length : 0;
  });
  
  // Character counter for personal focus
  $: remainingChars = 200 - profile.personal_focus.length;
  
  // Form validation
  $: isFormValid = !!(
    profile.content_bg &&
    profile.info_source &&
    profile.occupation_type &&
    profile.personal_focus &&
    profile.summary_mode &&
    profile.personal_focus.length <= 200
  );
  
  async function handleSubmit() {
    if (!isFormValid) return;
    
    loading = true;
    error = '';
    
    try {
      // Update the store with the form data
      userProfile.set(profile);
      
      // Translate profile values to current language for backend
      const translatedProfile = translateProfileForBackend(profile, $currentLanguage);
      
      // Send to prompt_generator API
      const promptResponse = await fetch('http://localhost:8000/api/prompt_generator', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(translatedProfile)
      });
      
      if (!promptResponse.ok) {
        throw new Error('Failed to generate prompt');
      }
      
      // The backend returns a plain text string, not JSON
      const promptText = await promptResponse.text();
      console.log('Prompt generator response received');
      console.log('Response length:', promptText.length);
      console.log('Response content:', promptText);
      
      if (!promptText || promptText.trim() === '') {
        console.error('Empty prompt received from backend');
        throw new Error('Empty prompt received from backend');
      }
      
      // info_storage API removed - profile is stored locally only
      
      // Store the generated prompt (it's already a string)
      console.log('Setting generated prompt:', promptText);
      
      // Ensure we have a prompt to display
      if (!promptText || promptText.trim() === '') {
        console.error('Warning: Empty or invalid prompt received, using fallback');
        promptTemplate = $t.onboarding.fallbackTemplate;
      } else {
        promptTemplate = promptText;
      }
      
      // Update the store
      generatedPrompt.set(promptTemplate);
      
      // Mark onboarding as completed
      onboardingCompleted.set(true);
      
      // Store in localStorage for persistence
      if (typeof window !== 'undefined') {
        localStorage.setItem('onboardingCompleted', 'true');
      }
      
      // Close the onboarding modal first
      open = false;
      
      // Force the prompt display modal to show after a small delay
      // This ensures the first modal is fully closed before opening the second
      await new Promise(resolve => setTimeout(resolve, 150));
      
      // Now show the prompt display modal
      showPromptModal = true;
      console.log('Prompt modal is now visible:', showPromptModal);
      console.log('Prompt template content:', promptTemplate?.substring(0, 100) + '...');
      
    } catch (err) {
      error = err instanceof Error ? err.message : 'An error occurred';
      console.error('Error submitting user profile:', err);
    } finally {
      loading = false;
    }
  }
  
  function handleClose() {
    if (!$onboardingCompleted) {
      // Don't allow closing if onboarding not completed
      return;
    }
    open = false;
  }
</script>

{#if open}
  <div 
    class="fixed inset-0 z-50 flex items-center justify-center p-4"
    transition:fade={{ duration: 200 }}
  >
    <!-- Backdrop -->
    <button
      type="button"
      class="absolute inset-0 bg-black/50 backdrop-blur-sm cursor-default"
      on:click={handleClose}
      aria-label="Close modal"
      tabindex="-1"
    />
    
    <!-- Modal -->
    <div 
      class="relative bg-white dark:bg-gray-900 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden"
      transition:fly={{ y: 20, duration: 300 }}
    >
      <!-- Header -->
      <div class="px-6 py-5 border-b border-gray-200 dark:border-gray-800 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/10 dark:to-indigo-900/10">
        <div class="flex items-start gap-3">
          <div class="p-2 bg-blue-100 dark:bg-blue-900/50 rounded-lg">
            <svg class="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div class="flex-1">
            <div class="flex items-center justify-between">
              <h2 class="text-2xl font-bold text-gray-900 dark:text-white">
                {$t.onboarding.welcome}
              </h2>
              <button
                on:click={toggleLanguage}
                class="p-2 rounded-full bg-white/50 dark:bg-black/20 hover:bg-white/80 dark:hover:bg-black/40 transition-colors border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300"
                title={$t.onboarding.switchLang}
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                </svg>
              </button>
            </div>
            <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
              {$t.onboarding.subtitle}
            </p>
            {#if !$onboardingCompleted}
              <div class="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 font-medium">
                <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                </svg>
                {$t.onboarding.required}
              </div>
            {/if}
          </div>
        </div>
      </div>
      
      <!-- Progress Indicator -->
      <div class="px-6 pt-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-medium text-gray-500 dark:text-gray-400">{$t.onboarding.step1}</span>
          <span class="text-xs text-gray-500 dark:text-gray-400">{$t.onboarding.step1Title}</span>
        </div>
        <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
          <div class="bg-blue-600 h-2 rounded-full" style="width: 50%"></div>
        </div>
      </div>
      
      <!-- Form Content -->
      <div class="px-6 py-4 overflow-y-auto max-h-[55vh]">
        <form on:submit|preventDefault={handleSubmit} class="space-y-6">
          <!-- 录制背景 -->
          <div class="group">
            <label for="content_bg" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 transition-colors group-focus-within:text-blue-600 dark:group-focus-within:text-blue-400">
              {$t.onboarding.contentBg}
            </label>
            <div class="relative">
            <select
              id="content_bg"
              bind:value={profile.content_bg}
                class="input-field appearance-none cursor-pointer hover:bg-white/60 dark:hover:bg-black/40"
              required
            >
              <option value="">{$t.onboarding.select}</option>
              {#each contentBgOptions as option}
                <option value={option}>{$t.options.contentBg[option] || option}</option>
              {/each}
            </select>
              <div class="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none text-gray-500">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
              </div>
            </div>
          </div>
          
          <!-- 信息来源 -->
          <div class="group">
            <label for="info_source" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 transition-colors group-focus-within:text-blue-600 dark:group-focus-within:text-blue-400">
              {$t.onboarding.infoSource}
            </label>
            <div class="relative">
            <select
              id="info_source"
              bind:value={profile.info_source}
                class="input-field appearance-none cursor-pointer hover:bg-white/60 dark:hover:bg-black/40"
              required
            >
              <option value="">{$t.onboarding.select}</option>
              {#each infoSourceOptions as option}
                <option value={option}>{$t.options.infoSource[option] || option}</option>
              {/each}
            </select>
              <div class="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none text-gray-500">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
              </div>
            </div>
          </div>
          
          <!-- 职业类型 -->
          <div class="group">
            <label for="occupation_type" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 transition-colors group-focus-within:text-blue-600 dark:group-focus-within:text-blue-400">
              {$t.onboarding.occupationType}
            </label>
            <div class="relative">
            <select
              id="occupation_type"
              bind:value={profile.occupation_type}
                class="input-field appearance-none cursor-pointer hover:bg-white/60 dark:hover:bg-black/40"
              required
            >
              <option value="">{$t.onboarding.select}</option>
              {#each occupationTypeOptions as option}
                <option value={option}>{$t.options.occupationType[option] || option}</option>
              {/each}
            </select>
              <div class="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none text-gray-500">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
              </div>
            </div>
          </div>
          
          <!-- 个人聚焦 -->
          <div class="group">
            <label for="personal_focus" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 transition-colors group-focus-within:text-blue-600 dark:group-focus-within:text-blue-400">
              {$t.onboarding.personalFocus}
              <span class="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400 bg-black/5 dark:bg-white/10 px-2 py-0.5 rounded-full">
                {remainingChars} {$t.onboarding.remainingChars}
              </span>
            </label>
            <textarea
              id="personal_focus"
              bind:value={profile.personal_focus}
              maxlength="200"
              rows="3"
              class="input-field resize-none hover:bg-white/60 dark:hover:bg-black/40"
              placeholder={$t.onboarding.placeholderFocus}
              required
            />
          </div>
          
          <!-- 总结深度 -->
          <div class="group">
            <label for="summary_mode" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 transition-colors group-focus-within:text-blue-600 dark:group-focus-within:text-blue-400">
              {$t.onboarding.summaryMode}
            </label>
            <div class="relative">
              <select
                id="summary_mode"
                bind:value={profile.summary_mode}
                class="input-field appearance-none cursor-pointer hover:bg-white/60 dark:hover:bg-black/40"
                required
              >
                <option value="">{$t.onboarding.select}</option>
                {#each summaryModeOptions as option}
                  <option value={option}>{$t.options.summaryMode[option] || option}</option>
                {/each}
              </select>
              <div class="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none text-gray-500">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
              </div>
            </div>
          </div>

          
          {#if error}
            <div class="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p class="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          {/if}
        </form>
      </div>
      
      <!-- Footer -->
      <div class="px-6 py-4 border-t border-gray-200 dark:border-gray-800 flex justify-end gap-3">
        {#if $onboardingCompleted}
          <button
            type="button"
            on:click={handleClose}
            class="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          >
            {$t.onboarding.cancel}
          </button>
        {/if}
        
        <button
          on:click={handleSubmit}
          disabled={!isFormValid || loading}
          class="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
        >
          {#if loading}
            <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {$t.onboarding.generating}
          {:else}
            {$t.onboarding.start}
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Prompt Display Modal -->
{#if showPromptModal && promptTemplate}
  <div 
    class="fixed inset-0 z-[100] flex items-center justify-center p-4"
    transition:fade={{ duration: 200 }}
  >
    <!-- Backdrop -->
    <button
      type="button"
      class="absolute inset-0 bg-black/60 backdrop-blur-sm cursor-default"
      on:click={() => showPromptModal = false}
      aria-label="Close prompt modal"
      tabindex="-1"
    />
    
    <!-- Modal -->
    <div 
      class="relative bg-white dark:bg-gray-900 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden ring-2 ring-blue-500/20"
      transition:fly={{ y: 20, duration: 400, delay: 100 }}
    >
      <!-- Header -->
      <div class="px-6 py-5 border-b border-gray-200 dark:border-gray-800 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20">
        <!-- Progress Indicator -->
        <div class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-medium text-gray-500 dark:text-gray-400">{$t.onboarding.step2}</span>
            <span class="text-xs text-gray-500 dark:text-gray-400">{$t.onboarding.step2Title}</span>
          </div>
          <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div class="bg-green-600 h-2 rounded-full transition-all duration-500" style="width: 100%"></div>
          </div>
        </div>
        
        <div class="flex items-center gap-3">
          <div>
            <h2 class="text-xl font-bold text-gray-900 dark:text-white">
              {$t.onboarding.templateGenerated}
            </h2>
            <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
              {$t.onboarding.templateSubtitle}
            </p>
          </div>
        </div>
      </div>
      
      <!-- Content -->
      <div class="px-6 py-6 overflow-y-auto max-h-[55vh]">
        <!-- Info banner -->
        <div class="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-start gap-2">
          <svg class="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p class="text-sm text-green-700 dark:text-green-300">
            {$t.onboarding.successMessage}
          </p>
        </div>
        
        <!-- Prompt template display -->
        <div class="p-5 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-850 rounded-xl border border-gray-200 dark:border-gray-700">
          <pre class="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 font-mono leading-relaxed">{promptTemplate || $t.onboarding.fallbackTemplate}</pre>
        </div>
      </div>
      
      <!-- Footer -->
      <div class="px-6 py-4 border-t border-gray-200 dark:border-gray-800 flex justify-between items-center">
        <button
          on:click={async () => {
            try {
              await navigator.clipboard.writeText(promptTemplate);
              copySuccess = true;
              setTimeout(() => copySuccess = false, 2000);
            } catch (err) {
              console.error('Failed to copy:', err);
            }
          }}
          class="px-4 py-2 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors flex items-center gap-2"
        >
          {#if copySuccess}
            <svg class="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            {$t.onboarding.copied}
          {:else}
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            {$t.onboarding.copy}
          {/if}
        </button>
        
        <button
          on:click={() => showPromptModal = false}
          class="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          {$t.onboarding.start}
        </button>
      </div>
    </div>
  </div>
{/if}
