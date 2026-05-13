<script lang="ts">
  import { 
    userProfile, 
    contentBgOptions, 
    infoSourceOptions, 
    occupationTypeOptions, 
    summaryModeOptions,
    generatedPrompt,
    type UserProfile
  } from '$lib/stores/userProfile';
  import { t, currentLanguage, translateProfileForBackend } from '$lib/stores/i18n';
  
  export let open = false;
  export let onPromptGenerated = () => {}; // Callback when prompt is generated
  
  let profile: UserProfile = {
    content_bg: '',
    info_source: '',
    occupation_type: '',
    personal_focus: '',
    summary_mode: ''
  };
  
  let loading = false;
  let error = '';
  let success = false;
  
  // Subscribe to userProfile store
  userProfile.subscribe(value => {
    profile = { ...value };
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
  
  async function handleUpdate() {
    if (!isFormValid) return;
    
    loading = true;
    error = '';
    success = false;
    
    try {
      // Update the store with the form data
      userProfile.set(profile);
      
      // Translate profile values to current language for backend
      const translatedProfile = translateProfileForBackend(profile, $currentLanguage);
      
      // Send updated profile to prompt_generator API
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
      
      // info_storage API removed - profile updates stored locally only
      
      // Update the generated prompt (it's already a string)
      generatedPrompt.set(promptText);
      
      success = true;
      
      // Auto-close after successful update and show prompt modal
      setTimeout(() => {
        open = false;
        success = false;
        // Trigger callback to show the prompt modal
        onPromptGenerated();
      }, 1500);
      
    } catch (err) {
      error = err instanceof Error ? err.message : 'An error occurred';
      console.error('Error updating user profile:', err);
    } finally {
      loading = false;
    }
  }
  
  function handleClose() {
    open = false;
    error = '';
    success = false;
  }

  function handleBackdropKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      handleClose();
    }
  }
</script>

{#if open}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
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
    <div class="liquid-modal relative max-w-2xl w-full max-h-[90vh] overflow-hidden animate-fade-in">
      <!-- Header -->
      <div class="px-8 py-6 border-b border-gray-200/50 dark:border-gray-800/50 flex items-center justify-between backdrop-blur-md bg-white/20 dark:bg-black/20">
        <div>
          <h2 class="text-2xl font-bold text-gray-900 dark:text-white bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300">
            {$t.settings.title}
          </h2>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400 font-medium">
            {$t.settings.subtitle}
          </p>
        </div>
        
        <button
          on:click={handleClose}
          class="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-black/5 dark:hover:bg-white/10 rounded-xl transition-all duration-200 active:scale-95"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      
      <!-- Form Content -->
      <div class="px-8 py-8 overflow-y-auto max-h-[60vh] space-y-6">
        <form on:submit|preventDefault={handleUpdate} class="space-y-6">
          <!-- 录制背景 -->
          <div class="group">
            <label for="content_bg_edit" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              {$t.onboarding.contentBg}
            </label>
            <div class="relative">
              <select
                id="content_bg_edit"
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
            <label for="info_source_edit" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              {$t.onboarding.infoSource}
            </label>
            <div class="relative">
              <select
                id="info_source_edit"
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
            <label for="occupation_type_edit" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              {$t.onboarding.occupationType}
            </label>
            <div class="relative">
              <select
                id="occupation_type_edit"
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
            <label for="personal_focus_edit" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              {$t.onboarding.personalFocus}
              <span class="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400 bg-black/5 dark:bg-white/10 px-2 py-0.5 rounded-full">
                {remainingChars} {$t.onboarding.remainingChars}
              </span>
            </label>
            <textarea
              id="personal_focus_edit"
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
            <label for="summary_mode_edit" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              {$t.onboarding.summaryMode}
            </label>
            <div class="relative">
              <select
                id="summary_mode_edit"
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
            <div class="p-4 bg-red-50/80 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl backdrop-blur-sm animate-fade-in">
              <p class="text-sm font-medium text-red-600 dark:text-red-400 flex items-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                {error}
              </p>
            </div>
          {/if}
          
          {#if success}
            <div class="p-4 bg-green-50/80 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl backdrop-blur-sm animate-fade-in">
              <p class="text-sm font-medium text-green-600 dark:text-green-400 flex items-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                {$t.settings.success}
              </p>
            </div>
          {/if}
        </form>
      </div>
      
      <!-- Footer -->
      <div class="px-8 py-6 border-t border-gray-200/50 dark:border-gray-800/50 flex justify-end gap-4 backdrop-blur-md bg-white/20 dark:bg-black/20">
        <button
          type="button"
          on:click={handleClose}
          class="px-6 py-2.5 btn-secondary"
        >
          {$t.onboarding.cancel}
        </button>
        
        <button
          on:click={handleUpdate}
          disabled={!isFormValid || loading}
          class="px-8 py-2.5 btn-primary flex items-center gap-2 shadow-lg shadow-blue-500/30"
        >
          {#if loading}
            <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {$t.settings.updating}
          {:else}
            {$t.settings.update}
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
