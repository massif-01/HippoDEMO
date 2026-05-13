<script lang="ts">
  import { onDestroy } from 'svelte';
  import { isRecording, isHighlighting } from '$lib/stores/recording';
  import { learnedSkills, newSkillsAlert } from '$lib/stores/skills';
  import { t } from '$lib/stores/i18n';

  const BACKEND_URL = 'http://localhost:8000';

  type HighlightState = 'idle' | 'highlighting' | 'waiting';
  let state: HighlightState = 'idle';
  let highlightStartTime = '';
  let highlightStopTime = '';
  let delayTimer: ReturnType<typeof setTimeout> | null = null;
  let abortController: AbortController | null = null;

  function reset() {
    state = 'idle';
    highlightStartTime = '';
    highlightStopTime = '';
    $isHighlighting = false;
    if (delayTimer) { clearTimeout(delayTimer); delayTimer = null; }
    if (abortController) { abortController.abort(); abortController = null; }
  }

  $: if (!$isRecording && state !== 'idle') {
    reset();
  }

  async function handleClick() {
    if (!$isRecording) return;

    if (state === 'idle') {
      highlightStartTime = new Date().toISOString();
      state = 'highlighting';
      $isHighlighting = true;
      return;
    }

    if (state === 'highlighting') {
      highlightStopTime = new Date().toISOString();
      state = 'waiting';
      $isHighlighting = false;

      try {
        await new Promise<void>((resolve, reject) => {
          abortController = new AbortController();
          const onAbort = () => reject(new DOMException('Aborted', 'AbortError'));
          abortController.signal.addEventListener('abort', onAbort);
          delayTimer = setTimeout(() => {
            abortController?.signal.removeEventListener('abort', onAbort);
            resolve();
          }, 30_000);
        });

        abortController = new AbortController();
        const response = await fetch(`${BACKEND_URL}/api/sop_generator`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            check_in: highlightStartTime,
            check_out: highlightStopTime
          }),
          signal: abortController.signal
        });

        if (response.ok) {
          const data = await response.json();
          const mdfile: string = data.mdfile || '';
          const name: string = data.name || 'SOP Skill';
          const description: string = data.description || '';
          if (mdfile) {
            learnedSkills.addSkills([{ name, description, content: mdfile }]);
            $newSkillsAlert = 1;
            console.log('[Highlight] SOP skill learned:', name);
          }
        } else {
          console.error('[Highlight] API error:', response.statusText);
        }
      } catch (e) {
        if (e instanceof DOMException && e.name === 'AbortError') {
          console.log('[Highlight] Cancelled');
        } else {
          console.error('[Highlight] Error:', e);
        }
      } finally {
        delayTimer = null;
        abortController = null;
        state = 'idle';
      }
    }
  }

  onDestroy(() => {
    if (delayTimer) clearTimeout(delayTimer);
    if (abortController) abortController.abort();
  });

  $: title = state === 'idle'
    ? ($t.highlight?.start || 'Highlight SOP')
    : state === 'highlighting'
      ? ($t.highlight?.stop || 'Stop Highlight')
      : ($t.highlight?.waiting || 'Analyzing...');
</script>

{#if $isRecording || state === 'waiting'}
  <button
    on:click={handleClick}
    disabled={state === 'waiting'}
    class="p-2 rounded-lg transition-all {
      state === 'highlighting'
        ? 'bg-amber-500 hover:bg-amber-600 text-white animate-pulse'
        : state === 'waiting'
          ? 'bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-wait'
          : 'text-amber-500 hover:text-amber-600 dark:text-amber-400 dark:hover:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/20'
    }"
    {title}
  >
    {#if state === 'waiting'}
      <svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    {:else if state === 'highlighting'}
      <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <rect x="6" y="6" width="12" height="12" rx="2" />
      </svg>
    {:else}
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
      </svg>
    {/if}
  </button>
{/if}
