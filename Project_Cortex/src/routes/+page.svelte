<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import ChatPanel from '$lib/components/ChatPanel.svelte';
  import SummaryPanel from '$lib/components/SummaryPanel.svelte';
  import TaskPanel from '$lib/components/TaskPanel.svelte';
  import RecordingIndicator from '$lib/components/RecordingIndicator.svelte';
  import Settings from '$lib/components/Settings.svelte';
  import OnboardingModal from '$lib/components/OnboardingModal.svelte';
  import ProfileSettings from '$lib/components/ProfileSettings.svelte';
  import PromptDisplayModal from '$lib/components/PromptDisplayModal.svelte';
  import CommandPalette from '$lib/components/CommandPalette.svelte';
  import SkillsPanel from '$lib/components/SkillsPanel.svelte';
  import { onboardingCompleted, generatedPrompt } from '$lib/stores/userProfile';
  import { skillsCount } from '$lib/stores/skills';
  import { t } from '$lib/stores/i18n';

  let settingsOpen = false;
  let profileSettingsOpen = false;
  let onboardingOpen = false;
  let promptDisplayOpen = false;
  let commandPaletteOpen = false;
  let skillsPanelOpen = false;
  let taskNotification = '';
  
  // Development mode flag - set to false in production
  const DEV_MODE = true;
  
  // Items to clear in dev mode - defined once
  const DEV_STORAGE_KEYS = [
    'onboardingCompleted',
    'generatedPrompt',
    'userProfile',
    'tasks',
    'agentTasks',
    'recordingContexts',
    'chatMessages'
  ];
  
  // Check if we have a stored prompt - use reactive statement instead of subscription
  $: hasPrompt = $generatedPrompt && $generatedPrompt.trim() !== '';
  
  // Subscription cleanup
  let unsubscribeOnboarding: (() => void) | undefined;
  
  // Check if user has completed onboarding on mount
  onMount(() => {
    if (DEV_MODE) {
      // Clear localStorage efficiently using batch operation
      console.log('=== DEV MODE: Clearing localStorage ===');
      DEV_STORAGE_KEYS.forEach(key => localStorage.removeItem(key));
      
      onboardingCompleted.set(false);
      onboardingOpen = true;
    } else {
      // Production mode - check storage once
      const hasCompletedOnboarding = localStorage.getItem('onboardingCompleted');
      const storedPrompt = localStorage.getItem('generatedPrompt');
      
      if (!hasCompletedOnboarding || !storedPrompt) {
        onboardingOpen = true;
        if (!storedPrompt && hasCompletedOnboarding) {
          localStorage.removeItem('onboardingCompleted');
          onboardingCompleted.set(false);
        }
      } else {
        onboardingCompleted.set(true);
      }
    }
    
    // Subscribe to onboarding completion for persistence
    unsubscribeOnboarding = onboardingCompleted.subscribe(value => {
      if (value) {
        localStorage.setItem('onboardingCompleted', 'true');
      }
    });
  });
  
  onDestroy(() => {
    unsubscribeOnboarding?.();
  });
  
  function handleTaskCreated(event: CustomEvent<{ count: number }>) {
    const count = event.detail.count;
    taskNotification = count === 1 
      ? $t.commandPalette?.taskCreated || 'Task created'
      : `${count} ${$t.commandPalette?.tasksCreated || 'tasks created'}`;
    
    // Clear notification after 3 seconds
    setTimeout(() => {
      taskNotification = '';
    }, 3000);
  }
  
  function handleAgentCompleted(event: CustomEvent<{ query: string; response: string; conversationId: string }>) {
    // Optional: Handle agent completion events (e.g., show notification, log, etc.)
    console.log('Agent completed task:', event.detail);
  }
</script>

<svelte:head>
  <title>HippoGenius</title>
</svelte:head>

<div class="h-screen flex flex-col bg-gray-50 dark:bg-gray-950 overflow-hidden text-gray-900 dark:text-gray-100 font-sans selection:bg-blue-100 dark:selection:bg-blue-900">
  
  <!-- Top Navigation Bar -->
  <header class="h-16 flex-shrink-0 px-8 flex items-center justify-between sticky top-0 z-20 transition-all duration-300">
    <div class="absolute inset-0 bg-white/10 dark:bg-black/10 backdrop-blur-md border-b border-white/20 dark:border-white/5"></div>
    
    <div class="relative flex items-center gap-4">
      <div class="w-10 h-10 rounded-2xl bg-gradient-to-br from-gray-800 to-black dark:from-white dark:to-gray-300 flex items-center justify-center shadow-lg ring-1 ring-black/5 dark:ring-white/10 overflow-hidden">
        <div class="absolute inset-0 bg-white/20 blur-sm"></div>
        <svg class="w-5 h-5 text-white dark:text-black relative z-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <h1 class="text-base font-bold tracking-tight text-gray-900 dark:text-white">
        HippoGenius
        {#if DEV_MODE}
          <span class="ml-2 text-xs font-normal text-orange-600 dark:text-orange-400">{$t.app.devMode}</span>
        {/if}
      </h1>
    </div>
    
    <div class="flex items-center gap-2 relative z-50">
      <!-- Learned Skills Button -->
      <button
        on:click={() => skillsPanelOpen = true}
        class="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-white/20 dark:hover:bg-white/10 rounded-xl transition-all duration-300 hover:scale-105 active:scale-95 liquid-card relative"
        title={$t.skills?.title || 'Learned Skills'}
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        {#if $skillsCount > 0}
          <span class="absolute -top-1 -right-1 w-4 h-4 bg-emerald-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">{$skillsCount}</span>
        {/if}
      </button>

      <!-- View Prompt Template Button (only show if we have a prompt) -->
      {#if hasPrompt}
        <button
          on:click={() => promptDisplayOpen = true}
          class="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-white/20 dark:hover:bg-white/10 rounded-xl transition-all duration-300 hover:scale-105 active:scale-95 liquid-card"
          title={$t.app.viewPrompt}
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </button>
      {/if}
      
      <!-- Profile Settings Button -->
      <button
        on:click={() => profileSettingsOpen = true}
        class="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-white/20 dark:hover:bg-white/10 rounded-xl transition-all duration-300 hover:scale-105 active:scale-95 liquid-card"
        title={$t.app.profileSettings}
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      </button>
      
      <!-- General Settings Button -->
      <button
        on:click={() => settingsOpen = true}
        class="p-2 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 hover:bg-white/20 dark:hover:bg-white/10 rounded-xl transition-all duration-300 hover:scale-105 active:scale-95 liquid-card"
        title={$t.app.settings}
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>
    </div>
  </header>

  <!-- Main Workspace -->
  <main class="flex-1 p-6 flex gap-6 overflow-hidden min-w-0 z-10 relative">
    <!-- Abstract background blobs -->
    <div class="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] rounded-full bg-blue-500/20 blur-[100px] pointer-events-none"></div>
    <div class="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-purple-500/20 blur-[100px] pointer-events-none"></div>

    <!-- Left Panel - Tasks -->
    <div class="w-[360px] flex-shrink-0 flex flex-col liquid-panel overflow-hidden animate-fade-in" style="animation-delay: 0.1s">
      <TaskPanel />
    </div>

    <!-- Center Panel - Chat -->
    <div class="flex-1 flex flex-col liquid-panel overflow-hidden animate-fade-in relative" style="animation-delay: 0.2s">
      <ChatPanel />
    </div>

    <!-- Right Panel - Summary -->
    <div class="w-[360px] flex-shrink-0 flex flex-col liquid-panel overflow-hidden animate-fade-in" style="animation-delay: 0.3s">
      <SummaryPanel />
    </div>
  </main>
</div>

<!-- Recording Indicator (Floating) -->
<RecordingIndicator />

<!-- Command Palette (Spotlight-like AI Agent interface) -->
<CommandPalette bind:open={commandPaletteOpen} on:agentCompleted={handleAgentCompleted} />

<!-- Floating Action Button for Command Palette -->
<button
  on:click={() => commandPaletteOpen = true}
  class="fixed bottom-6 right-6 z-40 group"
  title={$t.commandPalette?.shortcut || '⌘K Quick Command'}
>
  <div class="relative">
    <!-- Glow effect -->
    <div class="absolute inset-0 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl blur-lg opacity-50 group-hover:opacity-75 transition-opacity"></div>
    
    <!-- Button -->
    <div class="relative flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-2xl shadow-xl hover:shadow-2xl transition-all duration-300 hover:scale-105 active:scale-95">
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
      <span class="text-sm font-medium hidden sm:inline">{$t.commandPalette?.shortcut || '⌘K'}</span>
      <kbd class="hidden sm:inline px-1.5 py-0.5 text-xs bg-white/20 rounded">⌘K</kbd>
    </div>
  </div>
</button>

<!-- Task Creation Notification Toast -->
{#if taskNotification}
  <div class="fixed bottom-24 right-6 z-50 animate-slide-up">
    <div class="flex items-center gap-2 px-4 py-3 bg-green-500 text-white rounded-xl shadow-lg">
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
      </svg>
      <span class="text-sm font-medium">{taskNotification}</span>
    </div>
  </div>
{/if}

<!-- Settings Modal -->
<Settings bind:open={settingsOpen} />

<!-- Onboarding Modal -->
<OnboardingModal bind:open={onboardingOpen} />

<!-- Profile Settings Modal -->
<ProfileSettings 
  bind:open={profileSettingsOpen} 
  onPromptGenerated={() => {
    // Show the prompt display modal when a new prompt is generated from settings
    promptDisplayOpen = true;
  }}
/>

<!-- Prompt Display Modal -->
<PromptDisplayModal bind:open={promptDisplayOpen} />

<!-- Skills Panel -->
<SkillsPanel bind:open={skillsPanelOpen} />
