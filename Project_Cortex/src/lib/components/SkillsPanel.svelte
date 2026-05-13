<script lang="ts">
  import { fade, scale, fly } from 'svelte/transition';
  import { backOut } from 'svelte/easing';
  import { learnedSkills, newSkillsAlert, skillsCount } from '$lib/stores/skills';
  import type { LearnedSkill } from '$lib/stores/skills';
  import { t } from '$lib/stores/i18n';
  import { marked } from 'marked';
  import { onMount, onDestroy } from 'svelte';

  export let open = false;

  let expandedSkillId: string | null = null;
  let showToast = false;
  let toastCount = 0;
  let toastTimer: ReturnType<typeof setTimeout> | null = null;

  const unsubAlert = newSkillsAlert.subscribe(count => {
    if (count > 0) {
      toastCount = count;
      showToast = true;
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = setTimeout(() => {
        showToast = false;
        $newSkillsAlert = 0;
      }, 5000);
    }
  });

  onMount(() => {
    learnedSkills.load();
  });

  onDestroy(() => {
    unsubAlert();
    if (toastTimer) clearTimeout(toastTimer);
  });

  function close() {
    open = false;
    expandedSkillId = null;
  }

  function toggleExpand(id: string) {
    expandedSkillId = expandedSkillId === id ? null : id;
  }

  function removeSkill(id: string) {
    learnedSkills.removeSkill(id);
    if (expandedSkillId === id) expandedSkillId = null;
  }

  function clearAll() {
    learnedSkills.clearSkills();
    expandedSkillId = null;
  }

  function sanitizeHtml(html: string): string {
    return html.replace(/<img\s+([^>]*?)src="([^"]*)"([^>]*)>/g, (match, pre, src, post) => {
      if (!src || src === 'undefined' || src === 'null') {
        const altMatch = (pre + post).match(/alt="([^"]*)"/);
        return altMatch?.[1] ? `[Image: ${altMatch[1]}]` : '';
      }
      return match;
    });
  }

  function renderMarkdown(content: string): string {
    return sanitizeHtml(marked(content) as string);
  }

  function dismissToast() {
    showToast = false;
    $newSkillsAlert = 0;
  }

  function openFromToast() {
    dismissToast();
    open = true;
  }

  $: skills = $learnedSkills;
</script>

<!-- Toast Alert -->
{#if showToast}
  <div
    class="fixed top-20 left-1/2 -translate-x-1/2 z-[200]"
    transition:fly={{ y: -30, duration: 300 }}
  >
    <div class="flex items-center gap-3 px-5 py-3 bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-2xl shadow-xl">
      <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
      <span class="text-sm font-medium">
        {$t.skills?.alert?.replace('{count}', String(toastCount)) || `Learned ${toastCount} new skill(s)!`}
      </span>
      <button
        on:click={openFromToast}
        class="px-3 py-1 text-xs font-semibold bg-white/20 hover:bg-white/30 rounded-lg transition-colors"
      >
        {$t.skills?.viewAll || 'View'}
      </button>
      <button on:click={dismissToast} class="ml-1 opacity-70 hover:opacity-100 transition-opacity">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  </div>
{/if}

<!-- Panel Modal -->
{#if open}
  <div
    class="fixed inset-0 z-[100] backdrop-overlay"
    transition:fade={{ duration: 200 }}
    on:click={close}
    on:keydown={e => e.key === 'Escape' && close()}
    role="button"
    tabindex="-1"
    aria-label="Close skills panel"
  />

  <div class="fixed inset-0 z-[101] flex items-start justify-center pt-[10vh] pointer-events-none">
    <div
      class="skills-panel pointer-events-auto"
      transition:scale={{ duration: 250, start: 0.96, easing: backOut }}
      role="dialog"
      aria-modal="true"
      aria-label="Learned Skills"
    >
      <!-- Header -->
      <div class="panel-header-bar">
        <div class="flex items-center gap-3">
          <div class="p-2 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-xl text-white">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <div>
            <h2 class="text-base font-bold text-gray-900 dark:text-white">
              {$t.skills?.title || 'Learned Skills'}
            </h2>
            <p class="text-xs text-gray-500 dark:text-gray-400">
              {skills.length} {$t.skills?.learnedCount || 'skills learned'}
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          {#if skills.length > 0}
            <button
              on:click={clearAll}
              class="px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
            >
              {$t.skills?.clear || 'Clear All'}
            </button>
          {/if}
          <button on:click={close} class="p-1.5 hover:bg-black/5 dark:hover:bg-white/10 rounded-lg transition-colors">
            <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Skills List -->
      <div class="skills-list">
        {#if skills.length === 0}
          <div class="flex flex-col items-center justify-center py-16 text-center">
            <div class="w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center mb-4">
              <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <p class="text-sm font-medium text-gray-900 dark:text-gray-100">{$t.skills?.empty || 'No skills yet'}</p>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-[240px]">
              {$t.skills?.emptyDesc || 'Skills learned from screen recordings will appear here.'}
            </p>
          </div>
        {:else}
          {#each skills as skill (skill.id)}
            <div
              class="skill-card"
              transition:fly={{ y: 10, duration: 200 }}
            >
              <button
                class="skill-header"
                on:click={() => toggleExpand(skill.id)}
              >
                <div class="flex items-center gap-3 min-w-0">
                  <div class="skill-icon">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <div class="min-w-0">
                    <p class="text-sm font-semibold text-gray-900 dark:text-white truncate">{skill.name}</p>
                    <p class="text-[11px] text-gray-400 dark:text-gray-500 truncate">
                      {skill.description || skill.learnedAt.toLocaleString()}
                    </p>
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    on:click|stopPropagation={() => removeSkill(skill.id)}
                    class="p-1 opacity-0 group-hover:opacity-100 hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500 rounded-md transition-all"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                  <svg
                    class="w-4 h-4 text-gray-400 transition-transform {expandedSkillId === skill.id ? 'rotate-180' : ''}"
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </button>

              {#if expandedSkillId === skill.id}
                <div class="skill-content" transition:fly={{ y: -10, duration: 200 }}>
                  <div class="prose prose-sm dark:prose-invert max-w-none break-words">
                    {@html renderMarkdown(skill.content)}
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        {/if}
      </div>

      <!-- Footer -->
      <div class="panel-footer">
        <div class="flex items-center gap-6 text-xs text-gray-400">
          <span>
            <kbd class="kbd-s">Esc</kbd> {$t.skills?.closeHint || 'Close'}
          </span>
          <span class="text-gray-300 dark:text-gray-600">
            {$t.skills?.useHint || 'Use @ in Command Palette to reference skills'}
          </span>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop-overlay {
    background: rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }
  :global(.dark) .backdrop-overlay {
    background: rgba(0, 0, 0, 0.6);
  }

  .skills-panel {
    width: 100%;
    max-width: 560px;
    max-height: 75vh;
    margin: 0 16px;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 16px;
    border: 1px solid rgba(0, 0, 0, 0.08);
    box-shadow:
      0 24px 80px -12px rgba(0, 0, 0, 0.25),
      0 0 0 1px rgba(255, 255, 255, 0.5) inset;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  :global(.dark) .skills-panel {
    background: rgba(28, 28, 30, 0.95);
    border-color: rgba(255, 255, 255, 0.1);
    box-shadow:
      0 24px 80px -12px rgba(0, 0, 0, 0.5),
      0 0 0 1px rgba(255, 255, 255, 0.1) inset;
  }

  .panel-header-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    flex-shrink: 0;
  }
  :global(.dark) .panel-header-bar {
    border-bottom-color: rgba(255, 255, 255, 0.08);
  }

  .skills-list {
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
  }
  .skills-list::-webkit-scrollbar { width: 6px; }
  .skills-list::-webkit-scrollbar-track { background: transparent; }
  .skills-list::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.12);
    border-radius: 10px;
  }
  :global(.dark) .skills-list::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
  }

  .skill-card {
    margin-bottom: 8px;
    border-radius: 12px;
    border: 1px solid rgba(0, 0, 0, 0.06);
    overflow: hidden;
    transition: all 0.15s ease;
  }
  .skill-card:hover {
    border-color: rgba(0, 0, 0, 0.1);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  }
  :global(.dark) .skill-card {
    border-color: rgba(255, 255, 255, 0.08);
  }
  :global(.dark) .skill-card:hover {
    border-color: rgba(255, 255, 255, 0.12);
  }

  .skill-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 12px 14px;
    cursor: pointer;
    transition: background 0.15s ease;
  }
  .skill-header:hover {
    background: rgba(0, 0, 0, 0.02);
  }
  :global(.dark) .skill-header:hover {
    background: rgba(255, 255, 255, 0.03);
  }

  .skill-icon {
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: linear-gradient(135deg, #10b981, #14b8a6);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;
  }

  .skill-content {
    padding: 0 14px 14px 14px;
    border-top: 1px solid rgba(0, 0, 0, 0.04);
    background: rgba(0, 0, 0, 0.01);
  }
  :global(.dark) .skill-content {
    border-top-color: rgba(255, 255, 255, 0.06);
    background: rgba(255, 255, 255, 0.02);
  }

  .skill-content :global(.prose) {
    font-size: 13px;
    line-height: 1.6;
    padding-top: 12px;
  }

  .panel-footer {
    padding: 10px 20px;
    border-top: 1px solid rgba(0, 0, 0, 0.06);
    background: rgba(0, 0, 0, 0.02);
    flex-shrink: 0;
  }
  :global(.dark) .panel-footer {
    border-top-color: rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.02);
  }

  .kbd-s {
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
  :global(.dark) .kbd-s {
    color: #6b7280;
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.1);
  }
</style>
